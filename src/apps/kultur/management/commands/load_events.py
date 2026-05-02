import urllib.request
import json
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from apps.kultur.models import CulturalEvent

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Loads upcoming cultural events from the Open Data Euskadi API'

    def handle(self, *args, **options):
        url = "https://api.euskadi.eus/culture/events/v1.0/events/upcoming?_elements=100&_page=1"
        self.stdout.write(self.style.SUCCESS(f'Fetching from {url}'))

        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        
        try:
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    items = data.get('items', [])
                    
                    created_count = 0
                    updated_count = 0
                    
                    for item in items:
                        # Extract basic fields
                        # The API usually provides an 'id' or uses a URL as ID
                        source_id = item.get('id') or item.get('urlEvent')
                        if not source_id:
                            continue
                            
                        # Dates
                        start_date_str = item.get('startDate')
                        end_date_str = item.get('endDate')
                        
                        start_date = None
                        end_date = None
                        
                        try:
                            if start_date_str:
                                # Format usually is 2026-04-26T20:00:00Z
                                start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                            if end_date_str:
                                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                        except Exception as e:
                            self.stderr.write(f"Date parsing error: {e} for {start_date_str}")
                        
                        # Titles and Descriptions
                        title_es = item.get('nameEs', '')
                        title_eu = item.get('nameEu', '')
                        
                        desc_es = item.get('descriptionEs', '')
                        desc_eu = item.get('descriptionEu', '')
                        
                        # Location and Details
                        venue_es = item.get('establishmentEs', '')
                        venue_eu = item.get('establishmentEu', '')
                        municipality_es = item.get('municipalityEs', '')
                        municipality_eu = item.get('municipalityEu', '')
                        province = item.get('provinceNora', '')
                        event_type_es = item.get('typeEs', '')
                        event_type_eu = item.get('typeEu', '')
                        
                        hours_es = item.get('openingHoursEs', '')
                        hours_eu = item.get('openingHoursEu', '')
                        price_es = item.get('priceEs', '')
                        price_eu = item.get('priceEu', '')
                        
                        purchase_url_es = item.get('purchaseUrlEs', '')
                        purchase_url_eu = item.get('purchaseUrlEu', '')
                        
                        # Geometry (Lat, Lng might be in 'latwgs84', 'lonwgs84' or similar)
                        lat = None
                        lng = None
                        location = None
                        
                        try:
                            lat_val = item.get('municipalityLatitude') or item.get('latwgs84') or item.get('latitude')
                            lng_val = item.get('municipalityLongitude') or item.get('lonwgs84') or item.get('longitude')
                            
                            if lat_val and lng_val:
                                lat = float(lat_val)
                                lng = float(lng_val)
                                location = Point(lng, lat, srid=4326)
                        except (ValueError, TypeError):
                            pass
                            
                        url_es = item.get('urlEventEs', '')
                        url_eu = item.get('urlEventEu', '')
                        
                        images = item.get('images', [])
                        image_url = images[0].get('imageUrl') if images else ''
 
                        # Create or update
                        event, created = CulturalEvent.objects.update_or_create(
                            source_id=str(source_id),
                            defaults={
                                'title_es': title_es[:500] if title_es else None,
                                'title_eu': title_eu[:500] if title_eu else None,
                                'description_es': desc_es,
                                'description_eu': desc_eu,
                                'start_date': start_date,
                                'end_date': end_date,
                                'venue_name_es': venue_es[:500] if venue_es else None,
                                'venue_name_eu': venue_eu[:500] if venue_eu else None,
                                'municipality_es': municipality_es[:255] if municipality_es else None,
                                'municipality_eu': municipality_eu[:255] if municipality_eu else None,
                                'province': province[:255] if province else None,
                                'event_type_es': event_type_es[:255] if event_type_es else None,
                                'event_type_eu': event_type_eu[:255] if event_type_eu else None,
                                'opening_hours_es': hours_es[:500] if hours_es else None,
                                'opening_hours_eu': hours_eu[:500] if hours_eu else None,
                                'price_es': price_es[:500] if price_es else None,
                                'price_eu': price_eu[:500] if price_eu else None,
                                'url_es': url_es[:1000] if url_es else None,
                                'url_eu': url_eu[:1000] if url_eu else None,
                                'purchase_url_es': purchase_url_es[:1000] if purchase_url_es else None,
                                'purchase_url_eu': purchase_url_eu[:1000] if purchase_url_eu else None,
                                'image_url': image_url[:1000] if image_url else None,
                                'location': location,
                            }
                        )
                        
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
                            
                    self.stdout.write(self.style.SUCCESS(f'Successfully loaded {len(items)} events. Created: {created_count}, Updated: {updated_count}'))
                else:
                    self.stderr.write(self.style.ERROR(f'Failed to fetch API. Status: {response.status}'))
                    
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error occurred: {str(e)}'))
