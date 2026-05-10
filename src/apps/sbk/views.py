from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect, HttpResponseBadRequest, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.db import models
from django.db.models import F
from django.utils.translation import gettext_lazy as _
import json
from apps.core.entitlements import has_entitlement
from .forms import DanceVenueClaimForm, DanceVenueManageForm
from .models import (
    Event, UserEvent, UserEventStatus, EventReview, DanceProfile,
    EventNotice, CheckIn, VibeReport, EventType,
    DanceVenue, DanceVenueClaim,
)
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

def map_view(request):
    """
    Main view that renders the Leaflet map and Passport UI.
    """
    context = {
        'OPENWEATHERMAP_API_KEY': settings.OPENWEATHERMAP_API_KEY
    }
    return render(request, 'sbk/pages/home/map.html', context)

def events_json(request):
    """
    Returns events as JSON for the Leaflet map.
    """
    # Filter out rejected or highly reported events
    from django.utils import timezone
    from datetime import timedelta
    
    now = timezone.now()
    yesterday = now - timedelta(days=1)
    
    # Filter: Upcoming events or those that ended very recently (24h margin for reviews)
    events = Event.objects.prefetch_related('reviews', 'checkins', 'vibe_reports').filter(
        moderation_status__in=['pending', 'verified']
    ).filter(
        models.Q(end_date__gte=yesterday) | 
        models.Q(end_date__isnull=True, start_date__gte=yesterday)
    ).exclude(report_count__gte=3)
    
    # If user is logged in, get their event statuses
    user_statuses = {}
    if request.user.is_authenticated:
        user_events = UserEvent.objects.filter(user=request.user)
        for ue in user_events:
            user_statuses[ue.event_id] = ue.status
            
    data = []
    for e in events:
        # Calculate review stats
        reviews = e.reviews.all()
        avg_rating = sum(r.overall_rating for r in reviews) / len(reviews) if reviews else None
        
        # Pulse Data (Live)
        now = timezone.now()
        four_hours_ago = now - timedelta(hours=4)
        
        # Timing metadata
        is_happening = False
        is_recent_past = False
        
        if e.start_date:
            end_bound = e.end_date or (e.start_date + timedelta(hours=8))
            if e.start_date <= now <= end_bound:
                is_happening = True
            elif now > end_bound:
                is_recent_past = True
                
        active_checkins = 0
        vibe_summary = None
        if is_happening:
            active_checkins = e.checkins.filter(created_at__gte=four_hours_ago).count()
            # Calculate recent vibe
            recent_vibes = e.vibe_reports.filter(created_at__gte=four_hours_ago)
            if recent_vibes.exists():
                count = recent_vibes.count()
                vibe_summary = {
                    'music': round(sum(v.music_score for v in recent_vibes) / count, 1),
                    'crowd': round(sum(v.crowd_score for v in recent_vibes) / count, 1),
                    'ac': round(sum(v.ac_score for v in recent_vibes) / count, 1),
                    'count': count
                }

        data.append({
            'id': str(e.id),
            'name': e.name,
            'description': e.short_description or e.description[:200],
            'start_date': e.start_date.isoformat() if e.start_date else None,
            'end_date': e.end_date.isoformat() if e.end_date else None,
            'event_type': e.event_type,
            'primary_style': e.primary_style,
            'lat': float(e.lat) if e.lat else None,
            'lng': float(e.lng) if e.lng else None,
            'city': e.city,
            'country': e.country,
            'image_url': e.poster.url if e.poster else e.image_url,
            'ticket_url': e.ticket_url,
            'price_info': e.price_info,
            'atmosphere': e.atmosphere,
            'is_recent_past': is_recent_past,
            'is_verified': e.is_verified or not e.is_user_submitted,
            'is_user_submitted': e.is_user_submitted,
            'user_status': user_statuses.get(e.id, None),
            'avg_rating': round(avg_rating, 1) if avg_rating else None,
            'review_count': len(reviews),
            'pulse': {
                'active_checkins': active_checkins,
                'vibe': vibe_summary
            }
        })
        
    return JsonResponse({'events': data})

