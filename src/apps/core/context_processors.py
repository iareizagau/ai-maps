from .models import AppRegistry

def app_config(request):
    """
    Detects the current app context based on the subdomain or path
    and injects the AppRegistry configuration.
    """
    host = request.get_host().split(':')[0] # Remove port if present
    
    # Simple detection logic. 
    # In production, we'd match against AppRegistry.domain
    # For now, we'll try to find by slug in the hostname
    slug = 'pintxos' # Default
    if 'sbk' in host: slug = 'sbk'
    elif 'kultur' in host: slug = 'kultur'
    elif 'bidaiak' in host: slug = 'bidaiak'
    
    try:
        current_app = AppRegistry.objects.get(slug=slug, is_active=True)
    except AppRegistry.DoesNotExist:
        # Fallback to a default or create a mock object
        current_app = {
            'name': 'Maps.eus',
            'primary_color': '#f97316',
            'secondary_color': '#84cc16',
            'font_family': "Inter",
            'hero_title': 'Euskal Herriko GIS Ekosistema',
            'hero_subtitle': 'Discover your territory with curated experts.',
            'has_reviews': True,
            'has_maps': True
        }

    return {
        'current_app': current_app
    }
