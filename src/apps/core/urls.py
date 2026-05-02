from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('profile/', views.profile, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/username/', views.update_username, name='update_username'),
    path('profile/password/', views.update_password, name='update_password'),
    path('profile/payment/add/', views.add_payment_method, name='add_payment_method'),
    path('profile/payment/delete/<int:pk>/', views.delete_payment_method, name='delete_payment_method'),
    path('profile/remove-follow/<int:pk>/', views.remove_follow, name='remove_follow'),
    path('profile/search-users/', views.search_users, name='search_users'),
]
