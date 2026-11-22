from django.urls import path

from . import views

app_name = "quiniela"

urlpatterns = [
    path("", views.index, name="index"),
    path("jornada/nueva/", views.jornada_nueva, name="jornada_nueva"),
    path("jornada/proximos/", views.proximos, name="proximos"),
    path("jornada/<int:pk>/", views.jornada_detalle, name="jornada_detalle"),
    path("seguimiento/", views.seguimiento, name="seguimiento"),
    # Acciones HTMX: devuelven el panel de la jornada.
    path("jornada/<int:pk>/cuotas/", views.actualizar_cuotas, name="actualizar_cuotas"),
    path("jornada/<int:pk>/noticias/", views.actualizar_noticias, name="actualizar_noticias"),
    path("jornada/<int:pk>/generar/", views.generar, name="generar"),
    path("jornada/<int:pk>/sobrescribir/", views.sobrescribir, name="sobrescribir"),
    path("jornada/<int:pk>/pleno/", views.pleno, name="pleno"),
    path("jornada/<int:pk>/explicar/", views.explicar, name="explicar"),
    path("jornada/<int:pk>/confirmar/", views.confirmar, name="confirmar"),
    path("jornada/<int:pk>/resultados/", views.actualizar_resultados, name="actualizar_resultados"),
    path(
        "jornada/<int:pk>/resultado/<int:posicion>/",
        views.resultado_manual,
        name="resultado_manual",
    ),
]
