from django.urls import path
from ninja import NinjaAPI

from . import views
from .api import router

api = NinjaAPI(
    title='Mubil API',
    description='Sustainable mobility intelligence for Euskal Herria — advisor, ask, route, plan.',
    version='1.0.0',
    urls_namespace='mubil_api',
)
api.add_router('/v1', router)

app_name = 'mubil'

urlpatterns = [
    path('', views.index, name='index'),
    path('advisor/', views.advisor_page, name='advisor'),
    path('advisor/quote/', views.advisor_quote, name='advisor_quote'),
    path('ask/', views.ask_page, name='ask'),
    path('ask/query/', views.ask_query, name='ask_query'),
    path('route/', views.route_page, name='route'),
    path('route/plan/', views.route_plan, name='route_plan'),
    path('plan/', views.plan_page, name='plan'),
    path('api/', api.urls),
]
