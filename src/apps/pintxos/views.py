from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_control
import json

from apps.core.entitlements import has_entitlement
from .forms import RestaurantClaimForm, RestaurantManageForm
from .models import Restaurant, Dish, RestaurantClaim
from . import selectors


def index(request):
    """Main pintxos page - map + search + navigator"""
    q = request.GET.get('q')
    category = request.GET.get('category')
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    radius = request.GET.get('radius', 5)

    # Use custom QuerySet methods
    restaurants = Restaurant.objects.approved().search(q).by_category(category)

    if lat and lon:
        restaurants = restaurants.nearby(lon, lat, radius)
    else:
        restaurants = restaurants.order_by('-avg_rating', '-created_at')

    # Preparation for Leaderboard Lenses
    lense = request.GET.get('lense', 'global')
    top_dishes = selectors.get_top_dishes(user=request.user, limit=5, lense=lense)

    if request.headers.get('HX-Request'):
        if request.GET.get('component') == 'leaderboard':
            return render(request, 'pintxos/partials/leaderboard_content.html', {'top_dishes': top_dishes})
        return render(request, 'pintxos/partials/restaurant_grid.html', {'restaurants': restaurants})

    # Prepare restaurant data for map
    restaurants_json = json.dumps([
        {
            'id': r.id,
            'name': r.name,
            'address': r.address,
            'latitude': r.location.y,
            'longitude': r.location.x,
            'category': r.get_category_display(),
        }
        for r in restaurants
    ])

    # Get all categories for the filter slider
    categories = [
        {'id': choice[0], 'label': choice[1]}
        for choice in Dish.Category.choices
    ]

    context = {
        'restaurants': restaurants,
        'restaurants_json': restaurants_json,
        'top_dishes': top_dishes,
        'categories': categories,
    }
    return render(request, 'pintxos/index.html', context)


def restaurant_detail(request, restaurant_id):
    """Restaurant detail page"""
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    dishes = restaurant.dishes.all()
    context = {
        'restaurant': restaurant,
        'dishes': dishes,
    }
    return render(request, 'pintxos/restaurant_detail.html', context)


@login_required
def restaurant_create(request):
    """Create new restaurant (GET form + POST handler)"""
    # Logic for POST is handled by Ninja API/HTMX, this just serves the template
    return render(request, 'pintxos/restaurant_form.html')


def restaurant_edit(request, restaurant_id):
    """Edit restaurant (GET form + POST handler)"""
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    context = {'restaurant': restaurant}
    return render(request, 'pintxos/restaurant_form.html', context)


def dish_detail(request, dish_id):
    """Dish detail page"""
    dish = get_object_or_404(Dish, id=dish_id)
    ratings = dish.ratings.all()[:10]
    context = {
        'dish': dish,
        'ratings': ratings,
    }
    return render(request, 'pintxos/dish_detail.html', context)


@login_required
def dish_create(request, restaurant_id):
    """Create new dish (GET form + POST handler)"""
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    context = {'restaurant': restaurant}
    return render(request, 'pintxos/dish_form.html', context)


@login_required
def dish_rate(request, dish_id):
    """Rate a dish (GET form + POST handler)"""
    dish = get_object_or_404(Dish, id=dish_id)
    context = {'dish': dish}
    return render(request, 'pintxos/dish_rate.html', context)


@login_required
def restaurant_claim(request, restaurant_id):
    """Submit ownership claim for a venue. Admin reviews."""
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)

    if restaurant.claimed_by_id:
        if restaurant.claimed_by_id == request.user.id:
            return redirect('pintxos:restaurant_manage', restaurant_id=restaurant.id)
        messages.error(request, _("This venue is already claimed."))
        return redirect('pintxos:restaurant_detail', restaurant_id=restaurant.id)

    existing = RestaurantClaim.objects.filter(
        restaurant=restaurant, claimant=request.user
    ).first()
    if existing and existing.status == RestaurantClaim.Status.PENDING:
        messages.info(request, _("You already submitted a claim for this venue. We're reviewing it."))
        return redirect('account_app_panel', slug='pintxos')

    if request.method == 'POST':
        form = RestaurantClaimForm(request.POST, instance=existing)
        if form.is_valid():
            claim = form.save(commit=False)
            claim.restaurant = restaurant
            claim.claimant = request.user
            claim.status = RestaurantClaim.Status.PENDING
            claim.decided_at = None
            claim.reviewed_by = None
            claim.save()
            messages.success(request, _("Claim submitted. We'll get back to you within 48h."))
            return redirect('account_app_panel', slug='pintxos')
    else:
        form = RestaurantClaimForm(instance=existing, initial={
            'contact_email': request.user.email,
            'contact_phone': getattr(request.user, 'phone', '') or '',
        })

    return render(request, 'pintxos/claim.html', {
        'restaurant': restaurant,
        'form': form,
    })


