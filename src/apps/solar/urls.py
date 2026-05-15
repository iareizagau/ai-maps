from django.urls import path
from . import views

app_name = 'solar'

urlpatterns = [
    path('', views.solar_map_view, name='map_view'),
]
