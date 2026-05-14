from django.shortcuts import render

def map_view(request):
    """
    Vista principal del planificador de rutas de aventura.
    """
    context = {
        "title": "Adventure Lab - Planificador de Rutas",
        "app_slug": "adventure"
    }
    return render(request, "adventure/map.html", context)
