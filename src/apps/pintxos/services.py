from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import Restaurant, Dish, DishRating

def create_restaurant(*, name, address, category, location=None, latitude=None, longitude=None, created_by=None, **extra_fields):
    """
    Creates a restaurant with a proximity check to avoid duplicates.
    """
    if location is None and (latitude is not None and longitude is not None):
        location = Point(float(longitude), float(latitude))
    
    # Proximity check: same name within 50 meters
    existing = Restaurant.objects.filter(
        name__iexact=name,
        location__distance_lte=(location, D(m=50))
    ).first()

    if existing:
        raise ValueError(f"El restaurante '{name}' ya existe en esta ubicación o muy cerca.")

    return Restaurant.objects.create(
        name=name,
        address=address,
        category=category,
        location=location,
        created_by=created_by,
        approved=False, # Requires moderation
        **extra_fields
    )

def update_restaurant(restaurant_id, *, user, **data):
    """
    Updates a restaurant checking for ownership.
    """
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    
    if restaurant.created_by != user and not user.is_staff:
        raise PermissionError("No tienes permiso para editar este bar.")

    if 'latitude' in data and 'longitude' in data:
        data['location'] = Point(float(data.pop('longitude')), float(data.pop('latitude')))
    
    for attr, value in data.items():
        setattr(restaurant, attr, value)
    
    restaurant.save()
    return restaurant

def create_dish(*, restaurant_id, name, category, created_by, **extra_fields):
    """
    Creates a new dish for a restaurant.
    """
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    return Dish.objects.create(
        restaurant=restaurant,
        name=name,
        category=category,
        created_by=created_by,
        **extra_fields
    )

@transaction.atomic
def rate_dish(*, dish_id, user, rating_value, comment="", price=None):
    """
    Rates a dish and updates the dish's current price.
    """
    dish = get_object_or_404(Dish, id=dish_id)
    
    rating, created = DishRating.objects.update_or_create(
        dish=dish,
        user=user,
        defaults={
            'rating': rating_value,
            'comment': comment,
            'price': price,
        }
    )

    if price:
        dish.price = price
        dish.save(update_fields=['price'])
    
    # Model's save() method handles dish.update_rating()
    return rating
