from datetime import datetime
from decimal import Decimal

from ninja import Schema


class RestaurantIn(Schema):
    """Input schema for creating/updating restaurants"""

    name: str
    description: str | None = None
    address: str
    phone: str | None = None
    website: str | None = None
    image_url: str | None = None
    category: str  # 'BAR', 'RESTAURANT', 'TXOKO'
    latitude: float
    longitude: float
    hours: dict | None = None


class RestaurantOut(Schema):
    """Output schema for restaurants"""

    id: int
    name: str
    description: str | None
    address: str
    phone: str | None
    website: str | None
    image_url: str | None
    category: str
    hours: dict | None
    approved: bool
    created_at: datetime
    created_by_id: int | None
    latitude: float
    longitude: float


class DishIn(Schema):
    """Input schema for creating/updating dishes"""

    name: str
    category: str  # 'TORTILLA', 'CROQUETAS', etc.
    description: str | None = None
    price: Decimal | None = None
    image_url: str | None = None


class DishOut(Schema):
    """Output schema for dishes"""

    id: int
    restaurant_id: int
    name: str
    category: str
    description: str | None
    price: Decimal | None
    image_url: str | None
    avg_rating: float
    rating_count: int
    created_at: datetime
    created_by_id: int | None


class DishRatingIn(Schema):
    """Input schema for rating dishes"""

    rating: int  # 1-5
    comment: str | None = None
    price: Decimal | None = None


class DishRatingOut(Schema):
    """Output schema for ratings"""

    id: int
    dish_id: int
    user_id: int
    rating: int
    comment: str | None
    price: Decimal | None
    created_at: datetime
