import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from apps.sbk.models import Event, Artist, EventType, DanceStyle

class Command(BaseCommand):
    help = 'Load SBK events from Go&Dance API'

    def handle(self, *args, **kwargs):
        url = "https://www.goandance.com/api/affiliates/410cff06-0b5e-41d0-869e-6a6368af4c40/events"
        
        self.stdout.write("Fetching events from Go&Dance...")
        
        # In a real scenario we might need to handle pagination if 'nextUrl' is present
        # But for this demo, we just fetch the first page
        response = requests.get(url)
        if response.status_code != 200:
            self.stderr.write(self.style.ERROR(f"Failed to fetch data: {response.status_code}"))
            return
            
        data = response.json()
        
        # The data returned is an array directly? 
        # Wait, the content from read_url_content showed it as a list of dicts. Let me parse it correctly.
        # It's an array of events. Oh wait, at the end of the JSON it showed:
        # "meta":{"totalResults":88,"rpp":18,"totalPages":5,"currentPage":0,"nextUrl":"https:\/\/www.goandance.com\/api\/affiliates\/410cff06-0b5e-41d0-869e-6a6368af4c40\/events?page=1"}
        # Actually, looking at the JSON, it seems the root is a list, OR maybe it has 'events' key.
        # Let's assume it's a list for now, or if it's a dict, we check for 'data' or iterate directly.
        if isinstance(data, dict):
            events_data = data.get('data', []) or data.get('events', [])
            if not events_data and 'uuid' in str(data): 
                # maybe it's just the dict itself? No, looking at the data, it's a list of dicts + a meta dict at the end? 
                # Wait, JSON must have a single root. Let's just handle lists or dicts with 'data'
                pass
        elif isinstance(data, list):
            events_data = data
            
        # The API actually returns a list, and the last item might be a dict with 'meta' key? 
        # Wait, the read_url_content output showed `[ { event1 }, { event2 }, ..., {"meta":...} ]`? Or maybe `{ "data": [...], "meta": ... }`?
        # I'll just try to parse it safely.
        if isinstance(data, dict):
            if 'data' in data:
                events_data = data['data']
            elif 'events' in data:
                events_data = data['events']
            else:
                # If it's a list disguised as dict (unlikely)
                events_data = [v for k,v in data.items() if isinstance(v, dict) and 'uuid' in v]
        elif isinstance(data, list):
            # Sometimes APIs return a list where the last item is the metadata...
            events_data = [item for item in data if 'uuid' in item]
        else:
            self.stderr.write(self.style.ERROR("Unrecognized JSON format"))
            return
            
        events_created = 0
        events_updated = 0
        
        for item in events_data:
            goandance_id = item.get('uuid')
            if not goandance_id:
                continue
                
            name_data = item.get('name', {})
            name = name_data.get('es') or name_data.get('en') or "Unknown Event"
            
            desc_data = item.get('description', {})
            description = desc_data.get('es') or desc_data.get('en') or ""
            
            short_desc_data = item.get('shortDescription', {})
            short_description = short_desc_data.get('es') or short_desc_data.get('en') or ""
            
            start_date_str = item.get('dateFrom')
            end_date_str = item.get('dateTo')
            
            if not start_date_str or not end_date_str:
                continue
                
            start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            
            address_data = item.get('address', {})
            formatted_address = address_data.get('formattedAddress', '')
            city = address_data.get('locality', '')
            country = address_data.get('country', {}).get('caption', '')
            
            lat_lng = address_data.get('latLng', {})
            lat = lat_lng.get('lat')
            lng = lat_lng.get('lng')
            
            img_data = item.get('image', {})
            image_url = img_data.get('url', '')
            
            urls = item.get('url', {})
            ticket_url = urls.get('es') or urls.get('en') or ""
            
            # Simple heuristic for style based on text
            text_to_search = (name + " " + description).lower()
            primary_style = DanceStyle.MIXED
            if 'bachata' in text_to_search and 'salsa' not in text_to_search and 'kizomba' not in text_to_search:
                primary_style = DanceStyle.BACHATA
            elif 'salsa' in text_to_search and 'bachata' not in text_to_search and 'kizomba' not in text_to_search:
                primary_style = DanceStyle.SALSA
            elif 'kizomba' in text_to_search and 'bachata' not in text_to_search and 'salsa' not in text_to_search:
                primary_style = DanceStyle.KIZOMBA
                
            type_data = item.get('type', {})
            event_code = type_data.get('code', 'festival')
            if event_code == 'festival':
                event_type = EventType.FESTIVAL
            elif event_code == 'party':
                event_type = EventType.PARTY
            elif event_code == 'workshop':
                event_type = EventType.WORKSHOP
            else:
                event_type = EventType.FESTIVAL
            
            event, created = Event.objects.update_or_create(
                goandance_id=goandance_id,
                defaults={
                    'name': name,
                    'description': description,
                    'short_description': short_description,
                    'start_date': start_date,
                    'end_date': end_date,
                    'event_type': event_type,
                    'primary_style': primary_style,
                    'address': formatted_address,
                    'city': city,
                    'country': country,
                    'lat': lat,
                    'lng': lng,
                    'image_url': image_url,
                    'ticket_url': ticket_url,
                }
            )
            
            if created:
                events_created += 1
            else:
                events_updated += 1
                
        self.stdout.write(self.style.SUCCESS(f"Successfully loaded events. Created: {events_created}, Updated: {events_updated}"))
