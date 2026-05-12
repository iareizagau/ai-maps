from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect, HttpResponseBadRequest, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.db import models
from django.db.models import F, Q, Count
from django.utils.translation import gettext_lazy as _
import json
from apps.core.entitlements import has_entitlement
from .forms import DanceVenueClaimForm, DanceVenueManageForm
from .models import (
    Event, UserEvent, UserEventStatus, EventReview, DanceProfile,
    EventNotice, CheckIn, VibeReport, EventType,
    DanceVenue, DanceVenueClaim, Person, EventOccurrence
)
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

def map_view(request):
    """
    Main map interface with SEO context.
    """
    context = {
        'page_title': _('SBK Hub - Mapa de Festivales y Socials'),
        'OPENWEATHERMAP_API_KEY': settings.OPENWEATHERMAP_API_KEY
    }
    return render(request, 'sbk/pages/home/map.html', context)

def tonight_view(request):
    """
    SEO Landing: Events happening tonight.
    """
    today = timezone.now().date()
    count = Event.objects.filter(start_date__date=today).count()
    
    context = {
        'page_filter': 'tonight',
        'page_title': _('SBK esta noche: Festivales y Sociales hoy | SBK Hub'),
        'page_h1': _('%d eventos para bailar hoy') % count if count > 0 else _('SBK esta noche'),
        'meta_description': _('¿Dónde bailar esta noche? Lista actualizada de sesiones sociales, talleres y fiestas SBK para hoy.'),
        'OPENWEATHERMAP_API_KEY': settings.OPENWEATHERMAP_API_KEY
    }
    return render(request, 'sbk/pages/home/map.html', context)

def type_view(request, type_slug):
    """
    SEO Landing: Events filtered by type.
    """
    type_map = {
        'festivales': ('festival', _('Próximos Festivales SBK'), _('Calendario de congresos y festivales internacionales de Bachata, Salsa y Kizomba.')),
        'socials': ('party', _('Sesiones Sociales y Fiestas SBK'), _('Encuentra los mejores sociales para bailar durante la semana.')),
        'talleres': ('workshop', _('Talleres y Bootcamps SBK'), _('Mejora tu estilo con los mejores talleres intensivos.')),
    }
    
    if type_slug not in type_map:
        return redirect('sbk:map')
        
    db_type, h1, meta = type_map[type_slug]
    
    context = {
        'page_filter': db_type,
        'page_title': f"{h1} | SBK Hub",
        'page_h1': h1,
        'meta_description': meta,
        'OPENWEATHERMAP_API_KEY': settings.OPENWEATHERMAP_API_KEY
    }
    return render(request, 'sbk/pages/home/map.html', context)

def city_view(request, city_slug):
    """
    SEO Landing: Events in a specific city.
    """
    from django.utils.text import slugify
    events = Event.objects.all()
    city_name = "Desconocida"
    target_event = None
    
    for e in events:
        if slugify(e.city) == city_slug:
            target_event = e
            city_name = e.city
            break
            
    if not target_event:
        return redirect('sbk:map')

    context = {
        'page_filter': f'city:{city_slug}',
        'page_title': _('SBK en %s: Dónde bailar Salsa y Bachata') % city_name,
        'page_h1': _('Eventos SBK en %s') % city_name,
        'meta_description': _('Descubre todos los eventos de baile en %s. Festivales, sociales y academias en un solo mapa.') % city_name,
        'initial_center': [target_event.lat, target_event.lng],
        'initial_zoom': 11,
        'OPENWEATHERMAP_API_KEY': settings.OPENWEATHERMAP_API_KEY
    }
    return render(request, 'sbk/pages/home/map.html', context)

def practice_view(request):
    """
    Matchmaking landing: shows people looking for partners or roommates.
    """
    now = timezone.now()
    seekers = UserEvent.objects.filter(
        Q(looking_for_dance_partner=True) | Q(looking_for_roommate=True),
        event__end_date__gte=now
    ).select_related('user', 'event').order_by('event__start_date')

    context = {
        'seekers': seekers,
        'page_title': _('Busca pareja de baile o habitación | SBK Hub'),
        'page_h1': _('Comunidad SBK'),
        'meta_description': _('Conecta con otros bailadores. Encuentra pareja para talleres o compañeros para compartir alojamiento.'),
    }
    return render(request, 'sbk/pages/practice.html', context)

