from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from apps.pintxos.models import Restaurant, Dish, DishRating
import json

User = get_user_model()


class RestaurantAPITests(TestCase):
    """Test Restaurant API endpoints"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass')
        self.restaurant = Restaurant.objects.create(
            name='Test Bar',
            address='Test Address',
            location=Point(-2.9277, 43.2633),
            category=Restaurant.Category.BAR,
            created_by=self.user,
            approved=True,
        )

    def test_list_restaurants(self):
        """Test GET /api/restaurants/"""
        response = self.client.get('/api/restaurants/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], 'Test Bar')

    def test_get_restaurant_detail(self):
        """Test GET /api/restaurants/{id}/"""
        response = self.client.get(f'/api/restaurants/{self.restaurant.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'Test Bar')

    def test_create_restaurant_requires_auth(self):
        """Test POST /api/restaurants/ requires authentication"""
        response = self.client.post('/api/restaurants/', {
            'name': 'New Bar',
            'address': 'New Address',
            'latitude': 43.2633,
            'longitude': -2.9277,
            'category': 'BAR',
        })
        self.assertEqual(response.status_code, 401)

    def test_create_restaurant_authenticated(self):
        """Test POST /api/restaurants/ with authenticated user"""
        self.client.login(username='testuser', password='pass')
        response = self.client.post('/api/restaurants/', {
            'name': 'New Bar',
            'address': 'New Address',
            'latitude': 43.2633,
            'longitude': -2.9277,
            'category': 'RESTAURANT',
        }, content_type='application/json')

        # API endpoint returns 201 on creation
        self.assertIn(response.status_code, [200, 201])


class DishAPITests(TestCase):
    """Test Dish API endpoints"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass')
        self.restaurant = Restaurant.objects.create(
            name='Test Bar',
            address='Test Address',
            location=Point(-2.9277, 43.2633),
            category=Restaurant.Category.BAR,
            created_by=self.user,
            approved=True,
        )
        self.dish = Dish.objects.create(
            restaurant=self.restaurant,
            name='Tortilla',
            category=Dish.Category.TORTILLA,
            created_by=self.user,
        )

    def test_list_dishes_by_restaurant(self):
        """Test GET /api/restaurants/{id}/dishes/"""
        response = self.client.get(f'/api/restaurants/{self.restaurant.id}/dishes/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], 'Tortilla')

    def test_list_all_dishes(self):
        """Test GET /api/dishes/"""
        response = self.client.get('/api/dishes/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)

    def test_list_dishes_filter_by_category(self):
        """Test GET /api/dishes/?category=TORTILLA"""
        response = self.client.get('/api/dishes/?category=TORTILLA')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['category'], 'TORTILLA')

    def test_get_dish_detail(self):
        """Test GET /api/dishes/{id}/"""
        response = self.client.get(f'/api/dishes/{self.dish.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'Tortilla')

    def test_create_dish_requires_auth(self):
        """Test POST /api/restaurants/{id}/dishes/ requires auth"""
        response = self.client.post(f'/api/restaurants/{self.restaurant.id}/dishes/', {
            'name': 'Croquetas',
            'category': 'CROQUETAS',
        })
        self.assertEqual(response.status_code, 401)


class DishRatingAPITests(TestCase):
    """Test DishRating API endpoints"""

    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user('user1', 'u1@test.com', 'pass')
        self.user2 = User.objects.create_user('user2', 'u2@test.com', 'pass')
        self.restaurant = Restaurant.objects.create(
            name='Test Bar',
            address='Test Address',
            location=Point(-2.9277, 43.2633),
            category=Restaurant.Category.BAR,
            created_by=self.user1,
            approved=True,
        )
        self.dish = Dish.objects.create(
            restaurant=self.restaurant,
            name='Tortilla',
            category=Dish.Category.TORTILLA,
            created_by=self.user1,
        )

    def test_rate_dish_requires_auth(self):
        """Test POST /api/dishes/{id}/rate/ requires auth"""
        response = self.client.post(f'/api/dishes/{self.dish.id}/rate/', {
            'rating': 5,
        })
        self.assertEqual(response.status_code, 401)

    def test_rate_dish_authenticated(self):
        """Test POST /api/dishes/{id}/rate/ with authenticated user"""
        self.client.login(username='user1', password='pass')
        response = self.client.post(f'/api/dishes/{self.dish.id}/rate/', {
            'rating': 5,
            'comment': 'Great!',
        }, content_type='application/json')

        self.assertIn(response.status_code, [200, 201])

        # Verify rating was created
        rating = DishRating.objects.get(dish=self.dish, user=self.user1)
        self.assertEqual(rating.rating, 5)
        self.assertEqual(rating.comment, 'Great!')

    def test_list_ratings(self):
        """Test GET /api/dishes/{id}/ratings/"""
        DishRating.objects.create(dish=self.dish, user=self.user1, rating=5)
        DishRating.objects.create(dish=self.dish, user=self.user2, rating=4)

        response = self.client.get(f'/api/dishes/{self.dish.id}/ratings/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)


class SearchAPITests(TestCase):
    """Test spatial search API"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass')

        # Create restaurant in Bilbao
        self.restaurant = Restaurant.objects.create(
            name='Pintxos de Bilbao',
            address='Bilbao',
            location=Point(-2.9277, 43.2633),
            category=Restaurant.Category.BAR,
            created_by=self.user,
            approved=True,
        )

        # Create dish
        self.dish = Dish.objects.create(
            restaurant=self.restaurant,
            name='Tortilla',
            category=Dish.Category.TORTILLA,
            created_by=self.user,
        )

    def test_search_by_name(self):
        """Test search by restaurant/dish name"""
        # Search for 'Tortilla' within 5km of Bilbao
        response = self.client.get('/api/search/', {
            'q': 'Tortilla',
            'latitude': 43.2633,
            'longitude': -2.9277,
            'radius_km': 5,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('dishes', data)
        self.assertEqual(len(data['dishes']), 1)

    def test_search_restaurant_by_name(self):
        """Test search for restaurant by name"""
        response = self.client.get('/api/search/', {
            'q': 'Pintxos',
            'latitude': 43.2633,
            'longitude': -2.9277,
            'radius_km': 5,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('restaurants', data)
        self.assertEqual(len(data['restaurants']), 1)
