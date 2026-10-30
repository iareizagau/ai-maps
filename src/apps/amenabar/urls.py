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
]