def person_directory_view(request):
    """
    SEO Landing: Directory of verified people.
    """
    people = Person.objects.filter(is_verified=True).order_by('name')
    context = {
        'people': people,
        'page_title': _('Directorio de Artistas y DJs SBK | SBK Hub'),
        'page_h1': _('Artistas de la Comunidad'),
        'meta_description': _('Conoce a los mejores DJs, profesores y artistas de la escena SBK internacional.'),
    }
    return render(request, 'sbk/pages/directory.html', context)

def person_detail_view(request, slug):
    """
    SEO Landing: Profile of a specific person.
    """
    person = get_object_or_404(Person, slug=slug)
    now = timezone.now()
    upcoming_events = Event.objects.filter(
        Q(teachers=person) | Q(djs=person) | Q(artists=person) | Q(organizer=person),
        end_date__gte=now
    ).distinct().order_by('start_date')
    
    context = {
        'person': person,
        'upcoming_events': upcoming_events,
        'page_title': _('%s | Artista SBK Hub') % person.name,
        'page_h1': person.name,
        'meta_description': person.bio[:160] if person.bio else _('Perfil oficial de %s en SBK Hub.') % person.name,
    }
    return render(request, 'sbk/pages/person_detail.html', context)

@require_GET
def events_json(request):
    """
    Returns events as JSON for the Leaflet map.
    """
    now = timezone.now()
    yesterday = now - timedelta(days=1)
    
    events = Event.objects.prefetch_related('reviews', 'checkins', 'vibe_reports').filter(
        moderation_status__in=['pending', 'verified']
    ).filter(
        models.Q(end_date__gte=yesterday) | 
        models.Q(end_date__isnull=True, start_date__gte=yesterday)
    ).exclude(report_count__gte=3)
    
    user_statuses = {}
    if request.user.is_authenticated:
        user_events = UserEvent.objects.filter(user=request.user)
        for ue in user_events:
            user_statuses[ue.event_id] = ue.status
            
    data = []
    for e in events:
        reviews = e.reviews.all()
        avg_rating = sum(r.overall_rating for r in reviews) / len(reviews) if reviews else None
        
        four_hours_ago = now - timedelta(hours=4)
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
            'description': e.short_description or e.description[:200] if e.description else "",
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

@require_GET
def venues_json(request):
    """
    Returns dance venues as JSON for the Leaflet map.
    """
    venues = DanceVenue.objects.filter(is_verified=True)
    
    data = []
    for v in venues:
        data.append({
            'id': f"venue_{v.id}",
            'name': v.name,
            'description': v.description[:200] if v.description else "",
            'venue_type': v.venue_type,
            'styles': v.styles,
            'primary_style': v.styles[0] if v.styles else 'mixed',
            'lat': float(v.lat) if hasattr(v, 'lat') and v.lat else None,
            'lng': float(v.lng) if hasattr(v, 'lng') and v.lng else None,
            'city': v.city,
            'country': v.country,
            'image_url': v.image_url,
            'is_verified': True,
            'avg_rating': v.avg_rating,
            'review_count': v.rating_count,
            'is_venue': True
        })
    return JsonResponse({'venues': data})

