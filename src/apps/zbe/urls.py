from django.urls import path
from . import views

app_name = 'zbe'

urlpatterns = [
    path('', views.home, name='home'),
    path('save/', views.save_zones, name='save_zones'),
]
