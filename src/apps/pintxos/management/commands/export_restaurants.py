import json
import csv
from django.core.management.base import BaseCommand
from apps.pintxos.models import Restaurant, Dish


class Command(BaseCommand):
    help = "Export restaurants and dishes to JSON or CSV format"

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            type=str,
            choices=["json", "csv"],
            default="json",
            help="Export format (json or csv)",
        )
        parser.add_argument(
            "--output",
            type=str,
            help="Output file path (if not specified, prints to stdout)",
        )
        parser.add_argument(
            "--include-dishes",
            action="store_true",
            help="Include dishes data in export",
        )

    def handle(self, *args, **options):
        format_type = options["format"]
        output_file = options["output"]
        include_dishes = options["include_dishes"]

        restaurants = Restaurant.objects.all()

        if format_type == "json":
            self._export_json(restaurants, output_file, include_dishes)
        elif format_type == "csv":
            self._export_csv(restaurants, output_file, include_dishes)

    def _export_json(self, restaurants, output_file, include_dishes):
        data = []
        for restaurant in restaurants:
            restaurant_data = {
                "id": restaurant.id,
                "name": restaurant.name,
                "category": restaurant.get_category_display(),
                "address": restaurant.address,
                "latitude": restaurant.location.y if restaurant.location else None,
                "longitude": restaurant.location.x if restaurant.location else None,
                "phone": restaurant.phone,
                "website": restaurant.website,
                "description": restaurant.description,
                "created_at": restaurant.created_at.isoformat() if restaurant.created_at else None,
            }

            if include_dishes:
                dishes = Dish.objects.filter(restaurant=restaurant)
                restaurant_data["dishes"] = [
                    {
                        "id": dish.id,
                        "name": dish.name,
                        "category": dish.get_category_display(),
                        "price": str(dish.price) if dish.price else None,
                        "avg_rating": float(dish.avg_rating) if dish.avg_rating else None,
                        "rating_count": dish.rating_count,
                    }
                    for dish in dishes
                ]

            data.append(restaurant_data)

        output = json.dumps(data, indent=2, ensure_ascii=False)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output)
            self.stdout.write(self.style.SUCCESS(f"✓ Exported {len(data)} restaurants to {output_file}"))
        else:
            self.stdout.write(output)

    def _export_csv(self, restaurants, output_file, include_dishes):
        if include_dishes:
            # Export dishes with restaurant info
            rows = []
            for restaurant in restaurants:
                dishes = Dish.objects.filter(restaurant=restaurant)
                for dish in dishes:
                    rows.append({
                        "restaurant_id": restaurant.id,
                        "restaurant_name": restaurant.name,
                        "restaurant_category": restaurant.get_category_display(),
                        "restaurant_address": restaurant.address,
                        "restaurant_phone": restaurant.phone,
                        "dish_id": dish.id,
                        "dish_name": dish.name,
                        "dish_category": dish.get_category_display(),
                        "dish_price": dish.price,
                        "dish_avg_rating": dish.avg_rating,
                        "dish_rating_count": dish.rating_count,
                    })

            fieldnames = [
                "restaurant_id", "restaurant_name", "restaurant_category", "restaurant_address",
                "restaurant_phone", "dish_id", "dish_name", "dish_category", "dish_price",
                "dish_avg_rating", "dish_rating_count",
            ]
        else:
            # Export only restaurants
            rows = [
                {
                    "id": r.id,
                    "name": r.name,
                    "category": r.get_category_display(),
                    "address": r.address,
                    "latitude": r.location.y if r.location else None,
                    "longitude": r.location.x if r.location else None,
                    "phone": r.phone,
                    "website": r.website,
                }
                for r in restaurants
            ]

            fieldnames = ["id", "name", "category", "address", "latitude", "longitude", "phone", "website"]

        if output_file:
            with open(output_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            self.stdout.write(self.style.SUCCESS(f"✓ Exported {len(rows)} rows to {output_file}"))
        else:
            import sys
            writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
