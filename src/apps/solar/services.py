import requests
import logging

logger = logging.getLogger(__name__)

def get_pvgis_data(lat, lon, peak_power, angle=35, aspect=0):
    """
    Consulta la API de PVGIS (v5.3) para obtener la generación solar estimada.
    
    lat, lon: Coordenadas
    peak_power: kWp instalados estimados
    angle: Inclinación (0-90)
    aspect: Orientación (-180 a 180, donde 0 es Sur)
    """
    url = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
    params = {
        'lat': lat,
        'lon': lon,
        'peakpower': peak_power,
        'loss': 14, # Pérdidas estándar del sistema (14%)
        'mountingplace': 'building',
        'angle': angle,
        'aspect': aspect,
        'outputformat': 'json'
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Extraemos los datos de generación anual y mensual
        outputs = data.get('outputs', {})
        totals = outputs.get('totals', {}).get('fixed', {})
        monthly = outputs.get('monthly', {}).get('fixed', [])
        
        return {
            'annual_kwh': totals.get('E_y'),
            'monthly_data': [m.get('E_m') for m in monthly],
            'meta': data.get('inputs', {})
        }
        
    except Exception as e:
        logger.error(f"Error consultando PVGIS para {lat}, {lon}: {e}")
        return None

def estimate_peak_power(area_m2, efficiency=0.15):
    """
    Estima la potencia pico instalable basada en el área útil del tejado.
    Considera un 15% de eficiencia por defecto (150W por m2).
    """
    # Usualmente se asume que solo el 60-70% del área es utilizable por obstáculos
    usable_area = area_m2 * 0.7 
    return usable_area * efficiency
