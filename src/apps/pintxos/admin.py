from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Restaurant, Dish, DishRating, DishFavorite, RestaurantClaim


@admin.register(Restaurant)
class RestaurantAdmin(GISModelAdmin):
    list_display = ('name', 'category', 'address', 'approved', 'claimed_by', 'avg_rating', 'rating_count')
    list_filter = ('category', 'approved', 'created_at')
    search_fields = ('name', 'address', 'description')
    autocomplete_fields = ('created_by', 'claimed_by')
    readonly_fields = ('avg_rating', 'rating_count', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'category', 'approved')
        }),
        ('Location', {
            'fields': ('location', 'address')
        }),
        ('Contact & Info', {
            'fields': ('phone', 'website', 'image_url', 'hours')
        }),
        ('Ownership', {
            'fields': ('claimed_by',),
        }),
        ('Stats', {
            'fields': ('avg_rating', 'rating_count')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ('name', 'restaurant', 'category', 'price', 'avg_rating', 'rating_count')
    list_filter = ('category', 'restaurant', 'created_at')
    search_fields = ('name', 'description', 'restaurant__name')
    readonly_fields = ('avg_rating', 'rating_count', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('restaurant', 'name', 'category', 'description', 'price', 'image_url')
        }),
        ('Stats', {
            'fields': ('avg_rating', 'rating_count')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DishRating)
class DishRatingAdmin(admin.ModelAdmin):
    list_display = ('dish', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('dish__name', 'user__username', 'comment')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DishFavorite)
class DishFavoriteAdmin(admin.ModelAdmin):
    list_display = ('dish', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('dish__name', 'user__username')
    readonly_fields = ('created_at',)


@admin.register(RestaurantClaim)
class RestaurantClaimAdmin(admin.ModelAdmin):
    list_display = ('restaurant', 'claimant', 'status', 'method', 'created_at', 'decided_at', 'reviewed_by')
    list_filter = ('status', 'method', 'created_at')
    search_fields = ('restaurant__name', 'claimant__username', 'claimant__email', 'evidence', 'admin_notes')
    autocomplete_fields = ('restaurant', 'claimant', 'reviewed_by')
    readonly_fields = ('created_at', 'decided_at')
    actions = ['approve_claims', 'reject_claims']
    fieldsets = (
        (None, {
            'fields': ('restaurant', 'claimant', 'status', 'method'),
        }),
        ('Submitted info', {
            'fields': ('evidence', 'contact_phone', 'contact_email'),
        }),
        ('Review', {
            'fields': ('admin_notes', 'reviewed_by', 'decided_at'),
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    @admin.action(description=_("Approve selected claims (sets Restaurant.claimed_by)"))
    def approve_claims(self, request, queryset):
        n = 0
        for claim in queryset.filter(status=RestaurantClaim.Status.PENDING):
            claim.status = RestaurantClaim.Status.APPROVED
            claim.decided_at = timezone.now()
            claim.reviewed_by = request.user
            claim.save(update_fields=['status', 'decided_at', 'reviewed_by'])
            claim.restaurant.claimed_by = claim.claimant
            claim.restaurant.save(update_fields=['claimed_by'])
            n += 1
        self.message_user(request, _("%(n)d claims approved.") % {'n': n})

    @admin.action(description=_("Reject selected claims"))
    def reject_claims(self, request, queryset):
        n = queryset.filter(status=RestaurantClaim.Status.PENDING).update(
            status=RestaurantClaim.Status.REJECTED,
            decided_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, _("%(n)d claims rejected.") % {'n': n})
