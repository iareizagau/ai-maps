from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from apps.pintxos.models import Restaurant, Dish, DishRating
from decimal import Decimal

User = get_user_model()

# Mock data
RESTAURANTS_DATA = [
    {
        'name': 'Bar Donostia',
        'description': 'Pintxos tradicionales y vinos de la zona',
        'address': 'Calle Mayor 15, Bilbao',
        'phone': '+34944156789',
        'website': 'http://bardopostia.com',
        'category': Restaurant.Category.BAR,
        'location': Point(-2.9277, 43.2633),  # Bilbao
    },
    {
        'name': 'Txuleta de Txoko',
        'description': 'Txoko tradicional vasco con ambiente auténtico',
        'address': 'Plaza Arriaga 2, Bilbao',
        'phone': '+34944161122',
        'website': '',
        'category': Restaurant.Category.TXOKO,
        'location': Point(-2.9316, 43.2558),
    },
    {
        'name': 'Restaurante Etxebarri',
        'description': 'Gastronomía vasca de alto nivel',
        'address': 'Avenida Abandoibarra 4, Bilbao',
        'phone': '+34944239333',
        'website': 'http://etxebarri.com',
        'category': Restaurant.Category.RESTAURANT,
        'location': Point(-2.9370, 43.2640),
    },
    {
        'name': 'Pintxos & Txakoli',
        'description': 'Especialidad en pintxos variados y vinos locales',
        'address': 'Calle Bidebarrieta 12, Bilbao',
        'phone': '+34944153456',
        'website': '',
        'category': Restaurant.Category.BAR,
        'location': Point(-2.9240, 43.2650),
    },
    {
        'name': 'Casa Rubio',
        'description': 'Clásico de Bilbao, pintxos desde 1950',
        'address': 'Calle Fernández del Campo 8, Bilbao',
        'phone': '+34944234567',
        'website': 'http://casarubio.com',
        'category': Restaurant.Category.BAR,
        'location': Point(-2.9210, 43.2680),
    },
]

DISHES_DATA = [
    {'name': 'Tortilla Española', 'category': Dish.Category.TORTILLA, 'price': Decimal('3.50'), 'description': 'Tortilla de papas con cebolla'},
    {'name': 'Tortilla de Bacalao', 'category': Dish.Category.TORTILLA, 'price': Decimal('4.50'), 'description': 'Tortilla con bacalao desmenuzado'},
    {'name': 'Croquetas de Jamón', 'category': Dish.Category.CROQUETAS, 'price': Decimal('2.50'), 'description': 'Croquetas caseras de jamón ibérico'},
    {'name': 'Croquetas de Setas', 'category': Dish.Category.CROQUETAS, 'price': Decimal('2.50'), 'description': 'Croquetas de setas de temporada'},
    {'name': 'Croquetas de Bacalao', 'category': Dish.Category.CROQUETAS, 'price': Decimal('3.00'), 'description': 'Croquetas de bacalao desalado'},
    {'name': 'Calamares a la Romana', 'category': Dish.Category.CALAMARES, 'price': Decimal('4.00'), 'description': 'Calamares frescos rebozados'},
    {'name': 'Calamares en su Tinta', 'category': Dish.Category.CALAMARES, 'price': Decimal('5.00'), 'description': 'Calamares en tinta de calamar'},
    {'name': 'Taco de Carnitas', 'category': Dish.Category.COMIDA_MEXICANA, 'price': Decimal('3.50'), 'description': 'Taco con carnitas desmenuzadas'},
    {'name': 'Quesadilla Vegetal', 'category': Dish.Category.COMIDA_MEXICANA, 'price': Decimal('3.00'), 'description': 'Quesadilla con queso fundido y verduras'},
    {'name': 'Patatas Bravas', 'category': Dish.Category.PATATAS_BRAVAS, 'price': Decimal('2.50'), 'description': 'Patatas fritas con salsa brava y alioli'},
    {'name': 'Tarta de Queso Horno', 'category': Dish.Category.TARTA_QUESO_HORNO, 'price': Decimal('4.00'), 'description': 'Tarta de queso al horno estilo NY'},
    {'name': 'Tarta de Queso Frío', 'category': Dish.Category.TARTA_QUESO_FRIO, 'price': Decimal('3.50'), 'description': 'Tarta de queso frío con mermelada'},
    {'name': 'Hamburguesa Txuleta', 'category': Dish.Category.HAMBURGUESA, 'price': Decimal('5.50'), 'description': 'Hamburguesa con carne de txuleta vasca'},
    {'name': 'Hamburguesa Completa', 'category': Dish.Category.HAMBURGUESA, 'price': Decimal('4.50'), 'description': 'Hamburguesa con lechuga, tomate y cebolla'},
    {'name': 'Pizza Margherita', 'category': Dish.Category.PIZZA, 'price': Decimal('4.00'), 'description': 'Pizza con tomate, mozzarella y albahaca'},
    {'name': 'Pizza Carnívora', 'category': Dish.Category.PIZZA, 'price': Decimal('6.00'), 'description': 'Pizza con jamón, tocino y salchicha'},
    {'name': 'Sushi Variado', 'category': Dish.Category.SUSHI, 'price': Decimal('5.50'), 'description': 'Surtido de sushi fresco'},
    {'name': 'Sushi Tempura', 'category': Dish.Category.SUSHI, 'price': Decimal('6.00'), 'description': 'Sushi tempura con camarones'},
]

