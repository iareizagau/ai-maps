"""
Pluggable account-panel registry.

Each vertical app may expose `apps.<slug>.account` with two callables:

    get_summary_card(user) -> dict | None
        Card data for the /account/apps/ hub. Returning None hides the app.

    render_panel(request) -> HttpResponse
        Detailed panel rendered inside the /account/ layout at
        /account/apps/<slug>/. Optional; if missing, the slug 404s.

`AppRegistry` rows drive iteration order, so disabling an app in the registry
removes it from the hub without code changes. Apps without an `account` module
(zbe, inguru, gailur today) simply don't appear.
"""
import importlib
import logging

from .models import AppRegistry

logger = logging.getLogger(__name__)


def _load_module(slug):
    try:
        return importlib.import_module(f'apps.{slug}.account')
    except ModuleNotFoundError:
        return None
    except Exception:
        logger.exception("Failed to import apps.%s.account", slug)
        return None


def collect_panels(user):
    """
    Returns [(AppRegistry, card_dict), ...] for the hub. Apps without
    `get_summary_card` or returning None are filtered out.
    """
    cards = []
    for app in AppRegistry.objects.filter(is_active=True).order_by('slug'):
        mod = _load_module(app.slug)
        if not mod:
            continue
        getter = getattr(mod, 'get_summary_card', None)
        if not getter:
            continue
        try:
            card = getter(user)
        except Exception:
            logger.exception("get_summary_card crashed for %s", app.slug)
            continue
        if card:
            cards.append((app, card))
    return cards


def render_app_panel(request, slug):
    """
    Delegates rendering to `apps.<slug>.account.render_panel(request)`.
    Returns None if the app does not implement a panel.
    """
    mod = _load_module(slug)
    if not mod:
        return None
    renderer = getattr(mod, 'render_panel', None)
    if not renderer:
        return None
    return renderer(request)
