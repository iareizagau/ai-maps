from django.urls import path
from ninja import NinjaAPI
from . import views
from .api import router

# Create API instance for pintxos
api = NinjaAPI(
    title="Pintxos API",
    description="Crowdsourced gastro - restaurants and dishes with ratings",
    version="1.0.0",
)

api.add_router("", router)

app_name = 'pintxos'

urlpatterns = [
    # Views
    path('', views.index, name='index'),
    path('comanda/', views.comanda, name='comanda'),
    path('comanda/camarero/', views.comanda_camarero, name='comanda_camarero'),
    path('comanda/manifest.webmanifest', views.comanda_manifest, name='comanda_manifest'),
    path('comanda/sw.js', views.comanda_sw, name='comanda_sw'),
    path('restaurant/<int:restaurant_id>/', views.restaurant_detail, name='restaurant_detail'),
    path('restaurant/create/', views.restaurant_create, name='restaurant_create'),
    path('restaurant/<int:restaurant_id>/edit/', views.restaurant_edit, name='restaurant_edit'),
    path('dish/<int:dish_id>/', views.dish_detail, name='dish_detail'),
    path('dish/<int:dish_id>/rate/', views.dish_rate, name='dish_rate'),
    path('restaurant/<int:restaurant_id>/dish/create/', views.dish_create, name='dish_create'),

    # API
    path('api/', api.urls),
]
