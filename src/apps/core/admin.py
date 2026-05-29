from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin
from .models import User, PaymentMethod, Follow, AppRegistry, Subscription


# ─────────────────────────────── User ────────────────────────────────────────

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined')
    readonly_fields = ('date_joined', 'last_login')
    fieldsets = UserAdmin.fieldsets + (
        ('Profile', {'fields': ('phone', 'bio', 'avatar')}),
    )


# ─────────────────────────────── AppRegistry ─────────────────────────────────

STATUS_COLORS = {
    AppRegistry.STATUS_LIVE:         ('#16a34a', '#dcfce7'),   # green
    AppRegistry.STATUS_BETA:         ('#d97706', '#fef3c7'),   # amber
    AppRegistry.STATUS_COMING_SOON:  ('#2563eb', '#dbeafe'),   # blue
    AppRegistry.STATUS_ARCHIVED:     ('#6b7280', '#f3f4f6'),   # gray
}


@admin.register(AppRegistry)
class AppRegistryAdmin(admin.ModelAdmin):
    # ── List view ──────────────────────────────────────────────────────────
    list_display = (
        'display_priority',
        'colored_name',
        'slug',
        'status_badge',
        'active_badge',
        'is_featured',
        'domain',
        'created_at',
    )
    list_display_links = ('colored_name',)
    list_editable = ('display_priority', 'is_featured')
    list_filter = ('launch_status', 'is_active', 'is_featured', 'has_bookings')
    search_fields = ('name', 'slug', 'domain', 'tagline')
    ordering = ('display_priority', 'name')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at',)
    actions = ('activate_apps', 'deactivate_apps', 'mark_beta', 'mark_live')
    list_per_page = 25

    # ── Fieldsets (form) ───────────────────────────────────────────────────
    fieldsets = (
        ('🏷️  Identidad', {
            'fields': ('name', 'slug', 'tagline', 'domain', 'icon'),
        }),
        ('📋  Editorial (landing)', {
            'description': 'Controla posición y estado visible en la landing.',
            'fields': ('display_priority', 'launch_status', 'is_active', 'is_featured'),
        }),
        ('📰  Novedades (landing)', {
            'description': 'Última novedad visible para el usuario en la home. Frase corta y en lenguaje humano (ej. "Ya puedes ver eventos de dantza"), no nota técnica.',
            'fields': ('latest_update', 'latest_update_at'),
        }),
        ('🎨  Branding', {
            'classes': ('collapse',),
            'fields': ('primary_color', 'secondary_color', 'font_family'),
        }),
        ('🖼️  Hero & SEO', {
            'classes': ('collapse',),
            'fields': (
                'hero_title', 'hero_subtitle', 'description',
                'hero_image', 'social_image',
            ),
        }),
        ('🔧  Feature Flags', {
            'classes': ('collapse',),
            'fields': ('has_reviews', 'has_maps', 'has_bookings'),
        }),
        ('📅  Metadatos', {
            'classes': ('collapse',),
            'fields': ('created_at',),
        }),
    )

    # ── Custom columns ─────────────────────────────────────────────────────
    @admin.display(description='App', ordering='name')
    def colored_name(self, obj):
        return format_html(
            '<span style="font-weight:600;color:{}">{}</span>',
            obj.primary_color,
            obj.name,
        )

    @admin.display(description='Estado', ordering='launch_status')
    def status_badge(self, obj):
        fg, bg = STATUS_COLORS.get(obj.launch_status, ('#374151', '#f3f4f6'))
        label = obj.get_launch_status_display()
        return format_html(
            '<span style="'
            'background:{bg};color:{fg};'
            'padding:2px 8px;border-radius:9999px;'
            'font-size:11px;font-weight:600;white-space:nowrap'
            '">{label}</span>',
            bg=bg, fg=fg, label=label,
        )

    @admin.display(description='Activa', boolean=False, ordering='is_active')
    def active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color:#16a34a;font-size:16px">●</span>')
        return format_html('<span style="color:#dc2626;font-size:16px">●</span>')

    # ── Bulk actions ───────────────────────────────────────────────────────
    @admin.action(description='✅  Activar apps seleccionadas')
    def activate_apps(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} app(s) activadas.')

    @admin.action(description='🚫  Desactivar apps seleccionadas')
    def deactivate_apps(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} app(s) desactivadas.')

    @admin.action(description='🔵  Marcar como Beta')
    def mark_beta(self, request, queryset):
        updated = queryset.update(launch_status=AppRegistry.STATUS_BETA)
        self.message_user(request, f'{updated} app(s) marcadas como Beta.')

    @admin.action(description='🟢  Marcar como Live')
    def mark_live(self, request, queryset):
        updated = queryset.update(launch_status=AppRegistry.STATUS_LIVE)
        self.message_user(request, f'{updated} app(s) marcadas como Live.')


# ─────────────────────────────── Follow ──────────────────────────────────────

@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('follower', 'followed', 'app_context', 'created_at')
    list_filter = ('app_context',)
    search_fields = ('follower__username', 'followed__username')
    readonly_fields = ('created_at',)


# ─────────────────────────────── PaymentMethod ───────────────────────────────

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('user', 'brand', 'last4', 'exp_month', 'exp_year', 'is_default', 'created_at')
    list_filter = ('brand', 'is_default')
    search_fields = ('user__username', 'user__email', 'last4')
    readonly_fields = ('created_at',)


# ─────────────────────────────── Subscription ────────────────────────────────

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'app_slug', 'tier', 'status', 'current_period_end', 'updated_at')
    list_filter = ('app_slug', 'tier', 'status')
    search_fields = ('user__username', 'user__email', 'stripe_customer_id', 'stripe_subscription_id')
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')

