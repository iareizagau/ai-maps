"""
Kultur API: favorites + implicit preferences.

Mounted at /api/kultur/ from core/api.py. Auth is session-based (Django's
default); endpoints raise 401 for anonymous users.
"""
from typing import List, Optional

from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError

from .models import CulturalEvent, EventFavorite, KulturPrefs

router = Router(tags=['kultur'])


# --- Schemas ---------------------------------------------------------------

class FavIdsOut(Schema):
    ids: List[int]


class FavSyncIn(Schema):
    ids: List[int]


class OkOut(Schema):
    ok: bool


class PrefsOut(Schema):
    default_categories: List[str]
    default_moods: List[str]
    default_municipality: str


class PrefsPatchIn(Schema):
    default_categories: Optional[List[str]] = None
    default_moods: Optional[List[str]] = None
    default_municipality: Optional[str] = None


# --- Helpers ---------------------------------------------------------------

def _require_auth(request):
    if not request.user.is_authenticated:
        raise HttpError(401, "Auth required")


def _serialize_prefs(prefs: KulturPrefs) -> dict:
    return {
        'default_categories': prefs.default_categories or [],
        'default_moods': prefs.default_moods or [],
        'default_municipality': prefs.default_municipality or '',
    }


# --- Favorites -------------------------------------------------------------

@router.get("/favs/", response=FavIdsOut)
def list_favs(request):
    _require_auth(request)
    ids = list(request.user.kultur_favs.values_list('event_id', flat=True))
    return {'ids': ids}


@router.post("/favs/{event_id}/", response=OkOut)
def add_fav(request, event_id: int):
    _require_auth(request)
    event = get_object_or_404(CulturalEvent, id=event_id)
    EventFavorite.objects.get_or_create(user=request.user, event=event)
    return {'ok': True}


@router.delete("/favs/{event_id}/", response=OkOut)
def remove_fav(request, event_id: int):
    _require_auth(request)
    EventFavorite.objects.filter(user=request.user, event_id=event_id).delete()
    return {'ok': True}


@router.post("/favs/sync/", response=FavIdsOut)
def sync_favs(request, payload: FavSyncIn):
    """Merge a list of event ids (e.g. from localStorage) with the user's DB favs.
    Invalid ids are silently dropped. Returns the resulting full list."""
    _require_auth(request)
    valid_ids = set(
        CulturalEvent.objects.filter(id__in=payload.ids).values_list('id', flat=True)
    )
    existing_ids = set(request.user.kultur_favs.values_list('event_id', flat=True))
    to_create = valid_ids - existing_ids
    if to_create:
        EventFavorite.objects.bulk_create(
            [EventFavorite(user=request.user, event_id=eid) for eid in to_create],
            ignore_conflicts=True,
        )
    final_ids = list(request.user.kultur_favs.values_list('event_id', flat=True))
    return {'ids': final_ids}


# --- Preferences -----------------------------------------------------------

@router.get("/prefs/", response=PrefsOut)
def get_prefs(request):
    _require_auth(request)
    prefs, _ = KulturPrefs.objects.get_or_create(user=request.user)
    return _serialize_prefs(prefs)


@router.patch("/prefs/", response=PrefsOut)
def update_prefs(request, payload: PrefsPatchIn):
    _require_auth(request)
    prefs, _ = KulturPrefs.objects.get_or_create(user=request.user)
    if payload.default_categories is not None:
        prefs.default_categories = payload.default_categories
    if payload.default_moods is not None:
        prefs.default_moods = payload.default_moods
    if payload.default_municipality is not None:
        prefs.default_municipality = payload.default_municipality
    prefs.save()
    return _serialize_prefs(prefs)
