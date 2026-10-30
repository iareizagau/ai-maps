"""
Celery tasks for the Amenabar app.

Pattern: one task per promoción (independent process memory). The dispatcher
spaces them out via `countdown=` so we don't hammer Overpass; each child task
retries with exponential backoff on transient Overpass errors.

Entry points:
  - `fetch_pois_for_promocion(promocion_id)` — the atom.
  - `fetch_all_missing_pois(spacing_s=5)` — enqueue one atom per promoción
    without POIs. Call from a management command or the Django shell.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.db.models import Count, Q

from apps.amenabar import services
from apps.amenabar.models import POI, Promocion

log = logging.getLogger(__name__)


@shared_task(
    name="amenabar.fetch_pois_for_promocion",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=120,  # 2 min, then 4, 8, 16 (capped by max)
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=4,
    # Spaces retries too (countdown only spaces the first attempt). Celery
    # rate limits are per worker; with a single worker this is global.
    rate_limit="4/m",
    acks_late=True,
    time_limit=180,
    soft_time_limit=150,
)
def fetch_pois_for_promocion(self, promocion_id: int) -> dict:
    """Fetch Overpass POIs for one promoción and persist them. Idempotent."""
    try:
        p = Promocion.objects.only("id", "slug", "nombre", "location").get(pk=promocion_id)
    except Promocion.DoesNotExist:
        return {"promocion_id": promocion_id, "status": "missing"}

    if p.location is None:
        return {"promocion_id": promocion_id, "slug": p.slug, "status": "no-location"}

    elements = services.fetch_pois_overpass(p.location.y, p.location.x)
    kept = services.store_pois(p, elements)
    log.info("amenabar.fetch_pois_for_promocion slug=%s kept=%d", p.slug, kept)
    return {"promocion_id": promocion_id, "slug": p.slug, "kept": kept, "status": "ok"}


@shared_task(name="amenabar.fetch_all_missing_pois")
def fetch_all_missing_pois(spacing_s: int = 5, limit: int | None = None) -> dict:
    """Enqueue one `fetch_pois_for_promocion` per promoción without any POI,
    spaced `spacing_s` seconds apart so Overpass never sees a burst.
    """
    qs = (
        Promocion.objects.filter(location__isnull=False)
        .annotate(n_pois=Count("pois"))
        .filter(n_pois=0)
        .order_by("id")
        .values_list("id", flat=True)
    )
    ids = list(qs[:limit] if limit else qs)
    for i, pk in enumerate(ids):
        fetch_pois_for_promocion.apply_async(
            args=[pk],
            countdown=i * spacing_s,
        )
    log.info("amenabar.fetch_all_missing_pois enqueued=%d spacing_s=%d", len(ids), spacing_s)
    return {"enqueued": len(ids), "spacing_s": spacing_s}


@shared_task(name="amenabar.refetch_missing_categories")
def refetch_missing_categories(categories: tuple[str, ...] = ("COMPRAS", "EDUCACION")) -> dict:
    """Re-enqueue promociones that already have POIs but none of `categories`
    (e.g. after adding new Overpass rules). store_pois is idempotent."""
    ids = list(
        Promocion.objects.filter(location__isnull=False)
        .annotate(n_all=Count("pois"), n_new=Count("pois", filter=Q(pois__categoria__in=categories)))
        .filter(n_all__gt=0, n_new=0)
        .values_list("id", flat=True)
    )
    for pk in ids:
        fetch_pois_for_promocion.delay(pk)
    log.info("amenabar.refetch_missing_categories enqueued=%d", len(ids))
    return {"enqueued": len(ids)}


@shared_task(name="amenabar.fetch_pois_summary")
def fetch_pois_summary() -> dict:
    """Count of promociones vs promociones with POIs. Useful for monitoring."""
    total = Promocion.objects.filter(location__isnull=False).count()
    with_pois = Promocion.objects.filter(location__isnull=False).annotate(n=Count("pois")).filter(n__gt=0).count()
    return {
        "total_geocoded": total,
        "with_pois": with_pois,
        "missing_pois": total - with_pois,
        "total_pois": POI.objects.count(),
    }