@require_POST
@login_required
def toggle_event_status(request, event_id):
    """
    Toggle the user's status for a specific event (interested -> going -> none).
    """
    try:
        data = json.loads(request.body)
        target_status = data.get('status')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
    event = get_object_or_404(Event, id=event_id)
    
    if target_status not in [s[0] for s in UserEventStatus.choices] and target_status is not None:
        return JsonResponse({'error': 'Invalid status'}, status=400)
        
    if target_status is None:
        # Remove the UserEvent if status is null/none
        UserEvent.objects.filter(user=request.user, event=event).delete()
        return JsonResponse({'status': None})
        
    # Update or create the UserEvent
    user_event, created = UserEvent.objects.update_or_create(
        user=request.user,
        event=event,
        defaults={'status': target_status}
    )
    
    # Auto-verification logic
    if event.is_user_submitted and not event.is_verified:
        # If 3 or more people are "GOING", mark as verified
        going_count = UserEvent.objects.filter(event=event, status=UserEventStatus.GOING).count()
        if going_count >= 3:
            event.is_verified = True
            event.moderation_status = 'verified'
            event.save()
            # Reward the original submitter for a verified quality event (+100 XP)
            if event.submitted_by:
                add_xp(event.submitted_by, 100)
    
    # Reward user for confirm going (+5 XP)
    if target_status == UserEventStatus.GOING:
        add_xp(request.user, 5)
            
    return JsonResponse({
        'status': user_event.status,
        'is_verified': event.is_verified
    })

@login_required
def passport_view(request):
    """
    User's personal dashboard (Pasaporte Bailador).
    """
    user_events = UserEvent.objects.filter(user=request.user).select_related('event').order_by('event__start_date')
    
    # Split into upcoming and past based on current date
    from django.utils import timezone
    now = timezone.now()
    
    going_events = [ue for ue in user_events if ue.status == UserEventStatus.GOING and ue.event.start_date and ue.event.start_date >= now]
    interested_events = [ue for ue in user_events if ue.status == UserEventStatus.INTERESTED and ue.event.start_date and ue.event.start_date >= now]
    past_events = [ue for ue in user_events if ue.event.start_date and ue.event.start_date < now]
    
    # Also update 'going' to 'went' automatically if past
    for ue in past_events:
        if ue.status == UserEventStatus.GOING:
            ue.status = UserEventStatus.WENT
            ue.save()
            
    # We re-calculate after update just in case
    went_events = [ue for ue in past_events if ue.status == UserEventStatus.WENT]
    
    # Get User Rank
    profile, _ = DanceProfile.objects.get_or_create(user=request.user)
    
    # Get Leaderboard
    leaderboard = DanceProfile.objects.select_related('user').order_by('-points')[:10]
    
    context = {
        'going_events': going_events,
        'interested_events': interested_events,
        'went_events': went_events,
        'profile': profile,
        'leaderboard': leaderboard,
        'UserEventStatus': UserEventStatus, # Pass class for status checking in templates
        'stats_countries': len(set([ue.event.country for ue in user_events if ue.event.country])),
        'stats_total_events': len(went_events),
        'user_points': profile.points,
        'user_rank': profile.get_rank(),
    }
    
    return render(request, 'sbk/passport.html', context)

@require_POST
@login_required
def toggle_matchmaking(request, event_id):
    """
    Toggle matchmaking preferences (roommate or dance partner) for an event.
    """
    try:
        data = json.loads(request.body)
        field = data.get('field') # 'roommate' or 'partner'
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
    event = get_object_or_404(Event, id=event_id)
    
    # User must be "GOING" to the event to seek a partner or roommate
    user_event = get_object_or_404(UserEvent, user=request.user, event=event)
    
    if field == 'roommate':
        user_event.looking_for_roommate = not user_event.looking_for_roommate
        user_event.save()
        return JsonResponse({'status': user_event.looking_for_roommate})
    elif field == 'partner':
        user_event.looking_for_dance_partner = not user_event.looking_for_dance_partner
        user_event.save()
        return JsonResponse({'status': user_event.looking_for_dance_partner})
        
    return JsonResponse({'error': 'Invalid field'}, status=400)

