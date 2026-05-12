from django.urls import path
from . import views

app_name = 'sbk'

urlpatterns = [
    path('', views.map_view, name='map'),
    path('api/events/', views.events_json, name='events_json'),
    path('api/venues/', views.venues_json, name='venues_json'),
    path('api/events/<uuid:event_id>/status/', views.toggle_event_status, name='toggle_event_status'),
    path('api/events/<uuid:event_id>/matchmaking/', views.toggle_matchmaking, name='toggle_matchmaking'),
    path('api/events/<uuid:event_id>/community/', views.event_community_api, name='event_community'),
    path('api/events/<uuid:event_id>/review/', views.submit_event_review, name='submit_event_review'),
    path('api/events/submit/', views.submit_local_social, name='submit_local_social'),
    path('api/events/<uuid:event_id>/report/', views.report_event, name='report_event'),
    path('api/events/<uuid:event_id>/notice/', views.submit_event_notice, name='submit_event_notice'),
    path('api/events/<uuid:event_id>/checkin/', views.check_in, name='check_in'),
    path('api/events/<uuid:event_id>/vibe/', views.submit_vibe_report, name='submit_vibe_report'),
    path('pasaporte/', views.passport_view, name='passport'),
    path('go/<uuid:event_id>/', views.ticket_redirect, name='ticket_redirect'),

    # Phase 1 SEO Landings
    path('esta-noche/', views.tonight_view, name='tonight'),
    path('practica/', views.practice_view, name='practice'),
    path('ciudad/<slug:city_slug>/', views.city_view, name='city'),
    
    # Phase 2 SEO Landings
    path('directorio/', views.person_directory_view, name='person_directory'),
    path('persona/<slug:slug>/', views.person_detail_view, name='person_detail'),
    
    # Venue claim + manage
    path('venue/<int:venue_id>/claim/', views.dance_venue_claim, name='dance_venue_claim'),
    path('venue/<int:venue_id>/manage/', views.dance_venue_manage, name='dance_venue_manage'),

    # This MUST be last to avoid capturing literal slugs
    path('<slug:type_slug>/', views.type_view, name='type'),
]
