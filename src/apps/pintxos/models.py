from django.db import models
from django.contrib.gis.db import models as gis_models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from pgvector.django import VectorField

User = get_user_model()


class BaseModel(models.Model):
    """Base model with timestamps"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class RestaurantQuerySet(models.QuerySet):
    def approved(self):
        return self.filter(approved=True)

    def nearby(self, longitude, latitude, radius_km=5):
        from django.contrib.gis.geos import Point
        from django.contrib.gis.db.models.functions import Distance
        from django.contrib.gis.measure import D
        
        point = Point(float(longitude), float(latitude))
        return self.filter(
            location__distance_lte=(point, D(km=radius_km))
        ).annotate(
            distance=Distance('location', point)
        ).order_by('distance')

    def search(self, query):
        if not query:
            return self
        return self.filter(
            models.Q(name__icontains=query) | 
            models.Q(dishes__name__icontains=query) |
            models.Q(address__icontains=query)
        ).distinct()

    def by_category(self, category_code):
        if not category_code or category_code == 'ALL':
            return self
        return self.filter(dishes__category=category_code).distinct()


class Restaurant(BaseModel):
    objects = RestaurantQuerySet.as_manager()
    """Restaurant/bar where pintxos are served"""
    class Category(models.TextChoices):
        BAR = 'BAR', _('Bar')
        RESTAURANT = 'RESTAURANT', _('Restaurant')
        TXOKO = 'TXOKO', _('Txoko')

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    location = gis_models.PointField(srid=4326)  # EPSG:4326
    address = models.CharField(max_length=300)
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    image_url = models.URLField(blank=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    hours = models.JSONField(default=dict, blank=True)  # {"mon": "10-22", "tue": "10-22", ...}
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    claimed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='claimed_pintxos_venues',
        help_text='Verified owner. Set when a RestaurantClaim is approved.',
    )
    approved = models.BooleanField(default=False)  # Moderación
    avg_rating = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    rating_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def update_rating(self):
        """Recalculate average rating from all dishes' ratings"""
        from django.db.models import Avg
        # We average all DishRatings associated with this restaurant's dishes
        all_ratings = DishRating.objects.filter(dish__restaurant=self)
        if all_ratings.exists():
            stats = all_ratings.aggregate(avg=Avg('rating'), count=models.Count('id'))
            self.avg_rating = stats['avg'] or 0
            self.rating_count = stats['count'] or 0
        else:
            self.avg_rating = 0
            self.rating_count = 0
        self.save(update_fields=['avg_rating', 'rating_count'])


class DishQuerySet(models.QuerySet):
    def approved_restaurants(self):
        return self.filter(restaurant__approved=True)

    def by_category(self, category_code):
        if not category_code:
            return self
        return self.filter(category=category_code)

    def search(self, query):
        if not query:
            return self
        return self.filter(name__icontains=query)


class Dish(BaseModel):
    objects = DishQuerySet.as_manager()
    """Dish/pintxo served at restaurant"""
    class Category(models.TextChoices):
        TORTILLA = 'TORTILLA', _('Tortilla')
        CROQUETAS = 'CROQUETAS', _('Croquetas')
        CALAMARES = 'CALAMARES', _('Calamares')
        COMIDA_MEXICANA = 'COMIDA_MEXICANA', _('Comida Mexicana')
        PATATAS_BRAVAS = 'PATATAS_BRAVAS', _('Patatas Bravas')
        TARTA_QUESO_HORNO = 'TARTA_QUESO_HORNO', _('Tarta de Queso Horno')
        TARTA_QUESO_FRIO = 'TARTA_QUESO_FRIO', _('Tarta de Queso Frío')
        HAMBURGUESA = 'HAMBURGUESA', _('Hamburguesa')
        PIZZA = 'PIZZA', _('Pizza')
        SUSHI = 'SUSHI', _('Sushi')

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='dishes')
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=30, choices=Category.choices)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    image_url = models.URLField(blank=True)
    # embedding = VectorField(dimensions=384, null=True, blank=True)  # TODO: Enable after pgvector setup
    avg_rating = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    rating_count = models.IntegerField(default=0)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='dishes_created')

    class Meta:
        ordering = ['-avg_rating', '-created_at']
        unique_together = ('restaurant', 'name')

    def __str__(self):
        return f"{self.name} @ {self.restaurant.name}"

    def update_rating(self):
        """Recalculate average rating from DishRating entries"""
        ratings = self.ratings.all()
        if ratings.exists():
            self.avg_rating = ratings.aggregate(models.Avg('rating'))['rating__avg'] or 0
            self.rating_count = ratings.count()
        else:
            self.avg_rating = 0
            self.rating_count = 0
        self.save(update_fields=['avg_rating', 'rating_count'])
        self.restaurant.update_rating()


class DishRating(models.Model):
    """User rating for a dish"""
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dish_ratings')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    price = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('dish', 'user')  # One rating per user per dish
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} rated {self.dish.name}: {self.rating}/5"

    def save(self, *args, **kwargs):
        """Update dish rating after saving"""
        super().save(*args, **kwargs)
        self.dish.update_rating()

    def delete(self, *args, **kwargs):
        """Update dish rating after deleting"""
        super().delete(*args, **kwargs)
        self.dish.update_rating()


class DishFavorite(models.Model):
    """User saves a dish as a favourite (heart button)"""
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name='favorites')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dish_favorites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('dish', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} ♥ {self.dish.name}"


class RestaurantClaim(models.Model):
    """
    Ownership claim for a Restaurant. The bar's owner submits a claim, an admin
    verifies (default: phone call to the published number) and approves. On
    approval, Restaurant.claimed_by is set to the claimant.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')
        REVOKED = 'revoked', _('Revoked')

    class Method(models.TextChoices):
        PHONE = 'phone', _('Phone call')
        EMAIL = 'email', _('Domain email')
        DOCUMENT = 'document', _('Document upload')
        OTHER = 'other', _('Other')

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='claims')
    claimant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pintxos_claims')

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    method = models.CharField(max_length=16, choices=Method.choices, default=Method.PHONE)

    evidence = models.TextField(blank=True, help_text=_('Free-text proof: role, contact details, supporting info.'))
    contact_phone = models.CharField(max_length=30, blank=True)
    contact_email = models.EmailField(blank=True)

    admin_notes = models.TextField(blank=True, help_text=_('Internal notes left by the reviewer.'))
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_pintxos_claims',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['restaurant', 'claimant'], name='uniq_restaurant_claimant'),
        ]
        indexes = [models.Index(fields=['status', '-created_at'])]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.claimant.username} -> {self.restaurant.name} ({self.status})"
