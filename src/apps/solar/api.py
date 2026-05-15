from ninja import Router
from typing import List
from .models import Building, SolarPotential
from .selectors import get_buildings_in_bbox
from .services import get_pvgis_data, estimate_peak_power
from django.contrib.gis.geos import Polygon

router = Router(tags=["solar"])

@router.get("/buildings")
def list_buildings(request, bbox: str):
    """
    Obtiene edificios 3D con su potencial solar en un área.
    bbox: min_lon,min_lat,max_lon,max_lat
    """
    try:
        parts = [x for x in bbox.split(',') if x.strip()]
        if len(parts) != 4:
            return {"error": "Invalid bbox format. Expected 4 coordinates."}
            
        coords = [float(x) for x in parts]
        buildings = get_buildings_in_bbox(coords)[:50] # Límite para el prototipo
        
        features = []
        for b in buildings:
            has_solar = hasattr(b, 'potential')
            potential_data = {}
            if has_solar:
                potential_data = {
                    "annual_generation": b.potential.annual_generation_kwh,
                    "peak_power": b.potential.peak_power_kwp,
                }
            
            features.append({
                "type": "Feature",
                "id": b.osm_id,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": b.geom.coords
                },
                "properties": {
                    "name": b.name or "Edificio",
                    "height": b.height or 9.0,
                    "building_type": b.building_type,
                    "color": "#fbbf24" if has_solar else "#ffffff", # Dorado para analizados, blanco para el resto
                    "solar": potential_data
                }
            })
            
        return {
            "type": "FeatureCollection",
            "features": features
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/calculate/{osm_id}")
def trigger_calculation(request, osm_id: int):
    """
    Fuerza el cálculo de PVGIS para un edificio específico.
    """
    try:
        building = Building.objects.get(osm_id=osm_id)
        
        # Obtenemos centroide para PVGIS
        centroid = building.geom.centroid
        
        # Estimar potencia pico si no tiene
        if not building.roof_area:
            # Cálculo simple de área en metros
            building.roof_area = building.geom.transform(3857, clone=True).area
            building.save()
            
        peak_power = estimate_peak_power(building.roof_area)
        
        # Llamada a PVGIS
        data = get_pvgis_data(centroid.y, centroid.x, peak_power)
        
        if data:
            potential, created = SolarPotential.objects.update_or_create(
                building=building,
                defaults={
                    'annual_generation_kwh': data['annual_kwh'],
                    'monthly_generation_json': data['monthly_data'],
                    'peak_power_kwp': peak_power
                }
            )
            return {"status": "success", "annual_kwh": data['annual_kwh']}
        
        return {"status": "error", "message": "PVGIS API failed"}
        
    except Building.DoesNotExist:
        return {"status": "error", "message": "Building not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
@router.get("/building-at")
def get_building_at(request, lat: float, lon: float):
    """
    Busca el edificio en una coordenada específica.
    """
    from django.contrib.gis.geos import Point
    point = Point(lon, lat, srid=4326)
    
    building = Building.objects.filter(geom__intersects=point).select_related('potential').first()
    
    if not building:
        return {"error": "No building found at this location"}
        
    potential_data = {}
    if hasattr(building, 'potential'):
        potential = building.potential
        potential_data = {
            "annual_generation": potential.annual_generation_kwh,
            "peak_power": potential.peak_power_kwp,
            "monthly_data": potential.monthly_generation_json,
            "kpis": {
                "co2_offset": round(potential.annual_generation_kwh * 0.25), # 0.25kg/kWh approx
                "annual_savings": round(potential.annual_generation_kwh * 0.18), # 0.18€/kWh approx
                "roi_years": 6.5 # Estimación fija para el prototipo
            }
        }
        
    return {
        "id": building.osm_id,
        "name": building.name or "Edificio",
        "height": building.height,
        "roof_area": round(building.roof_area) if building.roof_area else None,
        "solar": potential_data
    }
