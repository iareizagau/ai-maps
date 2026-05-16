from django.urls import path
from . import views

urlpatterns = [
    path('', views.map_view, name='map_view'),
    path('mis-rutas/', views.dashboard_view, name='dashboard_view'),
    path('explorar/', views.explore_view, name='explore_view'),
    path('ruta/<int:route_id>/', views.route_detail_view, name='route_detail'),
    path('scout/', views.scout_view, name='scout_view'),
    path('seguir/<int:route_id>/', views.follow_view, name='follow_route'),
    path('crear-desde-fotos/', views.photo_route_view, name='photo_route_view'),
    path('mando-de-operaciones/', views.exploration_view, name='exploration_view'),
]
