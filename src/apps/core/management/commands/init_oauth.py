import environ
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from allauth.socialaccount.models import SocialApp


class Command(BaseCommand):
    help = "Create/update the Site and Google SocialApp from env vars (idempotent)."

    def handle(self, *args, **options):
        env = environ.Env()

        site_domain = env('SITE_DOMAIN', default='localhost:8000')
        site_name = env('SITE_NAME', default='Maps Local')
        google_client_id = env('GOOGLE_OAUTH_ID_CLIENTE', default='')
        google_client_secret = env('GOOGLE_OAUTH_SECRET_KEY', default='')

        site, _ = Site.objects.update_or_create(
            id=1,
            defaults={'domain': site_domain, 'name': site_name},
        )
        self.stdout.write(f"Site #{site.id}: {site.domain} ({site.name})")

        if not google_client_id or not google_client_secret:
            self.stdout.write(self.style.WARNING(
                "GOOGLE_OAUTH_ID_CLIENTE / GOOGLE_OAUTH_SECRET_KEY not set; skipping Google SocialApp."
            ))
            return

        app, created = SocialApp.objects.update_or_create(
            provider='google',
            defaults={
                'name': 'Google Login',
                'client_id': google_client_id,
                'secret': google_client_secret,
            },
        )
        app.sites.add(site)
        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Updated'} Google SocialApp and linked to {site.domain}"
        ))
