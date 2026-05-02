from ninja import Router, Query
from ninja.errors import HttpError
from django.shortcuts import get_object_or_404
from typing import List

from .models import Restaurant, Dish, DishRating, DishFavorite
from .schemas import (
    RestaurantIn, RestaurantOut,
    DishIn, DishOut,
    DishRatingIn, DishRatingOut,
)
from . import services

router = Router()


# ============ HELPERS ============

def _restaurant_to_schema(restaurant: Restaurant) -> dict:
    """Convert Restaurant model to dict for schema (handles PointField)"""
    return {
        'id': restaurant.id,
        'name': restaurant.name,
        'description': restaurant.description,
        'address': restaurant.address,
        'phone': restaurant.phone,
        'website': restaurant.website,
        'image_url': restaurant.image_url,
        'category': restaurant.category,
        'hours': restaurant.hours,
        'approved': restaurant.approved,
        'created_at': restaurant.created_at,
        'created_by_id': restaurant.created_by_id,
        'latitude': restaurant.location.y,
        'longitude': restaurant.location.x,
    }


# ============ RESTAURANTS ============

@router.get("/restaurants/nearby/", response=List[RestaurantOut])
def get_nearby_restaurants(
    request,
    latitude: float = Query(...),
    longitude: float = Query(...),
    radius_km: float = Query(0.1),
):
    """Search restaurants within radius (in km) from coordinates"""
    nearby = Restaurant.objects.approved().nearby(longitude, latitude, radius_km)
    return [_restaurant_to_schema(r) for r in nearby]


@router.get("/restaurants/", response=List[RestaurantOut])
def list_restaurants(request, skip: int = Query(0), limit: int = Query(20)):
    """List all approved restaurants"""
    restaurants = Restaurant.objects.approved()[skip : skip + limit]
    return [_restaurant_to_schema(r) for r in restaurants]


@router.get("/restaurants/{restaurant_id}/", response=RestaurantOut)
def get_restaurant(request, restaurant_id: int):
    """Get restaurant detail"""
    restaurant = get_object_or_404(Restaurant, id=restaurant_id, approved=True)
    return _restaurant_to_schema(restaurant)


@router.post("/restaurants/", response={200: RestaurantOut, 400: dict})
def create_restaurant(request, payload: RestaurantIn):
    """Create new restaurant using service layer"""
    if not request.user.is_authenticated:
        raise HttpError(401, "Se requiere iniciar sesión para crear un bar.")

    try:
        restaurant = services.create_restaurant(
            name=payload.name,
            address=payload.address,
            category=payload.category,
            latitude=payload.latitude,
            longitude=payload.longitude,
            description=payload.description,
            phone=payload.phone,
            website=payload.website,
            image_url=payload.image_url,
            hours=payload.hours,
            created_by=request.user
        )
        return 200, _restaurant_to_schema(restaurant)
    except ValueError as e:
        return 400, {"message": str(e)}


@router.put("/restaurants/{restaurant_id}/", response=RestaurantOut)
def update_restaurant(request, restaurant_id: int, payload: RestaurantIn):
    """Update restaurant using service layer"""
    if not request.user.is_authenticated:
        raise HttpError(401, "Se requiere iniciar sesión.")

    try:
        restaurant = services.update_restaurant(
            restaurant_id,
            user=request.user,
            name=payload.name,
            description=payload.description,
            address=payload.address,
            phone=payload.phone,
            website=payload.website,
            image_url=payload.image_url,
            category=payload.category,
            hours=payload.hours,
            latitude=payload.latitude,
            longitude=payload.longitude
        )
        return _restaurant_to_schema(restaurant)
    except PermissionError as e:
        raise HttpError(403, str(e))


# ============ DISHES ============

@router.get("/restaurants/{restaurant_id}/dishes/", response=List[DishOut])
def list_dishes(request, restaurant_id: int):
    """List dishes for a restaurant"""
    restaurant = get_object_or_404(Restaurant, id=restaurant_id, approved=True)
    return restaurant.dishes.all()


@router.get("/dishes/", response=List[DishOut])
def list_all_dishes(
    request,
    skip: int = Query(0),
    limit: int = Query(20),
    category: str = Query(None),
    restaurant_id: int = Query(None),
):
    """List all dishes with optional filters using QuerySet methods"""
    queryset = Dish.objects.approved_restaurants().by_category(category)

    if restaurant_id:
        queryset = queryset.filter(restaurant_id=restaurant_id)

    return queryset.order_by('-avg_rating')[skip : skip + limit]


@router.get("/dishes/{dish_id}/", response=DishOut)
def get_dish(request, dish_id: int):
    """Get dish detail"""
    dish = get_object_or_404(Dish, id=dish_id)
    return dish


@router.post("/restaurants/{restaurant_id}/dishes/", response=DishOut)
def create_dish(request, restaurant_id: int, payload: DishIn):
    """Create new dish using service layer"""
    if not request.user.is_authenticated:
        raise HttpError(401, "Se requiere iniciar sesión para añadir un pintxo.")

    dish = services.create_dish(
        restaurant_id=restaurant_id,
        name=payload.name,
        category=payload.category,
        description=payload.description,
        price=payload.price,
        image_url=payload.image_url,
        created_by=request.user
    )
    return dish


