import json
import urllib.request

start_lon, start_lat = -2.203, 43.048
end_lon, end_lat = -1.902, 43.313

url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=geojson"
print("Requesting OSRM URL:", url)

try:
    req = urllib.request.Request(url, headers={"User-Agent": "MubilTCOAdvisor/1.0"})
    with urllib.request.urlopen(req, timeout=5) as response:
        res_data = json.loads(response.read().decode("utf-8"))

    print("OSRM Code:", res_data.get("code"))
    if res_data.get("code") == "Ok":
        route = res_data["routes"][0]
        dist_m = route["distance"]
        dur_s = route["duration"]
        print(f"OSRM Distance: {dist_m / 1000.0:.2f} km")
        print(f"OSRM Duration: {dur_s / 60.0:.1f} mins")
        avg_speed = (dist_m / 1000.0) / (dur_s / 3600.0)
        print(f"OSRM Avg Speed: {avg_speed:.1f} km/h")
        print("GeoJSON Coordinate count:", len(route["geometry"]["coordinates"]))
except Exception as e:
    print("Error calling OSRM:", e)