def event_community_api(request, event_id):
    """
    Returns the list of users going to or interested in an event,
    along with their matchmaking preferences.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Debes iniciar sesión para ver la comunidad.'}, status=403)
        
    event = get_object_or_404(Event, id=event_id)
    
    # We only show people who are "GOING" or "INTERESTED"
    # To protect some privacy, maybe only GOING. Let's show GOING for now.
    user_events = UserEvent.objects.filter(
        event=event, 
        status=UserEventStatus.GOING
    ).select_related('user')
    
    community = []
    for ue in user_events:
        # Don't show the current user in the community list to themselves
        if ue.user == request.user:
            continue
            
        profile, _ = DanceProfile.objects.get_or_create(user=ue.user)
            
        community.append({
            'username': ue.user.username,
            'avatar_url': getattr(ue.user, 'avatar_url', None) or f"https://ui-avatars.com/api/?name={ue.user.username}&background=random",
            'looking_for_roommate': ue.looking_for_roommate,
            'looking_for_dance_partner': ue.looking_for_dance_partner,
            'notes': ue.notes,
            'rank': profile.get_rank(),
            'points': profile.points,
        })
        
    # Get Notices
    notices_qs = EventNotice.objects.filter(event=event).select_related('user').order_by('-created_at')
    notices = []
    for n in notices_qs:
        n_profile, _ = DanceProfile.objects.get_or_create(user=n.user)
        notices.append({
            'id': n.id,
            'username': n.user.username,
            'category': n.category,
            'category_display': n.get_category_display(),
            'message': n.message,
            'created_at': n.created_at.strftime("%H:%M"),
            'rank': n_profile.get_rank(),
            'avatar_url': getattr(n.user, 'avatar_url', None) or f"https://ui-avatars.com/api/?name={n.user.username}&background=random",
        })
        
    return JsonResponse({
        'event_name': event.name,
        'community': community,
        'notices': notices
    })

@require_POST
@login_required
def submit_event_review(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    
    # Optional: ensure user actually went. If they are reviewing, they should have went.
    # user_event = get_object_or_404(UserEvent, user=request.user, event=event, status=UserEventStatus.WENT)
    
    try:
        data = json.loads(request.body)
        review, created = EventReview.objects.update_or_create(
            event=event,
            user=request.user,
            defaults={
                'overall_rating': int(data.get('overall_rating', 3)),
                'floor_quality': int(data.get('floor_quality', 3)),
                'ac_ventilation': int(data.get('ac_ventilation', 3)),
                'gender_ratio': int(data.get('gender_ratio', 3)),
                'music_quality': int(data.get('music_quality', 3)),
                'comment': data.get('comment', '')[:1000]
            }
        )
        # Reward for review (+15 XP)
        if created:
            add_xp(request.user, 15)
            
        return JsonResponse({'status': 'success', 'message': 'Reseña guardada correctamente'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_POST
@login_required
def submit_local_social(request):
    """
    Allows a user to submit a local social or party with support for image upload.
    """
    try:
        # Check if it's multipart (file upload) or JSON
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            poster = None
        else:
            data = request.POST
            poster = request.FILES.get('poster')
            
        name = data.get('name')
        lat = data.get('lat')
        lng = data.get('lng')
        date_str = data.get('date')
        primary_style = data.get('primary_style', 'mixed')
        price_info = data.get('price_info')
        atmosphere = data.get('atmosphere')
        
        if not name or not lat or not lng or not date_str:
            return JsonResponse({'error': 'Faltan campos obligatorios'}, status=400)
            
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone
        
        # Simple parsing
        start_date = parse_datetime(f"{date_str}T22:00:00Z")
        if not start_date:
            start_date = timezone.now()
            
        event = Event.objects.create(
            name=name,
            start_date=start_date,
            end_date=start_date + timezone.timedelta(hours=5),
            lat=lat,
            lng=lng,
            primary_style=primary_style,
            event_type=EventType.PARTY,
            price_info=price_info,
            atmosphere=atmosphere,
            poster=poster,
            is_user_submitted=True,
            submitted_by=request.user
        )
        
        # Reward for submission (+50 XP)
        add_xp(request.user, 50)
        
        return JsonResponse({'status': 'success', 'message': '¡Social añadido con éxito!', 'event_id': str(event.id)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_POST
@login_required
def report_event(request, event_id):
    """
    Increments report count for an event.
    """
    event = get_object_or_404(Event, id=event_id)
    event.report_count += 1
    
    # If 3 or more reports, we hide it (filtered in events_json)
    event.save()
    return JsonResponse({'status': 'success', 'message': 'Reporte enviado. Gracias por ayudar a la comunidad.'})

@require_GET
def ticket_redirect(request, event_id):
    """
    Affiliate-tracking redirect: increments ticket_clicks and sends user to ticket_url.
    """
    event = get_object_or_404(Event, id=event_id)
    if not event.ticket_url:
        return HttpResponseBadRequest("No ticket URL")
    Event.objects.filter(pk=event.pk).update(ticket_clicks=F('ticket_clicks') + 1)
    return HttpResponseRedirect(event.ticket_url)

def add_xp(user, amount):
    profile, created = DanceProfile.objects.get_or_create(user=user)
    profile.points += amount
    profile.save()

@require_POST
@login_required
def submit_event_notice(request, event_id):
    """
    Submit a matching notice (partner, transport, etc.)
    """
    event = get_object_or_404(Event, id=event_id)
    try:
        data = json.loads(request.body)
        category = data.get('category', 'other')
        message = data.get('message', '').strip()
        
        if not message:
            return JsonResponse({'error': 'El mensaje no puede estar vacío'}, status=400)
            
        notice = EventNotice.objects.create(
            event=event,
            user=request.user,
            category=category,
            message=message[:250]
        )
        
        # Reward (+10 XP)
        add_xp(request.user, 10)
        
        return JsonResponse({'status': 'success', 'message': 'Anuncio publicado correctamente'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_POST
@login_required
def check_in(request, event_id):
    """
    Check-in to an event (only if physically there - handled by client-side GPS)
    """
    event = get_object_or_404(Event, id=event_id)
    now = timezone.now()

    # Validation: Only allow check-in if event is happening today/now
    if event.start_date:
        start_margin = event.start_date - timedelta(hours=2) # 2h before
        end_bound = event.end_date or (event.start_date + timedelta(hours=10)) # 10h total if no end
        
        if now < start_margin:
            return JsonResponse({'error': 'Demasiado pronto. El check-in abre 2 horas antes del inicio.'}, status=400)
        if now > end_bound:
            return JsonResponse({'error': 'El evento ya ha finalizado o no está activo hoy.'}, status=400)
    
    # Check if already checked in today (approx)
    checkin, created = CheckIn.objects.get_or_create(event=event, user=request.user)
    
    # Streak Logic
    today = timezone.now().date()
    profile, _ = DanceProfile.objects.get_or_create(user=request.user)
    
    if created:
        if profile.last_checkin_date:
            diff = (today - profile.last_checkin_date).days
            if diff == 1: # Consecutive day
                profile.current_streak += 1
            elif diff > 1: # Broke streak
                profile.current_streak = 1
            # if diff == 0, already checked in today (streak stays same)
        else:
            profile.current_streak = 1
            
        profile.last_checkin_date = today
        if profile.current_streak > profile.max_streak:
            profile.max_streak = profile.current_streak
        
        add_xp(request.user, 10) # Base Reward
        
        # Streak Bonus XP
        if profile.current_streak >= 3:
            bonus = profile.current_streak * 5
            add_xp(request.user, bonus)
            msg = f'¡Check-in realizado! +10 XP. ¡Racha de {profile.current_streak} días! (+{bonus} XP Bonus)'
        else:
            msg = '¡Check-in realizado! +10 XP'
            
        profile.save()
        return JsonResponse({'status': 'success', 'message': msg})
    else:
        # Update timestamp to refresh the 4-hour window
        checkin.created_at = timezone.now()
        checkin.save()
        return JsonResponse({'status': 'success', 'message': 'Has refrescado tu presencia en el evento'})

@require_POST
@login_required
def submit_vibe_report(request, event_id):
    """
    Submit a real-time vibe report
    """
    event = get_object_or_404(Event, id=event_id)
    now = timezone.now()
    
    # Validation: Only allow reporting if event is happening now
    if event.start_date:
        start_margin = event.start_date - timedelta(hours=1) # 1h before start
        end_bound = event.end_date or (event.start_date + timedelta(hours=12))
        if now < start_margin or now > end_bound:
            return JsonResponse({'error': 'Solo puedes reportar el ambiente durante el transcurso del evento.'}, status=400)

    try:
        data = json.loads(request.body)
        VibeReport.objects.create(
            event=event,
            user=request.user,
            music_score=data.get('music', 3),
            crowd_score=data.get('crowd', 3),
            ac_score=data.get('ac', 3)
        )
        add_xp(request.user, 15) # Reward for reporting
        return JsonResponse({'status': 'success', 'message': '¡Vibe reportada! +15 XP'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ---------------------------------------------------------------------------
# DanceVenue claim + manage flow (B2B Pro Venue)
# ---------------------------------------------------------------------------

@login_required
def dance_venue_claim(request, venue_id):
    venue = get_object_or_404(DanceVenue, id=venue_id)

    if venue.claimed_by_id:
        if venue.claimed_by_id == request.user.id:
            return redirect('sbk:dance_venue_manage', venue_id=venue.id)
        messages.error(request, _("This venue is already claimed."))
        return redirect('account_app_panel', slug='sbk')

    existing = DanceVenueClaim.objects.filter(venue=venue, claimant=request.user).first()
    if existing and existing.status == DanceVenueClaim.Status.PENDING:
        messages.info(request, _("You already submitted a claim for this venue. We're reviewing it."))
        return redirect('account_app_panel', slug='sbk')

    if request.method == 'POST':
        form = DanceVenueClaimForm(request.POST, instance=existing)
        if form.is_valid():
            claim = form.save(commit=False)
            claim.venue = venue
            claim.claimant = request.user
            claim.status = DanceVenueClaim.Status.PENDING
            claim.decided_at = None
            claim.reviewed_by = None
            claim.save()
            messages.success(request, _("Claim submitted. We'll get back to you within 48h."))
            return redirect('account_app_panel', slug='sbk')
    else:
        form = DanceVenueClaimForm(instance=existing, initial={
            'contact_email': request.user.email,
            'contact_phone': getattr(request.user, 'phone', '') or '',
        })

    return render(request, 'sbk/claim.html', {'venue': venue, 'form': form})


@login_required
def dance_venue_manage(request, venue_id):
    venue = get_object_or_404(DanceVenue, id=venue_id)
    if venue.claimed_by_id != request.user.id and not request.user.is_staff:
        return HttpResponseForbidden(_("You don't manage this venue."))

    if request.method == 'POST':
        form = DanceVenueManageForm(request.POST, instance=venue)
        if form.is_valid():
            form.save()
            messages.success(request, _("Venue updated."))
            return redirect('sbk:dance_venue_manage', venue_id=venue.id)
    else:
        form = DanceVenueManageForm(instance=venue)

    return render(request, 'sbk/manage.html', {
        'venue': venue,
        'form': form,
        'has_analytics': has_entitlement(request.user, 'sbk', 'analytics_dashboard'),
        'has_priority': has_entitlement(request.user, 'sbk', 'priority_listing'),
    })
