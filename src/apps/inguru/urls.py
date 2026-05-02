from django.urls import path
from . import views

app_name = 'inguru'

urlpatterns = [
    path('', views.InguruHomeView.as_view(), name='home'),
]
