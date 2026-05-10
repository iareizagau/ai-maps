from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, PaymentMethod, Follow, AppRegistry, Subscription

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Profile', {'fields': ('phone', 'bio', 'avatar')}),
    )

@admin.register(AppRegistry)
class AppRegistryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'domain', 'is_active', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'domain')
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'domain', 'is_active')
        }),
        ('Branding', {
            'fields': ('primary_color', 'secondary_color', 'font_family')
        }),
        ('Hero Content', {
            'fields': ('hero_title', 'hero_subtitle', 'hero_image')
        }),
        ('Feature Flags', {
            'fields': ('has_reviews', 'has_maps', 'has_bookings')
        }),
    )

@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('follower', 'followed', 'app_context', 'created_at')
    list_filter = ('app_context',)

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('user', 'brand', 'last4', 'is_default')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'app_slug', 'tier', 'status', 'current_period_end', 'updated_at')
    list_filter = ('app_slug', 'tier', 'status')
    search_fields = ('user__username', 'user__email', 'stripe_customer_id', 'stripe_subscription_id')
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')
