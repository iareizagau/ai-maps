from dataclasses import dataclass

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .models import POI, Promocion
from .services import SUBTIPO_LABELS, nearest_by_category


@dataclass(frozen=True)
class Idea:
    slug: str
    titulo: str
    descripcion: str
    url: str
    estado: str  # LIVE / WIP / IDEA


def _ideas(request) -> list[Idea]:
    return [
        Idea(
            slug="promociones-servicios",
            titulo="Promociones + servicios cercanos",
            descripcion=(
                "Mapa de todas las promociones de Amenabar. Al clicar una, "
                "aparecen los servicios de alrededor (transporte, salud, "
                "comida, deporte…) con círculos de 5' y 15' andando y 15' "
                "en bici. El valor para el comprador: entender en 10 segundos "
                "qué tiene el barrio."
            ),
            url=reverse("amenabar:promociones"),
            estado="LIVE",
        ),
    ]


def home(request):
    return render(
        request,
        "amenabar/home.html",
        {"ideas": _ideas(request)},
    )


def promociones(request):
    """Promociones map page. All data embedded as JSON for Leaflet."""
    qs = Promocion.objects.filter(location__isnull=False)
    data = [
        {
            "id": p.id,
            "slug": p.slug,
            "nombre": p.nombre,
            "ciudad": p.ciudad,
            "estado": p.estado,
            "estado_label": p.get_estado_display(),
            "porcentaje_vendido": p.porcentaje_vendido,
            "nota": p.nota,
            "detail_url": p.detail_url,
            "image_url": p.image_url,
            "lat": p.location.y,
            "lon": p.location.x,
        }
        for p in qs
    ]
    categories = [{"code": c.value, "label": str(c.label)} for c in POI.Categoria]
    # Resolve lazy strings to the active language right now so the dict is
    # JSON-serializable and reflects the user's locale.
    subtipo_labels = {k: str(v) for k, v in SUBTIPO_LABELS.items()}

    return render(
        request,
        "amenabar/promociones.html",
        {
            "promociones_data": data,
            "categories": categories,
            "subtipo_labels": subtipo_labels,
            "estados": [{"code": e.value, "label": str(e.label)} for e in Promocion.Estado],
            "carto_api_key": settings.CARTO_API_KEY,
        },
    )


def promocion_pois(request, slug: str):
    """JSON endpoint hit by the frontend when a promoción marker is clicked."""
    p = get_object_or_404(Promocion, slug=slug)

    # .values() not .only() on the related manager: .only() without the FK
    # makes Django lazy-load promocion_id once per row (N+1).
    pois = POI.objects.filter(promocion=p).values("id", "nombre", "categoria", "subtipo", "location")
    nearest = nearest_by_category(p) if p.location else []
    return JsonResponse(
        {
            "promocion": {
                "slug": p.slug,
                "nombre": p.nombre,
                "lat": p.location.y if p.location else None,
                "lon": p.location.x if p.location else None,
            },
            "pois": [
                {
                    "id": poi["id"],
                    "nombre": poi["nombre"],
                    "categoria": poi["categoria"],
                    "subtipo": poi["subtipo"],
                    "lat": poi["location"].y,
                    "lon": poi["location"].x,
                }
                for poi in pois
            ],
            "nearest": nearest,
        }
    )
