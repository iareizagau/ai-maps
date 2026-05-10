"""
sbk's contribution to the unified /account/ area.

Implements the contract defined in apps.core.account_panels.
"""
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import EventNotice


def get_summary_card(user):
    profile = getattr(user, 'dance_profile', None)
    going = user.sbk_events.filter(status='going').count()
    interested = user.sbk_events.filter(status='interested').count()
    went = user.sbk_events.filter(status='went').count()
    claimed = user.claimed_dance_venues.count()
    pending = user.sbk_claims.filter(status='pending').count()

    if not profile and not (going + interested + went) and not claimed and not pending:
        return None

    if claimed:
        headline = _("%(n)d venues managed") % {'n': claimed}
    elif pending:
        headline = _("Claim under review")
    else:
        rank = profile.get_rank() if profile else _("Dancer")
        points = profile.points if profile else 0
        headline = f"{rank} · {points} XP"

    streak = profile.current_streak if profile else 0

    return {
        'app_slug': 'sbk',
        'headline': headline,
        'metric_primary':   {'label': _("Confirmed"),     'value': going},
        'metric_secondary': {'label': _("Streak (days)"), 'value': streak},
        'cta_label': _("View detail"),
        'cta_url': reverse('account_app_panel', kwargs={'slug': 'sbk'}),
        'plan_status': None,
    }


def render_panel(request):
    user = request.user
    now = timezone.now()

    profile = getattr(user, 'dance_profile', None)

    upcoming = (
        user.sbk_events
        .filter(event__start_date__gte=now)
        .select_related('event')
        .order_by('event__start_date')[:30]
    )
    past = (
        user.sbk_events
        .filter(event__start_date__lt=now)
        .select_related('event')
        .order_by('-event__start_date')[:10]
    )
    notices = (
        EventNotice.objects
        .filter(user=user)
        .select_related('event')
        .order_by('-created_at')[:10]
    ) if user.is_authenticated else []

    claimed = user.claimed_dance_venues.all().order_by('name')
    pending_claims = (
        user.sbk_claims
        .filter(status='pending')
        .select_related('venue')
        .order_by('-created_at')
    )
    rejected_claims = (
        user.sbk_claims
        .filter(status='rejected')
        .select_related('venue')
        .order_by('-decided_at')[:5]
    )

    return render(request, 'sbk/account_panel.html', {
        'profile': profile,
        'upcoming': upcoming,
        'past': past,
        'notices': notices,
        'claimed': claimed,
        'pending_claims': pending_claims,
        'rejected_claims': rejected_claims,
    })

