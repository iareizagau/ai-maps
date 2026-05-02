from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from apps.pintxos.models import Restaurant, Dish, DishRating

User = get_user_model()


class Command(BaseCommand):
    help = "Clear all Pintxos data (restaurants, dishes, ratings, or users)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--restaurants",
            action="store_true",
            help="Clear all restaurants and related dishes",
        )
        parser.add_argument(
            "--dishes",
            action="store_true",
            help="Clear all dishes and ratings",
        )
        parser.add_argument(
            "--ratings",
            action="store_true",
            help="Clear all dish ratings",
        )
        parser.add_argument(
            "--users",
            action="store_true",
            help="Clear all users (except superuser)",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Clear everything (restaurants, dishes, ratings, and users)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip confirmation prompt",
        )

    def handle(self, *args, **options):
        if not any([options["restaurants"], options["dishes"], options["ratings"], options["users"], options["all"]]):
            raise CommandError("Specify what to clear: --restaurants, --dishes, --ratings, --users, or --all")

        # Build list of items to delete
        items = []
        counts = {}

        if options["all"] or options["restaurants"]:
            count = Restaurant.objects.count()
            items.append(f"Restaurant objects: {count}")
            counts["restaurants"] = count

        if options["all"] or options["dishes"]:
            count = Dish.objects.count()
            items.append(f"Dish objects: {count}")
            counts["dishes"] = count

        if options["all"] or options["ratings"]:
            count = DishRating.objects.count()
            items.append(f"DishRating objects: {count}")
            counts["ratings"] = count

        if options["all"] or options["users"]:
            count = User.objects.exclude(is_superuser=True).count()
            items.append(f"User objects (non-superuser): {count}")
            counts["users"] = count

        if not items:
            self.stdout.write(self.style.WARNING("Nothing to clear."))
            return

        # Show confirmation
        self.stdout.write(self.style.WARNING("About to delete:"))
        for item in items:
            self.stdout.write(f"  - {item}")

        if not options["force"]:
            confirm = input("\nAre you sure? Type 'yes' to confirm: ")
            if confirm.lower() != "yes":
                self.stdout.write(self.style.ERROR("Cancelled."))
                return

        # Delete data
        if options["all"] or options["restaurants"]:
            Restaurant.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"✓ Deleted {counts.get('restaurants', 0)} restaurants"))

        if options["all"] or options["dishes"]:
            Dish.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"✓ Deleted {counts.get('dishes', 0)} dishes"))

        if options["all"] or options["ratings"]:
            DishRating.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"✓ Deleted {counts.get('ratings', 0)} ratings"))

        if options["all"] or options["users"]:
            User.objects.exclude(is_superuser=True).delete()
            self.stdout.write(self.style.SUCCESS(f"✓ Deleted {counts.get('users', 0)} users"))

        self.stdout.write(self.style.SUCCESS("✓ Clear data completed"))