@router.put("/dishes/{dish_id}/", response=DishOut)
def update_dish(request, dish_id: int, payload: DishIn):
    """Update dish using service layer"""
    if not request.user.is_authenticated:
        raise HttpError(401, "Se requiere iniciar sesión.")

    dish = get_object_or_404(Dish, id=dish_id)

    if dish.created_by != request.user:
        raise HttpError(403, "No tienes permiso para editar este pintxo.")

    dish.name = payload.name
    dish.category = payload.category
    dish.description = payload.description or ""
    dish.price = payload.price
    dish.image_url = payload.image_url or ""
    dish.save()

    return dish


# ============ RATINGS ============

@router.post("/dishes/{dish_id}/rate/", response=DishRatingOut)
def rate_dish(request, dish_id: int, payload: DishRatingIn):
    """Rate a dish using service layer"""
    if not request.user.is_authenticated:
        raise HttpError(401, "Se requiere iniciar sesión para valorar un pintxo.")

    rating = services.rate_dish(
        dish_id=dish_id,
        user=request.user,
        rating_value=payload.rating,
        comment=payload.comment,
        price=payload.price
    )
    return rating


@router.get("/dishes/{dish_id}/ratings/", response=List[DishRatingOut])
def list_dish_ratings(request, dish_id: int, skip: int = Query(0), limit: int = Query(20)):
    """List ratings for a dish"""
    dish = get_object_or_404(Dish, id=dish_id)
    return dish.ratings.all()[skip : skip + limit]


@router.delete("/ratings/{rating_id}/")
def delete_rating(request, rating_id: int):
    """Delete a rating (only owner)"""
    if not request.user.is_authenticated:
        raise HttpError(401, "Se requiere iniciar sesión.")

    rating = get_object_or_404(DishRating, id=rating_id)

    if rating.user != request.user:
        raise HttpError(403, "No tienes permiso para borrar esta valoración.")

    rating.delete()
    return 204, None


# ============ SEARCH (Spatial + Semantic) ============

@router.get("/navigator/", response=List[RestaurantOut])
def list_filtered_restaurants(
    request,
    q: str = Query(None),
    category: str = Query(None),
    latitude: float = Query(None),
    longitude: float = Query(None),
    radius_km: float = Query(5),
    limit: int = Query(20),
):
    """Advanced filtering using custom QuerySet methods"""
    queryset = Restaurant.objects.approved().search(q).by_category(category)

    if latitude is not None and longitude is not None:
        queryset = queryset.nearby(longitude, latitude, radius_km)
    else:
        queryset = queryset.order_by('-created_at')

    return [_restaurant_to_schema(r) for r in queryset[:limit]]


@router.get("/search/")
def search_nearby(
    request,
    q: str = Query(...),
    latitude: float = Query(...),
    longitude: float = Query(...),
    radius_km: float = Query(5),
):
    """Search nearby restaurants and dishes using QuerySet methods"""
    restaurants = Restaurant.objects.approved().nearby(longitude, latitude, radius_km).filter(name__icontains=q)[:10]

    dishes = Dish.objects.approved_restaurants().search(q).select_related('restaurant')
    
    # Custom spatial sort for dishes if needed
    from django.contrib.gis.geos import Point
    from django.contrib.gis.db.models.functions import Distance
    user_point = Point(longitude, latitude)
    dishes = dishes.annotate(
        distance=Distance('restaurant__location', user_point)
    ).order_by('-avg_rating', 'distance')[:10]

    return 200, {
        'restaurants': [_restaurant_to_schema(r) for r in restaurants],
        'dishes': [DishOut.from_orm(d) for d in dishes],
    }


# ============ FAVOURITES ============

@router.post("/dishes/{dish_id}/favourite/")
def toggle_favourite(request, dish_id: int):
    """Toggle favourite (heart) for a dish. Returns {favourited: bool, count: int}"""
    if not request.user.is_authenticated:
        raise HttpError(401, "Se requiere iniciar sesión para guardar favoritos.")

    dish = get_object_or_404(Dish, id=dish_id)
    fav, created = DishFavorite.objects.get_or_create(dish=dish, user=request.user)

    if not created:
        # Already favourited → unfavourite
        fav.delete()
        favourited = False
    else:
        favourited = True

    count = dish.favorites.count()
    return 200, {'favourited': favourited, 'count': count}


@router.get("/dishes/{dish_id}/favourite/")
def get_favourite_status(request, dish_id: int):
    """Get favourite status for current user and total count"""
    dish = get_object_or_404(Dish, id=dish_id)
    favourited = (
        request.user.is_authenticated and
        DishFavorite.objects.filter(dish=dish, user=request.user).exists()
    )
    count = dish.favorites.count()
    return 200, {'favourited': favourited, 'count': count}


@router.get("/favourites/")
def list_my_favourites(request, skip: int = 0, limit: int = 20):
    """List dishes favourited by the current user"""
    if not request.user.is_authenticated:
        raise HttpError(401, "Se requiere iniciar sesión.")

    favs = DishFavorite.objects.filter(user=request.user).select_related(
        'dish', 'dish__restaurant'
    )[skip:skip + limit]

    return 200, [
        {
            'id': f.dish.id,
            'name': f.dish.name,
            'category': f.dish.category,
            'restaurant': f.dish.restaurant.name,
            'restaurant_id': f.dish.restaurant_id,
            'avg_rating': f.dish.avg_rating,
            'image_url': f.dish.image_url,
            'favourited_at': f.created_at,
        }
        for f in favs
    ]
