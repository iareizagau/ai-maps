import random
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.contrib.auth import get_user_model
from faker import Faker
from apps.pintxos.models import Restaurant, Dish, DishRating

User = get_user_model()
fake = Faker(['es_ES'])

class Command(BaseCommand):
    help = 'Seeds the database with mock pintxos data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding data...')
        
        # Get or create a superuser for associations
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stdout.write(self.style.ERROR('No superuser found. Please create one first.'))
            return

        # 1. Clear existing data (optional, but good for idempotent testing)
        # DishRating.objects.all().delete()
        # Dish.objects.all().delete()
        # Restaurant.objects.all().delete()

        # 2. Mock Data for Restaurants
        restaurants_data = [
            # Bilbao
            ("El Globo", "Referente de pintxos junto a la Gran Vía.", 43.2631, -2.9348, Restaurant.Category.BAR, "Calle de la Diputación, 8, Bilbao"),
            ("Ledesma 5", "Moderno y vibrante en la mítica calle Ledesma.", 43.2625, -2.9312, Restaurant.Category.RESTAURANT, "Calle Ledesma, 5, Bilbao"),
            ("Gure Toki", "Alta cocina en miniatura en el corazón de la Plaza Nueva.", 43.2592, -2.9234, Restaurant.Category.BAR, "Plaza Nueva, 12, Bilbao"),
            ("Berton", "Tradición y calidad en el Casco Viejo.", 43.2588, -2.9245, Restaurant.Category.BAR, "Jardin Kalea, 11, Bilbao"),
            # Donostia (San Sebastián)
            ("La Viña", "Famoso mundialmente por su tarta de queso.", 43.3242, -1.9839, Restaurant.Category.BAR, "Calle del Treinta y Uno de Agosto, 3, Donostia"),
            ("Gandarias", "Pintxos clásicos de primera calidad.", 43.3241, -1.9842, Restaurant.Category.RESTAURANT, "Calle del Treinta y Uno de Agosto, 23, Donostia"),
            ("Bar Nestor", "La mejor tortilla y chuletón de la ciudad.", 43.3238, -1.9845, Restaurant.Category.BAR, "Arrandegi Kalea, 11, Donostia"),
            ("Borda Berri", "Pintxos calientes creativos y deliciosos.", 43.3235, -1.9838, Restaurant.Category.BAR, "Fermin Calbeton Kalea, 12, Donostia"),
        ]

        # Categories for dishes
        dish_categories = Dish.Category.choices

        # 3. Mock Users for Ratings
        self.stdout.write('Creating mock users...')
        mock_users = []
        for i in range(10):
            username = f"user_{i}_{fake.user_name()}"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': f"{username}@example.com"}
            )
            mock_users.append(user)

        for name, desc, lat, lon, cat, addr in restaurants_data:
            restaurant, created = Restaurant.objects.get_or_create(
                name=name,
                defaults={
                    'description': desc,
                    'location': Point(lon, lat),
                    'address': addr,
                    'category': cat,
                    'approved': True,
                    'created_by': admin_user,
                    'image_url': f"https://picsum.photos/seed/{name.replace(' ', '')}/800/600"
                }
            )
            
            if created:
                self.stdout.write(f'Created restaurant: {name}')
            
            # Create some dishes for each restaurant
            num_dishes = random.randint(3, 6)
            for i in range(num_dishes):
                dish_cat = random.choice(dish_categories)[0]
                dish_name = f"{dish_cat.capitalize()} {fake.word().capitalize()}"
                
                # Special cases for famous places
                if name == "La Viña" and i == 0:
                    dish_name = "Tarta de Queso Horno"
                    dish_cat = Dish.Category.TARTA_QUESO_HORNO
                elif name == "Bar Nestor" and i == 0:
                    dish_name = "Tortilla de Patatas"
                    dish_cat = Dish.Category.TORTILLA

                dish, d_created = Dish.objects.get_or_create(
                    restaurant=restaurant,
                    name=dish_name,
                    defaults={
                        'category': dish_cat,
                        'description': fake.sentence(),
                        'price': random.uniform(2.5, 12.0),
                        'image_url': f"https://picsum.photos/seed/{dish_name.replace(' ', '')}/400/300",
                        'created_by': admin_user
                    }
                )

                if d_created:
                    # Create some ratings
                    num_ratings = random.randint(3, 8)
                    raters = random.sample(mock_users, num_ratings)
                    for user in raters:
                        DishRating.objects.create(
                            dish=dish,
                            user=user,
                            rating=random.randint(3, 5),
                            comment=fake.sentence()
                        )
        
        self.stdout.write(self.style.SUCCESS('Successfully seeded pintxos data and ratings!'))
