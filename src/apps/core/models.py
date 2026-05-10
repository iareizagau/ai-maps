from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

class User(AbstractUser):
    """
    Custom user model for Maps.eus
    """
    phone = models.CharField(max_length=20, blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    def __str__(self):
        return self.username

class PaymentMethod(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_methods')
    provider = models.CharField(max_length=50, default='Stripe')
    last4 = models.CharField(max_length=4)
    brand = models.CharField(max_length=20)  # Visa, Mastercard, etc.
    exp_month = models.IntegerField()
    exp_year = models.IntegerField()
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.brand} **** {self.last4}"

class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following_set')
    followed = models.ForeignKey(User, on_delete=models.CASCADE, related_name='follower_set')
    app_context = models.CharField(max_length=50, db_index=True)  # 'pintxos', 'sbk', etc.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'followed', 'app_context')

    def __str__(self):
        return f"{self.follower} follows {self.followed} in {self.app_context}"

class Subscription(models.Model):
    """
    Per-app subscription tier for a user.

    `app_slug='*'` is a wildcard bundle that overrides per-app subs.
    """
    TIER_FREE = 'free'
    TIER_PLUS = 'plus'
    TIER_PRO = 'pro'
    TIER_CHOICES = [
        (TIER_FREE, 'Free'),
        (TIER_PLUS, 'Plus'),
        (TIER_PRO, 'Pro'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_PAST_DUE = 'past_due'
    STATUS_CANCELED = 'canceled'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PAST_DUE, 'Past due'),
        (STATUS_CANCELED, 'Canceled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    app_slug = models.CharField(max_length=50, db_index=True, help_text="App slug or '*' for the cross-app bundle")
    tier = models.CharField(max_length=16, choices=TIER_CHOICES, default=TIER_FREE)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    stripe_customer_id = models.CharField(max_length=64, blank=True)
    stripe_subscription_id = models.CharField(max_length=64, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'app_slug'], name='uniq_user_app_sub'),
        ]
        indexes = [models.Index(fields=['user', 'status'])]

    def __str__(self):
        return f"{self.user.username} {self.app_slug}/{self.tier} ({self.status})"


class AppRegistry(models.Model):
    """
    Central registry for all sub-apps in the ecosystem.
    Defines branding, personality, and features.
    """
    slug = models.SlugField(unique=True, help_text="e.g., 'pintxos', 'sbk'")
    name = models.CharField(max_length=100)
    tagline = models.CharField(max_length=255, blank=True)
    domain = models.CharField(max_length=255, help_text="e.g., 'pintxos.maps.eus'")
    icon = models.CharField(max_length=50, default="map-pin", help_text="Lucide icon name")
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Show this app in the Home Hero section")
    
    # Branding
    primary_color = models.CharField(max_length=7, default="#f97316", help_text="Hex color")
    secondary_color = models.CharField(max_length=7, default="#84cc16")
    font_family = models.CharField(max_length=100, default="'Inter', sans-serif")
    
    # Hero & SEO Content
    hero_title = models.CharField(max_length=200, blank=True)
    hero_subtitle = models.TextField(blank=True)
    description = models.TextField(blank=True)
    hero_image = models.ImageField(upload_to='app_branding/', null=True, blank=True)
    social_image = models.ImageField(upload_to='apps/social/', blank=True, null=True)
    
    # Feature Flags
    has_reviews = models.BooleanField(default=True)
    has_maps = models.BooleanField(default=True)
    has_bookings = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "App Registries"

    def __str__(self):
        return f"{self.name} ({self.slug})"

    @property
    def get_absolute_url(self):
        """
        Devuelve la URL absoluta dependiendo del entorno.
        En producción (DEBUG=False): Usa el subdominio configurado (ej. https://kultur.maps.eus).
        En desarrollo (DEBUG=True): Usa el enrutamiento por rutas locales (ej. http://localhost:8000/kultur/).
        """
        if settings.DEBUG:
            return f"http://localhost:8000/{self.slug}/"
        return self.domain
