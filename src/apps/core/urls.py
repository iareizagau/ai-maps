from django.urls import path
from . import views, account_views

urlpatterns = [
    path('', views.home, name='home'),

    # Legacy /profile/ — kept working during the /account/ migration.
    path('profile/', views.profile, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/username/', views.update_username, name='update_username'),
    path('profile/password/', views.update_password, name='update_password'),
    path('profile/payment/add/', views.add_payment_method, name='add_payment_method'),
    path('profile/payment/delete/<int:pk>/', views.delete_payment_method, name='delete_payment_method'),
    path('profile/remove-follow/<int:pk>/', views.remove_follow, name='remove_follow'),
    path('profile/search-users/', views.search_users, name='search_users'),

    # Unified /account/ area.
    path('account/', account_views.account_root, name='account_root'),
    path('account/identity/', account_views.account_identity, name='account_identity'),
    path('account/security/', account_views.account_security, name='account_security'),
    path('account/social/', account_views.account_social, name='account_social'),
    path('account/billing/', account_views.account_billing, name='account_billing'),
    path('account/apps/', account_views.account_apps, name='account_apps'),
    path('account/apps/<slug:slug>/', account_views.account_app_panel, name='account_app_panel'),
    path('account/privacy/', account_views.account_privacy, name='account_privacy'),
]
