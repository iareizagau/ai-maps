"""
pintxos' contribution to the unified /account/ area.

Implements the contract defined in apps.core.account_panels.
"""
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


def get_summary_card(user):
    favs = user.dish_favorites.count()
    ratings = user.dish_ratings.count()
    claimed = user.claimed_pintxos_venues.count()
    pending = user.pintxos_claims.filter(status='pending').count()

    if favs == 0 and ratings == 0 and claimed == 0 and pending == 0:
        return None

    if claimed:
        headline = _("%(n)d venues managed") % {'n': claimed}
    elif pending:
        headline = _("Claim under review")
    else:
        headline = f"{ratings} {_('ratings')} · {favs} {_('favorites')}"

    return {
        'app_slug': 'pintxos',
        'headline': headline,
        'metric_primary':   {'label': _("Ratings"),   'value': ratings},
        'metric_secondary': {'label': _("Favorites"), 'value': favs},
        'cta_label': _("View detail"),
        'cta_url': reverse('account_app_panel', kwargs={'slug': 'pintxos'}),
        'plan_status': None,
    }


def render_panel(request):
    user = request.user
    return render(request, 'pintxos/account_panel.html', {
        'claimed': user.claimed_pintxos_venues.all().order_by('name'),
        'pending_claims': (
            user.pintxos_claims
            .filter(status='pending')
            .select_related('restaurant')
            .order_by('-created_at')
        ),
        'rejected_claims': (
            user.pintxos_claims
            .filter(status='rejected')
            .select_related('restaurant')
            .order_by('-decided_at')[:5]
        ),
        'favs': (
            user.dish_favorites
            .select_related('dish__restaurant')
            .order_by('-created_at')[:10]
        ),
        'ratings': (
            user.dish_ratings
            .select_related('dish__restaurant')
            .order_by('-created_at')[:10]
        ),
    })
