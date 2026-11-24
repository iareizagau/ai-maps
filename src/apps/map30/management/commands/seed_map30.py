"""Idempotent seed para las 30 entradas del #30DayMapChallenge 2026.

Uso:
    docker compose exec web python manage.py seed_map30
    docker compose exec web python manage.py seed_map30 --publish-past

Con `--publish-past`, marca como `published` las entradas cuya fecha ya pasó.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from django.core.management.base import BaseCommand

from apps.map30.models import MapEntry


@dataclass(frozen=True)
class Seed:
    day: int
    slug: str
    name: str
    title: str
    blurb: str
    accent: str  # #RRGGBB característico del día
    glyph: str  # Símbolo o emoji corto (1–2 chars visuales)
    library: str = MapEntry.Library.MAPLIBRE
    basemap: str = MapEntry.Basemap.VOYAGER


SEEDS: list[Seed] = [
    Seed(1, "points", "Points",
         "Puntos de recarga eléctrica en Euskal Herria",
         "Cada punto es un cargador público. Color por potencia (kW), tamaño por densidad local.",
         accent="#3b82f6", glyph="●"),
    Seed(2, "lines", "Lines",
         "Red de bidegorris de Gipuzkoa",
         "Vías ciclables conectadas, extraídas de OpenStreetMap.",
         accent="#059669", glyph="╱"),
    Seed(3, "polygons", "Polygons",
         "Concejos y municipios de Álava",
         "El entramado administrativo más fino del País Vasco: cuadrillas, municipios y concejos.",
         accent="#d97706", glyph="⬟"),
    Seed(4, "clusters", "Clusters",
         "Clústeres de pintxos en la parte vieja de Donostia",
         "Agrupamiento automático de bares por proximidad.",
         accent="#ef4444", glyph="✦"),
    Seed(5, "sight", "Senses: Sight",
         "Viewshed desde Aizkorri",
         "Lo que se ve y lo que no desde la cumbre, calculado sobre un DEM de 25 m.",
         accent="#f97316", glyph="◉",
         basemap=MapEntry.Basemap.POSITRON),
    Seed(6, "vintage", "Vintage",
         "Euskal Herria estilo 1875",
         "Mapa en tono sepia con tipografía serif, inspirado en los grabados del XIX.",
         accent="#92400e", glyph="⚓",
         basemap=MapEntry.Basemap.NONE),
    Seed(7, "ten_minute", "10 minute map",
         "10 minutos: catedrales y colegiatas de Euskal Herria",
         "Una sola capa, un solo estilo. Hecho a contrarreloj.",
         accent="#475569", glyph="⏱"),
    Seed(8, "utopia", "Utopia",
         "Utopía 2040: red completa de bidegorris en Euskal Herria",
         "Trazado especulativo que conecta las siete capitales sin discontinuidades.",
         accent="#10b981", glyph="✤"),
    Seed(9, "urban_rural", "Urban-rural",
         "Densidad de población: urbano vs. rural",
         "Coropleta por municipio con la densidad del último padrón del INE.",
         accent="#7e22ce", glyph="▓"),
    Seed(10, "prompting_only", "Prompting only",
          "Prompt-only: mapa generado íntegramente por IA",
          "Este mapa y su copy fueron producidos sin editar una sola línea a mano.",
          accent="#facc15", glyph="🤖"),
    Seed(11, "sound", "Senses: Sound",
          "Paisaje sonoro: festivales de música 2026",
          "Cada burbuja es un festival; el radio aproxima su aforo e intensidad acústica.",
          accent="#f472b6", glyph="♪",
          basemap=MapEntry.Basemap.DARK_MATTER),
    Seed(12, "power", "Power",
          "Red eléctrica + instalaciones solares residenciales",
          "Subestaciones, líneas de alta tensión y autoconsumo fotovoltaico declarado.",
          accent="#eab308", glyph="⚡"),
    Seed(13, "interactions", "Interactions",
          "Interacciones: pulsa cualquier concejo",
          "Mapa coreografiado — cada clic abre un panel con los indicadores del concejo.",
          accent="#4f46e5", glyph="◎",
          library=MapEntry.Library.LEAFLET),
    Seed(14, "borgesian", "Borgesian map",
          "Borges 1:1 — Donostia a escala real",
          "Un mapa en el que un metro del plano es un metro del territorio. Zoom infinito.",
          accent="#dc2626", glyph="∞"),
    Seed(15, "inside_out", "Inside out",
          "Inside out: el Cantábrico es tierra",
          "Inversión topológica. El mar se dibuja como continente y Euskal Herria como golfo.",
          accent="#06b6d4", glyph="⇋"),
    Seed(16, "collaborative", "Collaborative map",
          "Colaborativo: contribuciones abiertas",
          "Añade tu propio punto. Los datos viven mientras alguien escriba.",
          accent="#1e40af", glyph="⧉",
          library=MapEntry.Library.LEAFLET),
    Seed(17, "light_dark", "Light & dark",
          "Contaminación lumínica nocturna (VIIRS)",
          "Radiancia nocturna 2024, coloreada por intensidad. ¿Dónde se ven las estrellas?",
          accent="#fbbf24", glyph="◐",
          basemap=MapEntry.Basemap.DARK_MATTER),
    Seed(18, "null", "NULL",
          "NULL",
          "El mapa que no está. Un homenaje a los vacíos del dato.",
          accent="#64748b", glyph="∅",
          library=MapEntry.Library.STATIC,
          basemap=MapEntry.Basemap.NONE),
    Seed(19, "smell", "Senses: Smell",
          "Sidrerías, asadores y lonjas: un mapa oloroso",
          "Tres capas superpuestas con olores característicos de Euskal Herria.",
          accent="#f59e0b", glyph="❀"),
    Seed(20, "hexagons", "Hexagons",
          "Hexágonos H3: densidad de recargas EV",
          "Agrupación H3 a resolución 7. Los hexágonos son las mejores celdas.",
          accent="#8b5cf6", glyph="⬢"),
    Seed(21, "osm", "OpenStreetMap",
          "OpenStreetMap: mis ediciones del mes",
          "Diff de cambios subidos a OSM durante noviembre de 2026.",
          accent="#15803d", glyph="◈"),
    Seed(22, "projections", "Projections",
          "Proyecciones: Euskal Herria vista de siete maneras",
          "Mercator, Robinson, Peters, ortográfica, estereográfica, Van der Grinten y azimutal.",
          accent="#0ea5e9", glyph="⊕"),
    Seed(23, "taste", "Senses: Taste",
          "Ruta del gusto: pintxo + txakoli + sidra",
          "Tres capas con las denominaciones y bares emblemáticos.",
          accent="#be123c", glyph="♁"),
    Seed(24, "network", "Network",
          "Red de transporte público: Euskotren + Bizkaibus + Lurraldebus",
          "Grafo completo del transporte público a partir de los GTFS oficiales.",
          accent="#1d4ed8", glyph="⚭"),
    Seed(25, "is_this_a_map", "Is this a map?",
          "¿Esto es un mapa? Euskal Herria reducida a tipografía",
          "Cada municipio es sólo su nombre; sin basemap, sin fronteras, sin ejes.",
          accent="#334155", glyph="✎",
          library=MapEntry.Library.STATIC,
          basemap=MapEntry.Basemap.NONE),
    Seed(26, "water", "Water",
          "Agua: ríos, embalses y costa",
          "Toda la red hidrográfica, con embalses dimensionados por capacidad.",
          accent="#0369a1", glyph="≋",
          basemap=MapEntry.Basemap.POSITRON),
    Seed(27, "new_tool", "New tool",
          "Nueva herramienta: PMTiles + MapLibre",
          "Probamos PMTiles para servir los municipios sin backend de teselas.",
          accent="#ea580c", glyph="⚒"),
    Seed(28, "feeling", "Senses: Feeling",
          "Mapa emocional: sentimientos en reseñas de lugares",
          "Análisis de sentimiento en reseñas públicas, promediado por zona.",
          accent="#ec4899", glyph="♡"),
    Seed(29, "raster", "Raster",
          "Raster: sombreado del relieve de los Pirineos vascos",
          "Hillshade sobre un DEM de 25 m, combinado con una paleta hipsométrica.",
          accent="#78350f", glyph="▦"),
    Seed(30, "pen_paper", "Pen & paper",
          "Papel y boli: un mapa dibujado a mano",
          "El cierre del challenge: foto de un mapa analógico escaneado.",
          accent="#b45309", glyph="✎",
          library=MapEntry.Library.STATIC,
          basemap=MapEntry.Basemap.NONE),
]


class Command(BaseCommand):
    help = "Siembra las 30 entradas del #30DayMapChallenge de noviembre 2026."

    def add_arguments(self, parser):
        parser.add_argument(
            "--publish-past",
            action="store_true",
            help="Marca como publicadas las entradas cuya fecha ya pasó.",
        )

    def handle(self, *args, **opts):
        publish_past = opts["publish_past"]
        today = date.today()
        created = updated = 0

        for s in SEEDS:
            entry_date = date(2026, 11, s.day)
            defaults = {
                "date": entry_date,
                "category_slug": s.slug,
                "category_name": s.name,
                "title": s.title,
                "blurb": s.blurb,
                "library": s.library,
                "basemap": s.basemap,
            }
            if publish_past and entry_date <= today:
                defaults["status"] = MapEntry.Status.PUBLISHED
                defaults["published_at"] = datetime.combine(
                    entry_date, datetime.min.time(), tzinfo=timezone.utc
                )

            obj, was_created = MapEntry.objects.update_or_create(
                day=s.day, defaults=defaults
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"map30: {created} creadas, {updated} actualizadas.")
        )
