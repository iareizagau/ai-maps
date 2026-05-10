"""
kultur's contribution to the unified /account/ area.

Implements the contract defined in apps.core.account_panels.
"""
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def get_summary_card(user):
    favs_qs = user.kultur_favs.all()
    total = favs_qs.count()
    if total == 0:
        return None

    upcoming = favs_qs.filter(event__start_date__gte=timezone.now()).count()
    past = total - upcoming

    return {
        'app_slug': 'kultur',
        'headline': _("%(n)d events saved") % {'n': total},
        'metric_primary':   {'label': _("Upcoming"), 'value': upcoming},
        'metric_secondary': {'label': _("Past"),     'value': past},
        'cta_label': _("View detail"),
        'cta_url': reverse('account_app_panel', kwargs={'slug': 'kultur'}),
        'plan_status': None,
    }


def render_panel(request):
    user = request.user
    now = timezone.now()

    upcoming = (
        user.kultur_favs
        .filter(event__start_date__gte=now)
        .select_related('event__venue')
        .order_by('event__start_date')[:50]
    )
    past = (
        user.kultur_favs
        .filter(event__start_date__lt=now)
        .select_related('event__venue')
        .order_by('-event__start_date')[:20]
    )

    prefs = getattr(user, 'kultur_prefs', None)

    return render(request, 'kultur/account_panel.html', {
        'upcoming': upcoming,
        'past': past,
        'prefs': prefs,
    })
