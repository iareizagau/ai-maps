import requests
import xml.etree.ElementTree as ET
import re
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from apps.gailur.models import Crag, Sector, Route
from django.utils.text import slugify
from urllib.parse import urlparse

class Command(BaseCommand):
    help = 'Bilingual scraping of climbing blogs merging content into single entries'

    def handle(self, *args, **options):
        # Configuración de los feeds con su idioma asociado
        feeds = [
            {'url': 'https://eskalatzencas.blogspot.com/feeds/posts/default?max-results=500', 'lang': 'es'},
            {'url': 'https://eskalatzeneus.blogspot.com/feeds/posts/default?max-results=500', 'lang': 'eu'}
        ]

        clean_html = re.compile('<.*?>')

        for feed in feeds:
            url = feed['url']
            lang = feed['lang']
            self.stdout.write(f"Fetching {lang.upper()} feed: {url}")
            
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                root = ET.fromstring(response.content)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error fetching {url}: {e}"))
                continue
            
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            new_count = 0
            update_count = 0
            
            for entry in root.findall('atom:entry', ns):
                title_elem = entry.find('atom:title', ns)
                if title_elem is None or not title_elem.text:
                    continue
                
                link_elem = entry.find('atom:link[@rel="alternate"]', ns)
                if link_elem is None:
                    continue
                
                full_url = link_elem.get('href')
                url_path = urlparse(full_url).path
                route_slug = slugify(url_path.replace('.html', '').replace('/', '-'))[:255]

                title = title_elem.text
                content_elem = entry.find('atom:content', ns)
                content = content_elem.text if content_elem is not None else ""
                
                match = re.match(r"^(?P<zone>.*?) - (?P<route>.*?) \((?P<specs>.*)\)$", title)
                
                if match:
                    zone_name = match.group('zone').strip()
                    route_name = match.group('route').strip()
                    specs = match.group('specs').strip()
                    
                    description = re.sub(clean_html, '', content[:2000]) + "..."
                    
                    # 1. Crag (Bilingual)
                    zone_slug = slugify(zone_name)[:50]
                    crag, created_crag = Crag.objects.get_or_create(
                        slug=zone_slug,
                        defaults={'location': Point(0, 0)}
                    )
                    
                    # Update crag name and description based on current language
                    if lang == 'es':
                        crag.name_es = zone_name
                        crag.description_es = f"Zona extraída del blog Eskalatzencas."
                    else:
                        crag.name_eu = zone_name
                        crag.description_eu = f"Eskalatzeneus blogetik ateratako zona."
                    crag.save()
                    
                    # 2. Sector
                    sector, _ = Sector.objects.get_or_create(crag=crag, name="Principal")
                    
                    # 3. Grade
                    grade = ""
                    parts = [p.strip() for p in specs.split(',')]
                    for p in parts:
                        if re.match(r'^[1-9][a-c][\+]?$', p):
                            grade = p
                            break
                    if not grade and len(parts) > 1:
                        grade = parts[1] if len(parts[1]) < 10 else parts[0]

                    # 4. Route (Bilingual)
                    route, created_route = Route.objects.get_or_create(
                        slug=route_slug,
                        defaults={'sector': sector, 'grade': grade[:20]}
                    )
                    
                    if lang == 'es':
                        route.name_es = route_name
                        route.description_es = specs + "\n\n" + description
                    else:
                        route.name_eu = route_name
                        route.description_eu = specs + "\n\n" + description
                    
                    route.save()
                    
                    if created_route:
                        new_count += 1
                    else:
                        update_count += 1

            self.stdout.write(self.style.SUCCESS(f"Finished {lang.upper()}. New: {new_count}, Updated with {lang.upper()}: {update_count}"))

        self.stdout.write(self.style.SUCCESS('Bilingual import completed!'))
