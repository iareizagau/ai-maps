from django.urls import path
from ninja import NinjaAPI

from . import views
from .api import router

# NOTE: the NinjaAPI instance is exported and mounted directly in
# `config/urls.py` (NOT inside this `urlpatterns`). Reason: `app_name = 'mubil'`
# below makes `include()` treat every nested path as living under the
# `mubil:` instance namespace. Ninja registers its own namespace
# (`mubil_api`) on `api.urls` and internally calls
# `reverse('mubil_api:openapi-json')` to render the docs page — that lookup
# only succeeds when the namespace is registered at the top level, not nested.
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
    path('advisor/pdf/', views.advisor_pdf, name='advisor_pdf'),
    path('advisor/assist/', views.advisor_assist, name='advisor_assist'),
    path('ask/', views.ask_page, name='ask'),
    path('ask/query/', views.ask_query, name='ask_query'),
    path('route/', views.route_page, name='route'),
    path('route/plan/', views.route_plan, name='route_plan'),
    path('plan/', views.plan_page, name='plan'),
    path('infrastructure/', views.infrastructure_page, name='infrastructure'),
    path('news/', views.news_page, name='news'),
    path('contact/', views.contact_submit, name='contact'),
]
