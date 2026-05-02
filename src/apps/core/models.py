from django.contrib.auth.models import AbstractUser
from django.db import models

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

class AppRegistry(models.Model):
    """
    Central registry for all sub-apps in the ecosystem.
    Defines branding, personality, and features.
    """
    slug = models.SlugField(unique=True, help_text="e.g., 'pintxos', 'sbk'")
    name = models.CharField(max_length=100)
    domain = models.CharField(max_length=255, help_text="e.g., 'pintxos.maps.eus'")
    
    # Branding
    primary_color = models.CharField(max_length=7, default="#f97316", help_text="Hex color")
    secondary_color = models.CharField(max_length=7, default="#84cc16")
    font_family = models.CharField(max_length=100, default="'Inter', sans-serif")
    
    # Hero Content
    hero_title = models.CharField(max_length=200, blank=True)
    hero_subtitle = models.TextField(blank=True)
    hero_image = models.ImageField(upload_to='app_branding/', null=True, blank=True)
    
    # Feature Flags
    has_reviews = models.BooleanField(default=True)
    has_maps = models.BooleanField(default=True)
    has_bookings = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "App Registries"

    def __str__(self):
        return self.name
