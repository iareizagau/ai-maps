import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.gis.geos import Point, LineString, MultiPolygon, Polygon, GEOSGeometry
from .models import PacificCountry, CycloneEvent

# Sample dataset for automatic seeding if DB is empty
MOCK_COUNTRIES = [
    {
        "name": "Tuvalu",
        "code": "TUV",
        "population": 11200,
        "co2": 0.9,
        "vulnerability": 0.58,
        "readiness": 0.38,
        "coords": [179.1962, -8.5211],
        # Small polygon representation of Funafuti area for Leaflet
        "poly": [[[179.15, -8.55], [179.25, -8.55], [179.25, -8.48], [179.15, -8.48], [179.15, -8.55]]]
    },
    {
        "name": "Kiribati",
        "code": "KIR",
        "population": 131000,
        "co2": 0.6,
        "vulnerability": 0.54,
        "readiness": 0.35,
        "coords": [172.9717, 1.3278],
        "poly": [[[172.90, 1.25], [173.05, 1.25], [173.05, 1.40], [172.90, 1.40], [172.90, 1.25]]]
    },
    {
        "name": "Marshall Islands",
        "code": "MHL",
        "population": 42000,
        "co2": 1.5,
        "vulnerability": 0.53,
        "readiness": 0.40,
        "coords": [171.3800, 7.1170],
        "poly": [[[171.30, 7.05], [171.45, 7.05], [171.45, 7.20], [171.30, 7.20], [171.30, 7.05]]]
    },
    {
        "name": "Fiji",
        "code": "FJI",
        "population": 936000,
        "co2": 1.8,
        "vulnerability": 0.46,
        "readiness": 0.49,
        "coords": [178.4419, -18.1248],
        "poly": [[[177.0, -19.0], [179.5, -19.0], [179.5, -16.0], [177.0, -16.0], [177.0, -19.0]]]
    },
    {
        "name": "Vanuatu",
        "code": "VUT",
        "population": 326000,
        "co2": 0.5,
        "vulnerability": 0.51,
        "readiness": 0.36,
        "coords": [168.3270, -17.7330],
        "poly": [[[166.5, -20.5], [170.0, -20.5], [170.0, -14.5], [166.5, -14.5], [166.5, -20.5]]]
    },
    {
        "name": "Samoa",
        "code": "WSM",
        "population": 222000,
        "co2": 1.2,
        "vulnerability": 0.45,
        "readiness": 0.52,
        "coords": [171.7600, -13.8333],
        "poly": [[[172.8, -14.2], [171.2, -14.2], [171.2, -13.4], [172.8, -13.4], [172.8, -14.2]]]
    },
    {
        "name": "Solomon Islands",
        "code": "SLB",
        "population": 720000,
        "co2": 0.4,
        "vulnerability": 0.52,
        "readiness": 0.33,
        "coords": [159.9729, -9.4456],
        "poly": [[[155.5, -11.5], [162.5, -11.5], [162.5, -6.5], [155.5, -6.5], [155.5, -11.5]]]
    },
    {
        "name": "Tonga",
        "code": "TON",
        "population": 106000,
        "co2": 1.1,
        "vulnerability": 0.47,
        "readiness": 0.46,
        "coords": [-175.2049, -21.1396],
        "poly": [[[-176.0, -22.5], [-173.0, -22.5], [-173.0, -15.0], [-176.0, -15.0], [-176.0, -22.5]]]
    },
    {
        "name": "Palau",
        "code": "PLW",
        "population": 18000,
        "co2": 13.5,
        "vulnerability": 0.43,
        "readiness": 0.48,
        "coords": [134.5074, 7.3611],
        "poly": [[[134.0, 6.8], [135.0, 6.8], [135.0, 8.5], [134.0, 8.5], [134.0, 6.8]]]
    },
    {
        "name": "Micronesia",
        "code": "FSM",
        "population": 114000,
        "co2": 1.0,
        "vulnerability": 0.50,
        "readiness": 0.38,
        "coords": [158.1611, 6.9172],
        "poly": [[[137.0, 1.0], [163.0, 1.0], [163.0, 10.0], [137.0, 10.0], [137.0, 1.0]]]
    },
    {
        "name": "Nauru",
        "code": "NRU",
        "population": 12000,
        "co2": 4.8,
        "vulnerability": 0.49,
        "readiness": 0.39,
        "coords": [166.9211, -0.5476],
        "poly": [[[166.90, -0.56], [166.94, -0.56], [166.94, -0.52], [166.90, -0.52], [166.90, -0.56]]]
    },
    {
        "name": "Papua New Guinea",
        "code": "PNG",
        "population": 10000000,
        "co2": 0.7,
        "vulnerability": 0.53,
        "readiness": 0.32,
        "coords": [147.1803, -9.4438],
        "poly": [[[141.0, -12.0], [156.0, -12.0], [156.0, -2.0], [141.0, -2.0], [141.0, -12.0]]]
    }
]

