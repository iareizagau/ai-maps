from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import Restaurant, Dish, DishRating, DishFavorite


@admin.register(Restaurant)
class RestaurantAdmin(GISModelAdmin):
    list_display = ('name', 'category', 'address', 'approved', 'avg_rating', 'rating_count')
    list_filter = ('category', 'approved', 'created_at')
    search_fields = ('name', 'address', 'description')
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
