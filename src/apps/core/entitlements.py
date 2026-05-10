"""
Feature entitlement matrix.

Single source of truth for what each tier unlocks per app. Apps query this
helper instead of checking subscription rows directly, so feature gates stay
declarative.

Boolean features return bool. Numeric limits return int or None (unlimited).
"""
from typing import Any


DEFAULT_TIER = 'free'

# app_slug -> feature_key -> tier -> value
FEATURE_MATRIX: dict[str, dict[str, dict[str, Any]]] = {
    'kultur': {
        'favorites_max':       {'free': 50,    'plus': None, 'pro': None},
        'digest_email':        {'free': False, 'plus': True, 'pro': True},
        'reminders_24h':       {'free': False, 'plus': True, 'pro': True},
        'create_plan':         {'free': False, 'plus': True, 'pro': True},
        'plans_per_month':     {'free': 0,     'plus': 4,    'pro': None},
    },
    'sbk': {
        # Mirrors the pintxos split: claim flow itself is gated by login + admin
        # approval, not by tier. Pro Venue unlocks marketing/analytics for the
        # owner; Plus is for B2C dancers (matchmaking, full DanceProfile).
        'event_notices':       {'free': True,  'plus': True,  'pro': True},
        'find_partner_match':  {'free': False, 'plus': True,  'pro': True},
        'manage_claimed_venue':{'free': True,  'plus': True,  'pro': True},
        'analytics_dashboard': {'free': False, 'plus': False, 'pro': True},
        'priority_listing':    {'free': False, 'plus': False, 'pro': True},
        'venue_promotions':    {'free': False, 'plus': False, 'pro': True},
        'organizer_dashboard': {'free': False, 'plus': False, 'pro': True},
    },
    'pintxos': {
        # Free claim: any verified owner can edit their venue. Pro adds
        # analytics + priority + promotions. The claim *flow* itself is gated
        # by login + admin approval, not by tier.
        'rate_dishes':         {'free': True,  'plus': True,  'pro': True},
        'private_lists':       {'free': False, 'plus': True,  'pro': True},
        'manage_claimed_venue':{'free': True,  'plus': True,  'pro': True},
        'analytics_dashboard': {'free': False, 'plus': False, 'pro': True},
        'priority_listing':    {'free': False, 'plus': False, 'pro': True},
        'venue_promotions':    {'free': False, 'plus': False, 'pro': True},
        'review_replies':      {'free': False, 'plus': False, 'pro': True},
    },
}


def get_tier(user, app_slug: str) -> str:
    """
    Active tier for a user/app pair. Wildcard '*' bundle wins over per-app sub.
    """
    if not user.is_authenticated:
        return DEFAULT_TIER

    subs = list(
        user.subscriptions
        .filter(app_slug__in=[app_slug, '*'], status='active')
        .values('app_slug', 'tier')
    )
    if not subs:
        return DEFAULT_TIER
    for s in subs:
        if s['app_slug'] == '*':
            return s['tier']
    return subs[0]['tier']


def has_entitlement(user, app_slug: str, feature: str) -> Any:
    """
    Entitlement value for (user, app, feature). Raises KeyError on typos so
    misuse surfaces in tests instead of silently returning False.
    """
    tier = get_tier(user, app_slug)
    feature_tiers = FEATURE_MATRIX[app_slug][feature]
    return feature_tiers.get(tier, feature_tiers[DEFAULT_TIER])