@login_required
def restaurant_manage(request, restaurant_id):
    """Manage a venue you own. Free claim = edit basics. Pro = analytics + more."""
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    if restaurant.claimed_by_id != request.user.id and not request.user.is_staff:
        return HttpResponseForbidden(_("You don't manage this venue."))

    if request.method == 'POST':
        form = RestaurantManageForm(request.POST, instance=restaurant)
        if form.is_valid():
            form.save()
            messages.success(request, _("Venue updated."))
            return redirect('pintxos:restaurant_manage', restaurant_id=restaurant.id)
    else:
        form = RestaurantManageForm(instance=restaurant)

    return render(request, 'pintxos/manage.html', {
        'restaurant': restaurant,
        'form': form,
        'dishes': restaurant.dishes.all(),
        'has_analytics': has_entitlement(request.user, 'pintxos', 'analytics_dashboard'),
        'has_priority': has_entitlement(request.user, 'pintxos', 'priority_listing'),
    })


def comanda(request):
    """Group order pad: tally drinks, pintxos and raciones before going to the bar.

    Pure client-side (Alpine + localStorage) - no auth, no DB writes.
    """
    return render(request, 'pintxos/comanda.html')


def comanda_camarero(request):
    """High-contrast read-only view to show the bartender. Reads same localStorage."""
    return render(request, 'pintxos/comanda_camarero.html')


def comanda_manifest(request):
    """PWA manifest for the comanda app."""
    data = {
        "name": "Comanda Pintxos.eus",
        "short_name": "Comanda",
        "description": "Apunta lo que pide tu grupo antes de ir a la barra.",
        "start_url": reverse('pintxos:comanda'),
        "scope": reverse('pintxos:comanda'),
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0f172a",
        "theme_color": "#f97316",
        "icons": [
            {
                "src": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 192 192'><rect width='192' height='192' rx='32' fill='%23f97316'/><text x='50%' y='55%' font-size='128' text-anchor='middle' dominant-baseline='middle'>🍻</text></svg>",
                "sizes": "192x192",
                "type": "image/svg+xml",
                "purpose": "any",
            },
            {
                "src": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'><rect width='512' height='512' rx='96' fill='%23f97316'/><text x='50%' y='55%' font-size='340' text-anchor='middle' dominant-baseline='middle'>🍻</text></svg>",
                "sizes": "512x512",
                "type": "image/svg+xml",
                "purpose": "any",
            },
        ],
    }
    return JsonResponse(data)


@cache_control(max_age=0, no_cache=True)
def comanda_sw(request):
    """Service worker for offline support of the comanda views."""
    sw = """
const CACHE = 'comanda-v1';
const ASSETS = [
    '%(comanda)s',
    '%(camarero)s',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).catch(() => {})
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(
            keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))
        ))
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const req = event.request;
    if (req.method !== 'GET') return;
    event.respondWith(
        fetch(req)
            .then((res) => {
                const copy = res.clone();
                caches.open(CACHE).then((cache) => cache.put(req, copy)).catch(() => {});
                return res;
            })
            .catch(() => caches.match(req).then((hit) => hit || caches.match('%(comanda)s')))
    );
});
""" % {
        'comanda': reverse('pintxos:comanda'),
        'camarero': reverse('pintxos:comanda_camarero'),
    }
    return HttpResponse(sw, content_type='application/javascript')
