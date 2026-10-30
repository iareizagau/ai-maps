from django.urls import path

from . import views

app_name = "amenabar"

urlpatterns = [
    path("", views.home, name="home"),
    path("promociones/", views.promociones, name="promociones"),
    path(
        "promociones/<slug:slug>/pois.json",
        views.promocion_pois,
        name="promocion_pois",
    ),
    path("airquality.json", views.airquality, name="airquality"),
    path("match/", views.match_page, name="match"),
    path("match/results/", views.match_results, name="match_results"),
]
