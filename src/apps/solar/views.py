from django.shortcuts import render

def solar_map_view(request):
    """
    Vista principal del Mapa de Potencial Solar 3D.
    """
    context = {
        "title": "Solar 3D - Mapa de Potencial Fotovoltaico",
        "app_slug": "solar"
    }
    return render(request, "solar/map.html", context)
