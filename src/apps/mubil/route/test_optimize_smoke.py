"""Quick smoke test for the /api/route/optimize endpoint."""

import requests

payload = {
    "locations": [
        {"name": "Base Mungia", "lat": 43.354, "lng": -2.847, "is_depot": True},
        {"name": "Entrega Bilbao", "lat": 43.263, "lng": -2.935},
        {"name": "Entrega Getxo", "lat": 43.356, "lng": -3.012},
        {"name": "Entrega Durango", "lat": 43.170, "lng": -2.632},
        {"name": "Entrega Gernika", "lat": 43.316, "lng": -2.677},
    ],
    "soc_start": 90.0,
}

r = requests.post(
    "http://localhost:9000/api/mubil/v1/route/optimize", json=payload, timeout=30
)
print(f"Status: {r.status_code}")
data = r.json()

if r.status_code != 200:
    print(f"Error: {data}")
else:
    print(f"Distance: {data['total_distance_km']} km")
    print(f"Duration: {data['total_duration_min']} min")
    print(f"EV cost: {data['ev_cost_eur']} EUR")
    print(f"ICE cost: {data['ice_cost_eur']} EUR")
    print(f"Savings: {data['savings_eur']} EUR")
    print(f"CO2 saved: {data['co2_saved_kg']} kg")
    print(f"Charge stop: {data['needs_charge_stop']}")
    print(f"Opt savings: {data['optimization_savings_pct']}%")
    print()
    for stop in data.get("ordered_stops", []):
        soc = stop.get("arrival_soc", "?")
        dist = stop.get("distance_from_prev_km", 0)
        print(f"  {stop['type']:12s} | {stop['name']:35s} | SOC {soc:5}% | +{dist} km")
