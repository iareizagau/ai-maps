from django.urls import path
from . import views

app_name = 'kultur'

urlpatterns = [
    path('', views.map_view, name='map'),
    path('api/events.geojson', views.events_geojson, name='events_geojson'),
    path('api/weather.json', views.weather_forecast, name='weather'),
]
