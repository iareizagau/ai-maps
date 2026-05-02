from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Count
from apps.pintxos.models import Restaurant, Dish, DishRating

User = get_user_model()


class Command(BaseCommand):
    help = "Display statistics about Pintxos data"

    def handle(self, *args, **options):
        restaurants = Restaurant.objects.count()
        dishes = Dish.objects.count()
        ratings = DishRating.objects.count()
        users = User.objects.count()

        # Calculate averages
        avg_dishes_per_restaurant = (
            dishes / restaurants if restaurants > 0 else 0
        )
        avg_ratings_per_dish = (
            ratings / dishes if dishes > 0 else 0
        )

        # Get top rated dishes
        top_dishes = Dish.objects.order_by("-avg_rating")[:5]

        # Get restaurants with most dishes
        restaurants_with_dishes = (
            Restaurant.objects.annotate(dish_count=Count("dishes"))
            .order_by("-dish_count")[:5]
        )

        self.stdout.write(self.style.SUCCESS("\n📊 Pintxos.eus Statistics\n"))
        self.stdout.write(f"Total Restaurants: {restaurants}")
        self.stdout.write(f"Total Dishes: {dishes}")
        self.stdout.write(f"Total Ratings: {ratings}")
        self.stdout.write(f"Total Users: {users}")
        self.stdout.write(f"\nAverage dishes per restaurant: {avg_dishes_per_restaurant:.2f}")
        self.stdout.write(f"Average ratings per dish: {avg_ratings_per_dish:.2f}")

        if top_dishes.exists():
            self.stdout.write(self.style.SUCCESS("\n⭐ Top Rated Dishes:"))
            for i, dish in enumerate(top_dishes, 1):
                rating = f"{dish.avg_rating:.2f}" if dish.avg_rating else "No ratings"
                self.stdout.write(f"  {i}. {dish.name} ({rating} stars, {dish.rating_count} votes)")

        if restaurants_with_dishes.exists():
            self.stdout.write(self.style.SUCCESS("\n🏆 Restaurants with Most Dishes:"))
            for i, restaurant in enumerate(restaurants_with_dishes, 1):
                dish_count = restaurant.dish_count or 0
                self.stdout.write(f"  {i}. {restaurant.name} ({dish_count} dishes)")

        self.stdout.write("")
