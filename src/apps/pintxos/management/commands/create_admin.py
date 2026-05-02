from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Create an admin/superuser account"

    def add_arguments(self, parser):
        parser.add_argument("username", type=str, help="Username for the admin account")
        parser.add_argument("email", type=str, help="Email address for the admin account")
        parser.add_argument("password", type=str, help="Password for the admin account")

    def handle(self, *args, **options):
        username = options["username"]
        email = options["email"]
        password = options["password"]

        # Check if user already exists
        if User.objects.filter(username=username).exists():
            raise CommandError(f"User '{username}' already exists")

        # Create superuser
        User.objects.create_superuser(username=username, email=email, password=password)

        self.stdout.write(
            self.style.SUCCESS(f"✓ Created superuser '{username}' with email '{email}'")
        )
