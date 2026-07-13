import requests
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from apps.adventure.models import PointOfInterest


class Command(BaseCommand):
    help = "Import rich POIs (shelters, cafes, stations, campsites) from OpenStreetMap via Overpass API"

    def add_arguments(self, parser):
        parser.add_argument(
            "--country", type=str, help="ISO 3166-1 country code (e.g. ES, FR, CH)"
        )
        parser.add_argument(
            "--region",
            type=str,
            help="ISO 3166-2 region code (e.g. ES-PV, FR-ARA, CH-BE)",
        )
        parser.add_argument(
            "--bbox",
            type=str,
            help='Bounding box in format "min_lon,min_lat,max_lon,max_lat"',
        )

    def handle(self, *args, **options):
        country = options.get("country")
        region = options.get("region")
        bbox = options.get("bbox")

        if region:
            area_expr = f'area["ISO3166-2"="{region}"]->.a;'
            filter_expr = "(area.a)"
            self.stdout.write(f"Fetching POIs for region {region} from Overpass API...")
        elif country:
            area_expr = f'area["ISO3166-1"="{country}"]->.a;'
            filter_expr = "(area.a)"
            self.stdout.write(
                f"Fetching POIs for country {country} from Overpass API..."
            )
        elif bbox:
            coords = [c.strip() for c in bbox.split(",")]
            if len(coords) != 4:
                self.stdout.write(
                    self.style.ERROR(
                        'Bbox format must be "min_lon,min_lat,max_lon,max_lat"'
                    )
                )
                return
            # Overpass expects (lat_min, lon_min, lat_max, lon_max)
            area_expr = ""
            filter_expr = f"({coords[1]},{coords[0]},{coords[3]},{coords[2]})"
            self.stdout.write(
                f"Fetching POIs for bounding box {bbox} from Overpass API..."
            )
        else:
            # Default to ES-PV
            area_expr = 'area["ISO3166-2"="ES-PV"]->.a;'
            filter_expr = "(area.a)"
            self.stdout.write(
                "Fetching POIs for default region (Basque Country, ES-PV) from Overpass API..."
            )

        query = f"""
        [out:json][timeout:120];
        {area_expr}
        (
          node["amenity"="shelter"]{filter_expr};
          node["tourism"="alpine_hut"]{filter_expr};
          node["tourism"="wilderness_hut"]{filter_expr};
          node["amenity"="cafe"]{filter_expr};
          node["amenity"="restaurant"]{filter_expr};
          node["tourism"="camp_site"]{filter_expr};
          node["tourism"="caravan_site"]{filter_expr};
          node["railway"="station"]{filter_expr};
          node["public_transport"="station"]{filter_expr};
        );
        out body;
        """
        url = "https://overpass-api.de/api/interpreter"
        headers = {
            "User-Agent": "MapsEusAdventurePlanner/1.0 (imanol@maps.eus)",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            response = requests.post(url, data={"data": query}, headers=headers)
            response.raise_for_status()
            data = response.json()

            if "remark" in data:
                self.stdout.write(
                    self.style.WARNING(f"Overpass API Warning/Error: {data['remark']}")
                )

            elements = data.get("elements", [])
            self.stdout.write(f"Found {len(elements)} POI elements. Importing...")

            count = 0
            pois_to_create = []

            for el in elements:
                osm_id = el["id"]
                lat = el["lat"]
                lon = el["lon"]
                tags = el.get("tags", {})
                name = tags.get("name", "")

                # Determine POI type
                poi_type = "other"

                # 1. Shelter
                if tags.get("amenity") == "shelter" or tags.get("tourism") in [
                    "alpine_hut",
                    "wilderness_hut",
                ]:
                    poi_type = "shelter"
                # 2. Cafe / Rest
                elif tags.get("amenity") in ["cafe", "restaurant", "bar", "pub"]:
                    poi_type = "cafe"
                # 3. Camping (Paid)
                elif tags.get("tourism") == "camp_site":
                    # Determine if it's paid or free (default paid)
                    fee = tags.get("fee", "yes")
                    if fee == "no":
                        poi_type = "camp_free"
                    else:
                        poi_type = "camp_paid"
                # 4. Camper / Free area
                elif (
                    tags.get("tourism") == "caravan_site"
                    or tags.get("amenity") == "caravan_site"
                ):
                    poi_type = "camp_free"
                # 5. Station
                elif (
                    tags.get("railway") == "station"
                    or tags.get("public_transport") == "station"
                ):
                    poi_type = "station"

                # We skip 'other' to keep it clean and high-quality
                if poi_type == "other":
                    continue

                poi = PointOfInterest(
                    osm_id=osm_id,
                    poi_type=poi_type,
                    name=name,
                    location=Point(lon, lat, srid=4326),
                    tags=tags,
                )
                pois_to_create.append(poi)

            # Bulk create
            if pois_to_create:
                PointOfInterest.objects.bulk_create(
                    pois_to_create, ignore_conflicts=True
                )
                count = len(pois_to_create)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully imported {count} rich POIs from Overpass!"
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error importing POIs: {e}"))
