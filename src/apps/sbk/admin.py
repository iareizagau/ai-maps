from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Event, DanceVenue, VenueRating, DanceVenueClaim, Person, EventOccurrence


class EventOccurrenceInline(admin.TabularInline):
    model = EventOccurrence
    extra = 1


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'start_date', 'event_type', 'primary_style', 'is_recurring', 'ticket_clicks', 'moderation_status')
    list_filter = ('event_type', 'primary_style', 'is_recurring', 'moderation_status', 'is_verified', 'is_user_submitted')
    search_fields = ('name', 'city', 'country', 'address')
    ordering = ('-ticket_clicks', '-start_date')
    readonly_fields = ('id', 'goandance_id', 'ticket_clicks', 'report_count', 'created_at', 'updated_at')
    date_hierarchy = 'start_date'
    list_per_page = 50
    inlines = [EventOccurrenceInline]
    filter_horizontal = ('teachers', 'djs', 'artists')
    autocomplete_fields = ('organizer',)


@admin.register(DanceVenue)
class DanceVenueAdmin(GISModelAdmin):
    list_display = ('name', 'city', 'venue_type', 'is_verified', 'claimed_by', 'avg_rating', 'rating_count')
    list_filter = ('venue_type', 'city', 'is_verified')
    search_fields = ('name', 'city', 'address', 'description')
    autocomplete_fields = ('created_by', 'claimed_by')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('avg_rating', 'rating_count', 'created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'description', 'venue_type', 'styles', 'is_verified')}),
        ('Location', {'fields': ('location', 'address', 'city', 'country')}),
        ('Schedule & Links', {'fields': ('weekly_schedule', 'website', 'instagram', 'image_url')}),
        ('Ownership', {'fields': ('created_by', 'claimed_by')}),
        ('Stats', {'fields': ('avg_rating', 'rating_count')}),
        ('Metadata', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(VenueRating)
class VenueRatingAdmin(admin.ModelAdmin):
    list_display = ('venue', 'user', 'overall', 'created_at')
    list_filter = ('overall', 'created_at')
    search_fields = ('venue__name', 'user__username', 'comment')
    autocomplete_fields = ('venue', 'user')
    readonly_fields = ('created_at',)


@admin.register(DanceVenueClaim)
class DanceVenueClaimAdmin(admin.ModelAdmin):
    list_display = ('venue', 'claimant', 'status', 'method', 'created_at', 'decided_at', 'reviewed_by')
    list_filter = ('status', 'method', 'created_at')
    search_fields = ('venue__name', 'claimant__username', 'claimant__email', 'evidence', 'admin_notes')
    autocomplete_fields = ('venue', 'claimant', 'reviewed_by')
    readonly_fields = ('created_at', 'decided_at')
    actions = ['approve_claims', 'reject_claims']
    fieldsets = (
        (None, {'fields': ('venue', 'claimant', 'status', 'method')}),
        ('Submitted info', {'fields': ('evidence', 'contact_phone', 'contact_email')}),
        ('Review', {'fields': ('admin_notes', 'reviewed_by', 'decided_at')}),
        ('Metadata', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )

    @admin.action(description=_("Approve selected claims (sets DanceVenue.claimed_by)"))
    def approve_claims(self, request, queryset):
        n = 0
        for claim in queryset.filter(status=DanceVenueClaim.Status.PENDING):
            claim.status = DanceVenueClaim.Status.APPROVED
            claim.decided_at = timezone.now()
            claim.reviewed_by = request.user
            claim.save(update_fields=['status', 'decided_at', 'reviewed_by'])
            claim.venue.claimed_by = claim.claimant
            claim.venue.is_verified = True
            claim.venue.save(update_fields=['claimed_by', 'is_verified'])
            n += 1
        self.message_user(request, _("%(n)d claims approved.") % {'n': n})

    @admin.action(description=_("Reject selected claims"))
    def reject_claims(self, request, queryset):
        n = queryset.filter(status=DanceVenueClaim.Status.PENDING).update(
            status=DanceVenueClaim.Status.REJECTED,
            decided_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, _("%(n)d claims rejected.") % {'n': n})


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'country', 'is_verified', 'claimed_by')
    list_filter = ('roles', 'is_verified', 'country')
    search_fields = ('name', 'city', 'instagram', 'bio')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('claimed_by',)