MOCK_CYCLONES = [
    {
        "name": "Winston",
        "year": 2016,
        "category": 5,
        "winds": 280,
        "damage": 1400000000.00,
        "route": [[170.5, -15.5], [172.0, -17.0], [174.5, -18.5], [177.5, -20.0], [179.9, -19.5], [178.5, -17.5], [176.0, -17.0]]
    },
    {
        "name": "Pam",
        "year": 2015,
        "category": 5,
        "winds": 270,
        "damage": 433000000.00,
        "route": [[166.0, -10.0], [167.2, -12.5], [168.0, -15.0], [168.5, -17.8], [169.2, -20.5], [170.5, -23.0], [172.0, -26.0]]
    },
    {
        "name": "Gita",
        "year": 2018,
        "category": 4,
        "winds": 230,
        "damage": 250000000.00,
        "route": [[177.0, -15.0], [-179.0, -18.0], [-175.0, -21.0], [-176.5, -22.5], [178.0, -23.0], [173.0, -21.0]]
    }
]

def auto_seed_if_needed():
    """Seeds sample data if database table is empty."""
    if PacificCountry.objects.count() == 0:
        for c in MOCK_COUNTRIES:
            pnt = Point(c["coords"][0], c["coords"][1], srid=4326)
            
            # Simple bounding box representation of geom for rendering maps
            shell = c["poly"][0]
            poly = Polygon(shell)
            mpoly = MultiPolygon(poly)
            
            PacificCountry.objects.create(
                name=c["name"],
                code=c["code"],
                population=c["population"],
                co2_emissions=c["co2"],
                nd_gain_vulnerability=c["vulnerability"],
                nd_gain_readiness=c["readiness"],
                geom=mpoly,
                capital_coords=pnt
            )
            
    if CycloneEvent.objects.count() == 0:
        for cyc in MOCK_CYCLONES:
            line = LineString(cyc["route"])
            CycloneEvent.objects.create(
                name=cyc["name"],
                year=cyc["year"],
                category=cyc["category"],
                max_wind_speed=cyc["winds"],
                damage_usd=cyc["damage"],
                route_geom=line
            )

@ensure_csrf_cookie
def home(request):
    # Ensure database has mock data for rendering
    auto_seed_if_needed()
    
    countries = PacificCountry.objects.all()
    cyclones = CycloneEvent.objects.all()
    
    # Global comparison emitters for the Carbon Debt Chart
    comparison_emitters = [
        {"name": "Qatar", "co2": 35.5, "vulnerability": 0.32, "readiness": 0.58, "is_pacific": False},
        {"name": "United States", "co2": 14.9, "vulnerability": 0.28, "readiness": 0.72, "is_pacific": False},
        {"name": "Australia", "co2": 15.3, "vulnerability": 0.29, "readiness": 0.74, "is_pacific": False},
        {"name": "China", "co2": 8.0, "vulnerability": 0.39, "readiness": 0.52, "is_pacific": False},
        {"name": "World Average", "co2": 4.7, "vulnerability": 0.42, "readiness": 0.48, "is_pacific": False},
    ]
    
    # Format Pacific Countries data for chart
    for country in countries:
        comparison_emitters.append({
            "name": country.name,
            "co2": country.co2_emissions,
            "vulnerability": country.nd_gain_vulnerability,
            "readiness": country.nd_gain_readiness,
            "is_pacific": True
        })

    context = {
        'countries': countries,
        'cyclones': cyclones,
        'chart_data': json.dumps(comparison_emitters),
    }
    return render(request, 'oceania/home.html', context)

def country_geojson(request):
    countries = PacificCountry.objects.all()
    features = []
    for c in countries:
        if c.geom:
            feature = {
                "type": "Feature",
                "properties": {
                    "id": c.id,
                    "name": c.name,
                    "code": c.code,
                    "population": c.population,
                    "co2": c.co2_emissions,
                    "vulnerability": c.nd_gain_vulnerability,
                    "readiness": c.nd_gain_readiness,
                    "capital": [c.capital_coords.x, c.capital_coords.y] if c.capital_coords else None
                },
                "geometry": json.loads(c.geom.geojson)
            }
            features.append(feature)
            
    return JsonResponse({
        "type": "FeatureCollection",
        "features": features
    })

def cyclone_geojson(request):
    cyclones = CycloneEvent.objects.all()
    features = []
    for cyc in cyclones:
        feature = {
            "type": "Feature",
            "properties": {
                "id": cyc.id,
                "name": cyc.name,
                "year": cyc.year,
                "category": cyc.category,
                "winds": cyc.max_wind_speed,
                "damage": float(cyc.damage_usd) if cyc.damage_usd else 0.0
            },
            "geometry": json.loads(cyc.route_geom.geojson)
        }
        features.append(feature)
        
    return JsonResponse({
        "type": "FeatureCollection",
        "features": features
    })
