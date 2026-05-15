from django.urls import path
from . import views

urlpatterns = [
    path('', views.map_view, name='map_view'),
    path('mis-rutas/', views.dashboard_view, name='dashboard_view'),
    path('explorar/', views.explore_view, name='explore_view'),
    path('ruta/<int:route_id>/', views.route_detail_view, name='route_detail'),
]
