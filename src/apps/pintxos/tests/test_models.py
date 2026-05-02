from django.test import TestCase
from django.contrib.gis.geos import Point
from django.contrib.auth import get_user_model
from apps.pintxos.models import Restaurant, Dish, DishRating

User = get_user_model()


class RestaurantModelTests(TestCase):
    """Test Restaurant model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_restaurant(self):
        """Test creating a restaurant"""
        restaurant = Restaurant.objects.create(
            name='Bar Euskaltzale',
            description='Best pintxos in Bilbao',
            address='Calle Ercilla 1, Bilbao',
            phone='+34946154400',
            location=Point(-2.9277, 43.2633),  # lon, lat
            category=Restaurant.Category.BAR,
            created_by=self.user,
        )
        self.assertEqual(restaurant.name, 'Bar Euskaltzale')
        self.assertEqual(restaurant.category, Restaurant.Category.BAR)
        self.assertFalse(restaurant.approved)  # Should be unapproved by default

    def test_restaurant_str(self):
        """Test restaurant string representation"""
        restaurant = Restaurant.objects.create(
            name='Test Bar',
            address='Test Address',
            location=Point(-2.9277, 43.2633),
            category=Restaurant.Category.BAR,
            created_by=self.user,
        )
        self.assertEqual(str(restaurant), 'Test Bar')

    def test_restaurant_location_validation(self):
        """Test that restaurant location is stored with correct SRID"""
        restaurant = Restaurant.objects.create(
            name='Location Test',
            address='Test',
            location=Point(-2.9277, 43.2633),
            category=Restaurant.Category.RESTAURANT,
            created_by=self.user,
        )
        self.assertEqual(restaurant.location.srid, 4326)


class DishModelTests(TestCase):
    """Test Dish model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.restaurant = Restaurant.objects.create(
            name='Test Bar',
            address='Test Address',
            location=Point(-2.9277, 43.2633),
            category=Restaurant.Category.BAR,
            created_by=self.user,
            approved=True,
        )

    def test_create_dish(self):
        """Test creating a dish"""
        dish = Dish.objects.create(
            restaurant=self.restaurant,
            name='Tortilla Española',
            category=Dish.Category.TORTILLA,
            description='Spanish potato omelette',
            price=5.00,
            created_by=self.user,
        )
        self.assertEqual(dish.name, 'Tortilla Española')
        self.assertEqual(dish.category, Dish.Category.TORTILLA)
        self.assertEqual(dish.avg_rating, 0)
        self.assertEqual(dish.rating_count, 0)

    def test_dish_str(self):
        """Test dish string representation"""
        dish = Dish.objects.create(
            restaurant=self.restaurant,
            name='Croquetas',
            category=Dish.Category.CROQUETAS,
            created_by=self.user,
        )
        self.assertEqual(str(dish), 'Croquetas @ Test Bar')

    def test_dish_unique_constraint(self):
        """Test that restaurant + name combination is unique"""
        Dish.objects.create(
            restaurant=self.restaurant,
            name='Tortilla',
            category=Dish.Category.TORTILLA,
            created_by=self.user,
        )
        with self.assertRaises(Exception):
            Dish.objects.create(
                restaurant=self.restaurant,
                name='Tortilla',
                category=Dish.Category.TORTILLA,
                created_by=self.user,
            )

    def test_dish_rating_calculation(self):
        """Test that dish rating is calculated correctly"""
        dish = Dish.objects.create(
            restaurant=self.restaurant,
            name='Test Dish',
            category=Dish.Category.PIZZA,
            created_by=self.user,
        )

        # Create ratings
        user1 = User.objects.create_user('user1', 'u1@test.com', 'pass')
        user2 = User.objects.create_user('user2', 'u2@test.com', 'pass')

        DishRating.objects.create(dish=dish, user=user1, rating=5)
        DishRating.objects.create(dish=dish, user=user2, rating=4)

        # Reload to get updated values
        dish.refresh_from_db()

        self.assertEqual(dish.avg_rating, 4.5)
        self.assertEqual(dish.rating_count, 2)


class DishRatingModelTests(TestCase):
    """Test DishRating model"""

    def setUp(self):
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
            name='Test Dish',
            category=Dish.Category.TORTILLA,
            created_by=self.user1,
        )

    def test_create_rating(self):
        """Test creating a dish rating"""
        rating = DishRating.objects.create(
            dish=self.dish,
            user=self.user1,
            rating=4,
            comment='Very good!',
        )
        self.assertEqual(rating.rating, 4)
        self.assertEqual(rating.comment, 'Very good!')

    def test_rating_unique_constraint(self):
        """Test that each user can only rate a dish once"""
        DishRating.objects.create(dish=self.dish, user=self.user1, rating=5)

        # Trying to create another rating for same user+dish should fail
        with self.assertRaises(Exception):
            DishRating.objects.create(dish=self.dish, user=self.user1, rating=3)

    def test_rating_updates_dish_average(self):
        """Test that creating/deleting rating updates dish average"""
        self.assertEqual(self.dish.avg_rating, 0)

        rating = DishRating.objects.create(dish=self.dish, user=self.user1, rating=5)
        self.dish.refresh_from_db()
        self.assertEqual(self.dish.avg_rating, 5.0)

        rating.delete()
        self.dish.refresh_from_db()
        self.assertEqual(self.dish.avg_rating, 0)

    def test_rating_validation(self):
        """Test rating value validation (1-5)"""
        from django.core.exceptions import ValidationError

        # Invalid rating (0)
        with self.assertRaises(ValidationError):
            rating = DishRating(dish=self.dish, user=self.user1, rating=0)
            rating.full_clean()

        # Invalid rating (6)
        with self.assertRaises(ValidationError):
            rating = DishRating(dish=self.dish, user=self.user1, rating=6)
            rating.full_clean()
