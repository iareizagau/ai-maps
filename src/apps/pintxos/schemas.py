from ninja import Schema
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


class RestaurantIn(Schema):
    """Input schema for creating/updating restaurants"""
    name: str
    description: Optional[str] = None
    address: str
    phone: Optional[str] = None
    website: Optional[str] = None
    image_url: Optional[str] = None
    category: str  # 'BAR', 'RESTAURANT', 'TXOKO'
    latitude: float
    longitude: float
    hours: Optional[dict] = None


class RestaurantOut(Schema):
    """Output schema for restaurants"""
    id: int
    name: str
    description: Optional[str]
    address: str
    phone: Optional[str]
    website: Optional[str]
    image_url: Optional[str]
    category: str
    hours: Optional[dict]
    approved: bool
    created_at: datetime
    created_by_id: Optional[int]
    latitude: float
    longitude: float


class DishIn(Schema):
    """Input schema for creating/updating dishes"""
    name: str
    category: str  # 'TORTILLA', 'CROQUETAS', etc.
    description: Optional[str] = None
    price: Optional[Decimal] = None
    image_url: Optional[str] = None


class DishOut(Schema):
    """Output schema for dishes"""
    id: int
    restaurant_id: int
    name: str
    category: str
    description: Optional[str]
    price: Optional[Decimal]
    image_url: Optional[str]
    avg_rating: float
    rating_count: int
    created_at: datetime
    created_by_id: Optional[int]


class DishRatingIn(Schema):
    """Input schema for rating dishes"""
    rating: int  # 1-5
    comment: Optional[str] = None
    price: Optional[Decimal] = None


class DishRatingOut(Schema):
    """Output schema for ratings"""
    id: int
    dish_id: int
    user_id: int
    rating: int
    comment: Optional[str]
    price: Optional[Decimal]
    created_at: datetime
