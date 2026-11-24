from django.urls import path

from . import views

app_name = "map30"

urlpatterns = [
    path("", views.index, name="index"),
    # Datos JSON por día (endpoints específicos cuando el día los necesita).
    path("data/day01_points.geojson", views.day01_points_geojson, name="day01_points_geojson"),
    path("data/day04_pintxos.geojson", views.day04_pintxos_geojson, name="day04_pintxos_geojson"),
    path("data/day11_festivales.geojson", views.day11_festivales_geojson, name="day11_festivales_geojson"),
    path("data/day20_hexagons.geojson", views.day20_hexagons_geojson, name="day20_hexagons_geojson"),
    # Detalle genérico: siempre al final para que las rutas específicas ganen.
    path("dia/<int:day>/", views.day_detail, name="day_detail"),
]