RATINGS = [
    (5, 'Excelente, muy bueno'),
    (5, 'Me encantó'),
    (4, 'Muy bueno'),
    (4, 'Bueno'),
    (5, 'Delicioso'),
    (3, 'Está bien'),
]


class Command(BaseCommand):
    help = 'Seed mock data for Pintxos app'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Creating mock data...'))

        # Get or create test user
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={
                'email': 'test@pintxos.eus',
                'first_name': 'Test',
                'last_name': 'User',
            }
        )
        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write(self.style.SUCCESS(f'✓ Created test user: {user.username}'))
        else:
            self.stdout.write(self.style.WARNING(f'✓ Test user already exists: {user.username}'))

        # Create restaurants
        restaurants = []
        for restaurant_data in RESTAURANTS_DATA:
            restaurant, created = Restaurant.objects.get_or_create(
                name=restaurant_data['name'],
                defaults={
                    **restaurant_data,
                    'created_by': user,
                    'approved': True,
                }
            )
            restaurants.append(restaurant)
            if created:
                self.stdout.write(self.style.SUCCESS(f'✓ Created restaurant: {restaurant.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'✓ Restaurant already exists: {restaurant.name}'))

        # Create dishes
        dishes_created = 0
        for restaurant in restaurants:
            # Assign 3-5 random dishes to each restaurant
            import random
            selected_dishes = random.sample(DISHES_DATA, k=random.randint(3, 5))

            for dish_data in selected_dishes:
                dish, created = Dish.objects.get_or_create(
                    restaurant=restaurant,
                    name=dish_data['name'],
                    defaults={
                        'category': dish_data['category'],
                        'price': dish_data['price'],
                        'description': dish_data['description'],
                        'created_by': user,
                    }
                )
                if created:
                    dishes_created += 1

                    # Add some random ratings
                    import random
                    num_ratings = random.randint(2, 6)
                    for i in range(num_ratings):
                        rating_value, comment = random.choice(RATINGS)
                        rating_user, _ = User.objects.get_or_create(
                            username=f'user_{restaurant.id}_{dish.id}_{i}',
                            defaults={'email': f'user_{restaurant.id}_{dish.id}_{i}@pintxos.eus'}
                        )
                        DishRating.objects.get_or_create(
                            dish=dish,
                            user=rating_user,
                            defaults={'rating': rating_value, 'comment': comment}
                        )

        self.stdout.write(self.style.SUCCESS(f'✓ Created {dishes_created} dishes'))

        self.stdout.write(self.style.SUCCESS('\n✅ Mock data seeded successfully!'))
        self.stdout.write(self.style.WARNING('\nTest credentials:'))
        self.stdout.write(self.style.WARNING('  Username: testuser'))
        self.stdout.write(self.style.WARNING('  Password: testpass123'))
