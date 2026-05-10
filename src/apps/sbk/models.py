from django.db import models
from django.contrib.gis.db import models as gis_models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.fields import ArrayField
import uuid

class DanceStyle(models.TextChoices):
    SALSA = 'salsa', 'Salsa'
    BACHATA = 'bachata', 'Bachata'
    KIZOMBA = 'kizomba', 'Kizomba'
    URBAN_KIZ = 'urbankiz', 'Urban Kiz'
    ZOUK = 'zouk', 'Zouk'
    MIXED = 'mixed', 'SBK / Mixed'

class EventType(models.TextChoices):
    FESTIVAL = 'festival', 'Festival / Congress'
    PARTY = 'party', 'Party / Social'
    WORKSHOP = 'workshop', 'Workshop / Bootcamp'

class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, null=True)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='sbk/people/', blank=True, null=True)
    instagram = models.CharField(max_length=100, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')

    class Role(models.TextChoices):
        DJ = 'dj', 'DJ'
        TEACHER = 'teacher', 'Teacher'
        ORGANIZER = 'organizer', 'Organizer'
        DANCER = 'dancer', 'Dancer'
        VIDEOGRAPHER = 'videographer', 'Videographer'

    roles = ArrayField(models.CharField(max_length=20, choices=Role.choices), default=list, blank=True)

    # Claim flow
    claimed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='claimed_profiles')
    is_verified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    goandance_id = models.UUIDField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True)
    description = models.TextField(blank=True)
    short_description = models.TextField(blank=True)
    
    # Recurring events (Phase 2.2)
    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.CharField(max_length=255, blank=True, help_text="iCalendar RRULE")
    
    # Legacy dates (to be moved to occurrences)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    event_type = models.CharField(max_length=50, choices=EventType.choices, default=EventType.FESTIVAL)
    primary_style = models.CharField(max_length=50, choices=DanceStyle.choices, default=DanceStyle.MIXED)
    
    # Location
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    lat = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    lng = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    
    # Media & Links
    image_url = models.URLField(max_length=500, blank=True, null=True)
    poster = models.ImageField(upload_to='sbk/posters/', blank=True, null=True)
    ticket_url = models.URLField(max_length=500, blank=True, null=True)
    ticket_clicks = models.PositiveIntegerField(default=0)
    
    # Trust & Info (Waze approach)
    price_info = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. 10€ with drink")
    atmosphere = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. Chill, Pure Social, Training")
    
    # Cost Estimation
    estimated_pass_price = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    # Relations (Phase 2.1)
    organizer = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name='organized_events')
    teachers = models.ManyToManyField(Person, related_name='teaching_events', blank=True)
    djs = models.ManyToManyField(Person, related_name='dj_events', blank=True)
    artists = models.ManyToManyField(Person, related_name='performing_events', blank=True)
    
    # User Submissions (Waze approach)
    is_user_submitted = models.BooleanField(default=False)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_sbk_events')
    
    # Moderation & Trust
    MODERATION_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    moderation_status = models.CharField(max_length=20, choices=MODERATION_CHOICES, default='pending')
    is_verified = models.BooleanField(default=False)
    report_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.city})"

class EventOccurrence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='occurrences')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    cancelled = models.BooleanField(default=False)
    override_venue = models.CharField(max_length=255, blank=True) # punctual change

    class Meta:
        indexes = [
            models.Index(fields=['event', 'start_date']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['event', 'start_date'], name='uniq_occurrence')
        ]
        ordering = ['start_date']

    def __str__(self):
        return f"{self.event.name} @ {self.start_date}"

class EventReview(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    overall_rating = models.IntegerField(choices=RATING_CHOICES)
    floor_quality = models.IntegerField(choices=RATING_CHOICES, help_text="1: Slippery/Sticky, 5: Perfect wood")
    ac_ventilation = models.IntegerField(choices=RATING_CHOICES, help_text="1: Sauna, 5: Perfect AC")
    gender_ratio = models.IntegerField(choices=RATING_CHOICES, help_text="1: Bad balance, 5: Perfect 50/50")
    music_quality = models.IntegerField(choices=RATING_CHOICES)
    
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('event', 'user')

class UserEventStatus(models.TextChoices):
    INTERESTED = 'interested', 'Interested'
    GOING = 'going', 'Going'
    WENT = 'went', 'Went (Past)'

class UserEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sbk_events')
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    status = models.CharField(max_length=50, choices=UserEventStatus.choices, default=UserEventStatus.INTERESTED)
    
    # For Matchmaking/Social
    looking_for_roommate = models.BooleanField(default=False)
    looking_for_dance_partner = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True, help_text="E.g., 'Have a spare bed in my Airbnb'")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'event')

class DanceProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dance_profile')
    points = models.IntegerField(default=0)
    current_streak = models.IntegerField(default=0)
    max_streak = models.IntegerField(default=0)
    last_checkin_date = models.DateField(null=True, blank=True)
    
    @property
    def level(self):
        return (self.points // 100) + 1

    def get_rank(self):
        if self.points < 100: return "Novato"
        if self.points < 500: return "Bailador Local"
        if self.points < 2000: return "Explorador SBK"
        if self.points < 5000: return "Embajador del Social"
        return "Leyenda del Social"

    def __str__(self):
        return f"Profile of {self.user.username} ({self.points} XP)"

class EventNotice(models.Model):
    CATEGORY_CHOICES = [
        ('partner', '🤝 Buscar Pareja'),
        ('transport', '🚗 Compartir Coche'),
        ('dinner', '🥘 Cena / Quedada'),
        ('other', '✨ Otros'),
    ]
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='notices')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    message = models.TextField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} by {self.user.username}"

class CheckIn(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='checkins')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('event', 'user') # One checkin per event per night (we can reset/clear old ones later)

class VibeReport(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='vibe_reports')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    music_score = models.IntegerField(default=3) # 1-5
    crowd_score = models.IntegerField(default=3) # 1-5 (1=Empty, 5=Packed)
    ac_score = models.IntegerField(default=3) # 1-5 (1=Sauna, 5=Cold)
    created_at = models.DateTimeField(auto_now_add=True)


# ---------------------------------------------------------------------------
# DanceVenue: persistent venues for SBK dancing (academies, social rooms,
# bars with weekly dance nights). Distinct from Event (one-off festivals).
# ---------------------------------------------------------------------------

class DanceVenueType(models.TextChoices):
    ACADEMY = 'academy', _('Academy')
    SOCIAL = 'social', _('Social room')
    BAR = 'bar', _('Bar with dance night')
    MULTI = 'multi', _('Multi-purpose')


class DanceVenue(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    location = gis_models.PointField(srid=4326, null=True, blank=True)
    address = models.CharField(max_length=300)
    city = models.CharField(max_length=100, db_index=True)
    country = models.CharField(max_length=100, default='Euskadi')

    venue_type = models.CharField(max_length=20, choices=DanceVenueType.choices, default=DanceVenueType.MULTI)
    styles = models.JSONField(default=list, blank=True, help_text=_("List of style codes: salsa, bachata, kizomba, ..."))
    weekly_schedule = models.JSONField(default=dict, blank=True, help_text=_('Free-form: e.g. {"mon":{"class":["bachata-19h"]},"wed":{"social":["21h-2h"]}}'))

    website = models.URLField(blank=True)
    instagram = models.CharField(max_length=100, blank=True)
    image_url = models.URLField(max_length=500, blank=True)

    avg_rating = models.FloatField(default=0)
    rating_count = models.IntegerField(default=0)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_dance_venues',
    )
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='claimed_dance_venues',
        help_text=_('Verified owner. Set when a DanceVenueClaim is approved.'),
    )
    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['city', 'venue_type']),
        ]
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.city})"

    def update_rating(self):
        agg = self.ratings.aggregate(avg=models.Avg('overall'), count=models.Count('id'))
        self.avg_rating = agg['avg'] or 0
        self.rating_count = agg['count'] or 0
        self.save(update_fields=['avg_rating', 'rating_count'])


class VenueRating(models.Model):
    venue = models.ForeignKey(DanceVenue, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dance_venue_ratings')
    overall = models.IntegerField()
    floor_quality = models.IntegerField(null=True, blank=True, help_text=_('1: slippery/sticky, 5: perfect'))
    music_quality = models.IntegerField(null=True, blank=True)
    crowd_level = models.IntegerField(null=True, blank=True, help_text=_('1: empty, 5: packed'))
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('venue', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} → {self.venue.name}: {self.overall}/5"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.venue.update_rating()

    def delete(self, *args, **kwargs):
        venue = self.venue
        super().delete(*args, **kwargs)
        venue.update_rating()


class DanceVenueClaim(models.Model):
    """Ownership claim for a DanceVenue. Same flow as pintxos.RestaurantClaim."""

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

    venue = models.ForeignKey(DanceVenue, on_delete=models.CASCADE, related_name='claims')
    claimant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sbk_claims')

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    method = models.CharField(max_length=16, choices=Method.choices, default=Method.PHONE)

    evidence = models.TextField(blank=True, help_text=_('Free-text proof: role, contact details, supporting info.'))
    contact_phone = models.CharField(max_length=30, blank=True)
    contact_email = models.EmailField(blank=True)

    admin_notes = models.TextField(blank=True, help_text=_('Internal notes left by the reviewer.'))
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_dance_venue_claims',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['venue', 'claimant'], name='uniq_dance_venue_claimant'),
        ]
        indexes = [models.Index(fields=['status', '-created_at'])]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.claimant.username} -> {self.venue.name} ({self.status})"