@require_POST
@login_required
def toggle_event_status(request, event_id):
    """
    Toggle the user's status for a specific event.
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
        UserEvent.objects.filter(user=request.user, event=event).delete()
        return JsonResponse({'status': None})
        
    user_event, created = UserEvent.objects.update_or_create(
        user=request.user,
        event=event,
        defaults={'status': target_status}
    )
    
    if event.is_user_submitted and not event.is_verified:
        going_count = UserEvent.objects.filter(event=event, status=UserEventStatus.GOING).count()
        if going_count >= 3:
            event.is_verified = True
            event.moderation_status = 'verified'
            event.save()
            if event.submitted_by:
                add_xp(event.submitted_by, 100)
    
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
    now = timezone.now()
    
    going_events = [ue for ue in user_events if ue.status == UserEventStatus.GOING and ue.event.start_date and ue.event.start_date >= now]
    interested_events = [ue for ue in user_events if ue.status == UserEventStatus.INTERESTED and ue.event.start_date and ue.event.start_date >= now]
    past_events = [ue for ue in user_events if ue.event.start_date and ue.event.start_date < now]
    
    for ue in past_events:
        if ue.status == UserEventStatus.GOING:
            ue.status = UserEventStatus.WENT
            ue.save()
            
    went_events = [ue for ue in past_events if ue.status == UserEventStatus.WENT]
    profile, _ = DanceProfile.objects.get_or_create(user=request.user)
    leaderboard = DanceProfile.objects.select_related('user').order_by('-points')[:10]
    
    context = {
        'going_events': going_events,
        'interested_events': interested_events,
        'went_events': went_events,
        'profile': profile,
        'leaderboard': leaderboard,
        'UserEventStatus': UserEventStatus,
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

@login_required
@require_GET
def event_community_api(request, event_id):
    """
    Returns users going to an event and board notices.
    """
    event = get_object_or_404(Event, id=event_id)
    user_events = UserEvent.objects.filter(
        event=event, 
        status=UserEventStatus.GOING
    ).select_related('user')
    
    community = []
    for ue in user_events:
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
        if created:
            add_xp(request.user, 15)
        return JsonResponse({'status': 'success', 'message': 'Reseña guardada correctamente'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_POST
@login_required
def submit_local_social(request):
    """
    Allows a user to submit a local social.
    """
    try:
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
        start_date = parse_datetime(f"{date_str}T22:00:00Z")
        if not start_date:
            start_date = timezone.now()
            
        # Trust-Based Logic (Waze approach)
        moderation_status = 'pending'
        is_verified = False
        
        # Auto-verify if user is a Verified Person (Organizer/Teacher) or Staff
        person_profile = Person.objects.filter(claimed_by=request.user, is_verified=True).first()
        if person_profile or request.user.is_staff:
            moderation_status = 'verified'
            is_verified = True
            
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
            submitted_by=request.user,
            moderation_status=moderation_status,
            is_verified=is_verified
        )
        
        xp_amount = 100 if is_verified else 50
        add_xp(request.user, xp_amount)
        return JsonResponse({'status': 'success', 'message': '¡Social añadido con éxito!', 'event_id': str(event.id)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_POST
@login_required
def report_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    event.report_count += 1
    event.save()
    return JsonResponse({'status': 'success', 'message': 'Reporte enviado.'})

@require_GET
def ticket_redirect(request, event_id):
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
        add_xp(request.user, 10)
        return JsonResponse({'status': 'success', 'message': 'Anuncio publicado correctamente'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_POST
@login_required
def check_in(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    now = timezone.now()
    if event.start_date:
        start_margin = event.start_date - timedelta(hours=2)
        end_bound = event.end_date or (event.start_date + timedelta(hours=10))
        if now < start_margin:
            return JsonResponse({'error': 'Demasiado pronto.'}, status=400)
        if now > end_bound:
            return JsonResponse({'error': 'El evento ya ha finalizado.'}, status=400)
    
    checkin, created = CheckIn.objects.get_or_create(event=event, user=request.user)
    today = timezone.now().date()
    profile, _ = DanceProfile.objects.get_or_create(user=request.user)
    
    if created:
        if profile.last_checkin_date:
            diff = (today - profile.last_checkin_date).days
            if diff == 1:
                profile.current_streak += 1
            elif diff > 1:
                profile.current_streak = 1
        else:
            profile.current_streak = 1
        profile.last_checkin_date = today
        if profile.current_streak > profile.max_streak:
            profile.max_streak = profile.current_streak
        add_xp(request.user, 10)
        profile.save()
        return JsonResponse({'status': 'success', 'message': '¡Check-in realizado!'})
    else:
        checkin.created_at = timezone.now()
        checkin.save()
        return JsonResponse({'status': 'success', 'message': 'Has refrescado tu presencia'})

@require_POST
@login_required
def submit_vibe_report(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    now = timezone.now()
    if event.start_date:
        start_margin = event.start_date - timedelta(hours=1)
        end_bound = event.end_date or (event.start_date + timedelta(hours=12))
        if now < start_margin or now > end_bound:
            return JsonResponse({'error': 'Solo puedes reportar el ambiente durante el evento.'}, status=400)

    try:
        data = json.loads(request.body)
        VibeReport.objects.create(
            event=event,
            user=request.user,
            music_score=data.get('music', 3),
            crowd_score=data.get('crowd', 3),
            ac_score=data.get('ac', 3)
        )
        add_xp(request.user, 15)
        return JsonResponse({'status': 'success', 'message': '¡Vibe reportada!'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

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
        messages.info(request, _("You already submitted a claim for this venue."))
        return redirect('account_app_panel', slug='sbk')
    if request.method == 'POST':
        form = DanceVenueClaimForm(request.POST, instance=existing)
        if form.is_valid():
            claim = form.save(commit=False)
            claim.venue = venue
            claim.claimant = request.user
            claim.status = DanceVenueClaim.Status.PENDING
            claim.save()
            messages.success(request, _("Claim submitted."))
            return redirect('account_app_panel', slug='sbk')
    else:
        form = DanceVenueClaimForm(instance=existing, initial={'contact_email': request.user.email})
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
    return render(request, 'sbk/manage.html', {'venue': venue, 'form': form})
