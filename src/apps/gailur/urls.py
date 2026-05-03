from django.urls import path
from . import views

app_name = 'gailur'

urlpatterns = [
    path('', views.home, name='home'),
    path('crag/<int:pk>/', views.CragDetailView.as_view(), name='crag_detail'),
    path('route/<int:pk>/', views.RouteDetailView.as_view(), name='route_detail'),
]
