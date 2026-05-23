from django.urls import path
from . import views

app_name = 'oceania'

urlpatterns = [
    path('', views.home, name='home'),
    path('sources/', views.sources, name='sources'),
    path('api/countries/', views.country_geojson, name='country_geojson'),
    path('api/cyclones/', views.cyclone_geojson, name='cyclone_geojson'),
]
