"""TCO calculation services for the `advisor` module.

PROPUESTA.md §3.1: jurado teclea CP + vehículo actual/objetivo + km/año →
recibe coste total, payback, CO₂ evitado, breakdown de costes y mapa de
cargadores a 5 km del centroide.

La función `calculate_tco_quote` es pura — entrada Python, salida dict
(o pydantic via schemas). Fácil de testear, fácil de cambiar fuentes.

Tests objetivo: precisión ±5% vs valor de mercado real (ver tests/).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from apps.mubil.data import cp_centroids, fuel_ingest, pvpc_ingest
from apps.mubil.data.price_defaults import (
    CO2_KG_PER_KWH_MIX_ES,
    CO2_KG_PER_LITRE_DIESEL,
    CO2_KG_PER_LITRE_GASOLINA,
    DEFAULT_INSURANCE_EUR_YEAR_EV,
    DEFAULT_INSURANCE_EUR_YEAR_ICE,
    DEFAULT_MAINTENANCE_EUR_YEAR_EV,
    DEFAULT_MAINTENANCE_EUR_YEAR_ICE,
    DEFAULT_TAX_EUR_YEAR_EV,
    DEFAULT_TAX_EUR_YEAR_ICE,
    WALLBOX_CAPEX_EUR,
)
from apps.mubil.models import ChargingStation, Vehicle

from .charging_mix import ChargingMix
from .incentives import IncentivesBreakdown, compute_incentives


@dataclass(frozen=True)
class CostBreakdown:
    energy: Decimal
    maintenance: Decimal
    insurance: Decimal
    taxes: Decimal

    @property
    def total(self) -> Decimal:
        return self.energy + self.maintenance + self.insurance + self.taxes


@dataclass(frozen=True)
class TCOQuote:
    cp: str
    cp_name: Optional[str]
    km_year: int
    years_horizon: int
    vehicle_current: Vehicle
    vehicle_target: Vehicle
    breakdown_current: CostBreakdown
    breakdown_target: CostBreakdown
    co2_kg_year_current: Decimal
    co2_kg_year_target: Decimal
    payback_years: Optional[Decimal]
    nearby_chargers: list[ChargingStation]
    subvencion_eur: Decimal = Decimal("0")
    motorway_pct: Optional[float] = None
    nacional_pct: Optional[float] = None
    urban_pct: Optional[float] = None
    charging_mix: Optional[ChargingMix] = None
    weighted_charging_eur_kwh: Optional[Decimal] = None
    incentives: Optional[IncentivesBreakdown] = None
    wallbox_capex_eur: Decimal = Decimal("0")


# ------------------------------------------------------------------ helpers


def _is_electric(v: Vehicle) -> bool:
    return v.propulsion == Vehicle.Propulsion.BEV


def _is_diesel(v: Vehicle) -> bool:
    return v.propulsion == Vehicle.Propulsion.DIESEL


def _annual_energy_cost(
    vehicle: Vehicle,
    km_year: int,
    night_charging: bool,
    *,
    postal_code: Optional[str] = None,
    motorway_pct: Optional[float] = None,
    nacional_pct: Optional[float] = None,
    urban_pct: Optional[float] = None,
    charging_mix: Optional[ChargingMix] = None,
) -> Decimal:
    """Coste anual de energía (€) en función del vehículo, km, régimen y perfil de vía (3 vías).

    Para rutas geolocalizadas, adapta el consumo en función del tipo de vía:
      - EV: −20% en ciudad (0.80), +25% en autovía (1.25), −5% en nacional (0.95).
      - ICE/combustión: +25% en ciudad (1.25), −15% en autovía (0.85), −5% en nacional (0.95).

    Para EV, si se pasa `charging_mix`, el precio se calcula ponderando los
    cuatro canales (casa / trabajo / pública AC / pública DC). Si no, se
    cae al binario `night_charging` legacy.
    """
    km = Decimal(km_year)

    if motorway_pct is not None or nacional_pct is not None:
        mw = Decimal(motorway_pct or 0) / Decimal("100")
        nac = Decimal(nacional_pct or 0) / Decimal("100")

        # Si urban_pct no está definido, lo estimamos del residuo
        if urban_pct is not None:
            urb = Decimal(urban_pct) / Decimal("100")
        else:
            urb = Decimal("1") - mw - nac

        if _is_electric(vehicle):
            efficiency_multiplier = (Decimal("0.80") * urb) + (Decimal("1.25") * mw) + (Decimal("0.95") * nac)
        else:
            efficiency_multiplier = (Decimal("1.25") * urb) + (Decimal("0.85") * mw) + (Decimal("0.95") * nac)
    else:
        efficiency_multiplier = Decimal("1")

    if _is_electric(vehicle):
        kwh_100 = vehicle.consumption_kwh_100km or Decimal("17.0")
        kwh = (kwh_100 * km * efficiency_multiplier) / Decimal("100")
        if charging_mix is not None:
            price = charging_mix.weighted_price_eur_kwh(night_charging=night_charging)
        else:
            price = pvpc_ingest.current_price_eur_kwh(night_charging=night_charging)
        return (kwh * price).quantize(Decimal("0.01"))

    l_100 = vehicle.consumption_l_100km or Decimal("6.0")
    litres = (l_100 * km * efficiency_multiplier) / Decimal("100")
    fuel_key = "gasoleo_a" if _is_diesel(vehicle) else "gasolina_95_e5"
    price = fuel_ingest.current_price_eur_l(fuel_key=fuel_key, postal_code=postal_code)
    return (litres * price).quantize(Decimal("0.01"))


def _annual_co2_kg(
    vehicle: Vehicle, 
    km_year: int,
    motorway_pct: Optional[float] = None,
    nacional_pct: Optional[float] = None,
    urban_pct: Optional[float] = None,
) -> Decimal:
    """Emisiones tank-to-wheel + well-to-tank con factor de eficiencia por 3 tipos de vía."""
    km = Decimal(km_year)
    
    if motorway_pct is not None or nacional_pct is not None:
        mw = Decimal(motorway_pct or 0) / Decimal("100")
        nac = Decimal(nacional_pct or 0) / Decimal("100")
        if urban_pct is not None:
            urb = Decimal(urban_pct) / Decimal("100")
        else:
            urb = Decimal("1") - mw - nac
            
        if _is_electric(vehicle):
            efficiency_multiplier = (Decimal("0.80") * urb) + (Decimal("1.25") * mw) + (Decimal("0.95") * nac)
        else:
            efficiency_multiplier = (Decimal("1.25") * urb) + (Decimal("0.85") * mw) + (Decimal("0.95") * nac)
    else:
        efficiency_multiplier = Decimal("1")

    if _is_electric(vehicle):
        kwh_100 = vehicle.consumption_kwh_100km or Decimal("17.0")
        kwh = (kwh_100 * km * efficiency_multiplier) / Decimal("100")
        return (kwh * CO2_KG_PER_KWH_MIX_ES).quantize(Decimal("0.1"))
        
    l_100 = vehicle.consumption_l_100km or Decimal("6.0")
    litres = (l_100 * km * efficiency_multiplier) / Decimal("100")
    factor = CO2_KG_PER_LITRE_DIESEL if _is_diesel(vehicle) else CO2_KG_PER_LITRE_GASOLINA
    return (litres * factor).quantize(Decimal("0.1"))


def _breakdown(
    vehicle: Vehicle,
    km_year: int,
    years_horizon: int,
    night_charging: bool,
    *,
    postal_code: Optional[str] = None,
    motorway_pct: Optional[float] = None,
    nacional_pct: Optional[float] = None,
    urban_pct: Optional[float] = None,
    charging_mix: Optional[ChargingMix] = None,
) -> CostBreakdown:
    horizon = Decimal(years_horizon)
    energy = _annual_energy_cost(
        vehicle, km_year, night_charging, postal_code=postal_code,
        motorway_pct=motorway_pct, nacional_pct=nacional_pct, urban_pct=urban_pct,
        charging_mix=charging_mix,
    ) * horizon
    if _is_electric(vehicle):
        maint = DEFAULT_MAINTENANCE_EUR_YEAR_EV * horizon
        insur = DEFAULT_INSURANCE_EUR_YEAR_EV * horizon
        taxes = DEFAULT_TAX_EUR_YEAR_EV * horizon
    else:
        maint = DEFAULT_MAINTENANCE_EUR_YEAR_ICE * horizon
        insur = DEFAULT_INSURANCE_EUR_YEAR_ICE * horizon
        taxes = DEFAULT_TAX_EUR_YEAR_ICE * horizon
    return CostBreakdown(
        energy=energy.quantize(Decimal("0.01")),
        maintenance=maint.quantize(Decimal("0.01")),
        insurance=insur.quantize(Decimal("0.01")),
        taxes=taxes.quantize(Decimal("0.01")),
    )


def _payback_years(
    current: Vehicle,
    target: Vehicle,
    annual_savings: Decimal,
    subvencion_eur: Decimal = Decimal("0"),
    wallbox_capex_eur: Decimal = Decimal("0"),
) -> Optional[Decimal]:
    if not current.price_eur or not target.price_eur or annual_savings <= 0:
        return None
    delta_price = (
        Decimal(target.price_eur - current.price_eur)
        + wallbox_capex_eur
        - subvencion_eur
    )
    if delta_price <= 0:
        return Decimal("0")
    return (delta_price / annual_savings).quantize(Decimal("0.1"))


def _nearby_chargers(cp: str, radius_km: float = 5.0, limit: int = 25) -> list[ChargingStation]:
    centroid = cp_centroids.lookup(cp)
    if centroid is None:
        return []
    lat, lon, _name = centroid
    qs = ChargingStation.objects.nearby(longitude=lon, latitude=lat, radius_km=radius_km)
    return list(qs[:limit])


# ------------------------------------------------------------------ public API


def calculate_tco_quote(
    *,
    cp: str,
    km_year: int,
    vehicle_current_id: int,
    vehicle_target_id: int,
    years_horizon: int = 10,
    night_charging: bool = False,
    subvencion_eur: int = 0,
    motorway_pct: Optional[float] = None,
    nacional_pct: Optional[float] = None,
    urban_pct: Optional[float] = None,
    profile: str = "particular",
    scrapping: bool = False,
    wallbox_state: str = "installed",
    home_pct: Optional[int] = None,
    work_pct: Optional[int] = None,
    public_ac_pct: Optional[int] = None,
    public_dc_pct: Optional[int] = None,
    subvencion_override_eur: Optional[int] = None,
) -> TCOQuote:
    """Calcula la comparativa TCO para el `advisor`.

    Si se pasan los porcentajes del mix de carga, el coste energético del
    EV se computa ponderando los cuatro canales (casa/trabajo/AC/DC). Si
    no, se mantiene el binario `night_charging` legacy.

    `subvencion_eur` es legacy y queda como total alternativo. Si se pasa
    `profile`/`scrapping`/`wallbox_state` se calculan los incentivos
    automáticamente y `subvencion_eur` se ignora a menos que
    `subvencion_override_eur` esté presente.
    """
    if not (1_000 <= km_year <= 60_000):
        raise ValueError(f"km_year fuera de rango (1.000-60.000): {km_year}")
    if not (1 <= years_horizon <= 20):
        raise ValueError(f"years_horizon fuera de rango (1-20): {years_horizon}")
    if not (0 <= subvencion_eur <= 30_000):
        raise ValueError(f"subvencion_eur fuera de rango (0-30.000): {subvencion_eur}")
    if profile not in ("particular", "autonomo", "empresa"):
        raise ValueError(f"profile inválido: {profile}")
    if wallbox_state not in ("installed", "needs_install", "no_home"):
        raise ValueError(f"wallbox_state inválido: {wallbox_state}")

    current = Vehicle.objects.get(pk=vehicle_current_id)
    target = Vehicle.objects.get(pk=vehicle_target_id)

    # ----- Mix de carga (sólo si se aportan los 4 porcentajes) -----
    mix: Optional[ChargingMix] = None
    if home_pct is not None and work_pct is not None \
            and public_ac_pct is not None and public_dc_pct is not None:
        mix = ChargingMix.normalized(home_pct, work_pct, public_ac_pct, public_dc_pct)

    # ----- Breakdowns -----
    bd_current = _breakdown(
        current, km_year, years_horizon, night_charging, postal_code=cp,
        motorway_pct=motorway_pct, nacional_pct=nacional_pct, urban_pct=urban_pct,
    )
    bd_target = _breakdown(
        target, km_year, years_horizon, night_charging, postal_code=cp,
        motorway_pct=motorway_pct, nacional_pct=nacional_pct, urban_pct=urban_pct,
        charging_mix=mix,
    )

    # ----- Ahorro anual (energía + opex constante) -----
    annual_savings = (
        _annual_energy_cost(current, km_year, night_charging, postal_code=cp,
                            motorway_pct=motorway_pct, nacional_pct=nacional_pct, urban_pct=urban_pct)
        + (DEFAULT_MAINTENANCE_EUR_YEAR_ICE if not _is_electric(current) else DEFAULT_MAINTENANCE_EUR_YEAR_EV)
        + (DEFAULT_INSURANCE_EUR_YEAR_ICE if not _is_electric(current) else DEFAULT_INSURANCE_EUR_YEAR_EV)
        + (DEFAULT_TAX_EUR_YEAR_ICE if not _is_electric(current) else DEFAULT_TAX_EUR_YEAR_EV)
    ) - (
        _annual_energy_cost(target, km_year, night_charging, postal_code=cp,
                            motorway_pct=motorway_pct, nacional_pct=nacional_pct, urban_pct=urban_pct,
                            charging_mix=mix)
        + (DEFAULT_MAINTENANCE_EUR_YEAR_ICE if not _is_electric(target) else DEFAULT_MAINTENANCE_EUR_YEAR_EV)
        + (DEFAULT_INSURANCE_EUR_YEAR_ICE if not _is_electric(target) else DEFAULT_INSURANCE_EUR_YEAR_EV)
        + (DEFAULT_TAX_EUR_YEAR_ICE if not _is_electric(target) else DEFAULT_TAX_EUR_YEAR_EV)
    )

    # ----- Wallbox CAPEX (sólo si necesita instalar y target es BEV) -----
    needs_wallbox = wallbox_state == "needs_install" and _is_electric(target)
    wallbox_capex = WALLBOX_CAPEX_EUR if needs_wallbox else Decimal("0")

    # ----- Incentivos: auto o override -----
    incentives = compute_incentives(
        profile=profile,
        cp=cp,
        vehicle_price_eur=target.price_eur,
        scrapping=scrapping,
        needs_wallbox=needs_wallbox,
        years_horizon=years_horizon,
    )
    if subvencion_override_eur is not None and subvencion_override_eur >= 0:
        total_subv = Decimal(subvencion_override_eur)
    else:
        total_subv = incentives.total_lump_sum_eur

    centroid = cp_centroids.lookup(cp)
    cp_name = centroid[2] if centroid else None

    weighted_price = (
        mix.weighted_price_eur_kwh(night_charging=night_charging)
        if mix is not None
        else None
    )

    return TCOQuote(
        cp=cp,
        cp_name=cp_name,
        km_year=km_year,
        years_horizon=years_horizon,
        vehicle_current=current,
        vehicle_target=target,
        breakdown_current=bd_current,
        breakdown_target=bd_target,
        co2_kg_year_current=_annual_co2_kg(current, km_year, motorway_pct=motorway_pct, nacional_pct=nacional_pct, urban_pct=urban_pct),
        co2_kg_year_target=_annual_co2_kg(target, km_year, motorway_pct=motorway_pct, nacional_pct=nacional_pct, urban_pct=urban_pct),
        payback_years=_payback_years(
            current, target, annual_savings, total_subv, wallbox_capex,
        ),
        nearby_chargers=_nearby_chargers(cp),
        subvencion_eur=total_subv,
        motorway_pct=motorway_pct,
        nacional_pct=nacional_pct,
        urban_pct=urban_pct,
        charging_mix=mix,
        weighted_charging_eur_kwh=weighted_price,
        incentives=incentives,
        wallbox_capex_eur=wallbox_capex,
    )


# ------------------------------------------------------------------ Commute Routing


def get_commute_route(start_lng: float, start_lat: float, end_lng: float, end_lat: float) -> dict:
    """
    Calcula la ruta óptima entre origen y destino para el commute planner.
    Usa pgRouting sobre la tabla `ways` con los tags drivable.
    Si pgRouting falla o no encuentra nodos, aplica un fallback de OSRM en línea.
    Si OSRM falla, recurre a una estimación por línea recta con un factor de 1.27.
    """
    from django.db import connection
    import json
    import urllib.request
    import urllib.error
    import re
    
    # 1. Encontrar nodos más cercanos
    start_node = find_nearest_drivable_node(start_lng, start_lat)
    end_node = find_nearest_drivable_node(end_lng, end_lat)
    
    def fallback_route(reason=""):
        # Intenta OSRM online primero para devolver el trazado de carreteras exacto con pasos detallados
        try:
            url = f"http://router.project-osrm.org/route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}?overview=full&geometries=geojson&steps=true"
            req = urllib.request.Request(url, headers={'User-Agent': 'MubilTCOAdvisor/1.0'})
            with urllib.request.urlopen(req, timeout=3.5) as response:
                res_data = json.loads(response.read().decode('utf-8'))
            
            if res_data.get("code") == "Ok" and res_data.get("routes"):
                route = res_data["routes"][0]
                distance_m = route["distance"]
                distance_km = distance_m / 1000.0
                
                # Clasificar cada tramo (step) por nombre y velocidad
                autopista_m = 0
                nacional_m = 0
                urbano_m = 0
                
                steps = route["legs"][0]["steps"]
                for step in steps:
                    name = step.get("name", "")
                    dist = step.get("distance", 0)
                    dur = step.get("duration", 0)
                    
                    speed_kmh = (dist / dur) * 3.6 if dur > 0 else 0
                    name_lower = name.lower()
                    
                    is_autopista = (
                        speed_kmh >= 85.0 or
                        any(x in name_lower for x in ["autobia", "autobidea", "autovía", "autopista"]) or
                        re.match(r'^(A-|AP-)\d+', name)
                    )
                    
                    is_nacional = False
                    if not is_autopista:
                        is_nacional = (
                            (speed_kmh >= 50.0 and speed_kmh < 85.0) or
                            any(x in name_lower for x in ["variante", "saihesbidea", "enlace", "acceso", "korridorea", "corredor"]) or
                            re.match(r'^(N-|GI-|BI-|VI-)\d+', name)
                        )
                    
                    if is_autopista:
                        autopista_m += dist
                    elif is_nacional:
                        nacional_m += dist
                    else:
                        urbano_m += dist
                
                total_classified_m = autopista_m + nacional_m + urbano_m
                if total_classified_m > 0:
                    motorway_pct = (autopista_m / total_classified_m) * 100.0
                    nacional_pct = (nacional_m / total_classified_m) * 100.0
                    urban_pct = (urbano_m / total_classified_m) * 100.0
                else:
                    motorway_pct = 50.0
                    nacional_pct = 25.0
                    urban_pct = 25.0
                
                route_geojson = {
                    "type": "FeatureCollection",
                    "features": [{
                        "type": "Feature",
                        "geometry": route["geometry"],
                        "properties": {
                            "name": "Ruta por Carretera (OSRM)",
                            "highway_type": "motorway" if motorway_pct > 50 else "residential",
                            "length_m": distance_m
                        }
                    }],
                    "metadata": {
                        "total_distance_m": distance_m,
                        "note": "OSRM Routing successful"
                    }
                }
                
                return {
                    "distance_km": round(distance_km, 2),
                    "motorway_pct": round(motorway_pct, 1),
                    "nacional_pct": round(nacional_pct, 1),
                    "urban_pct": round(urban_pct, 1),
                    "route_geojson": route_geojson
                }
        except Exception as osrm_err:
            # Si falla OSRM, usa el fallback geométrico local offline
            reason = f"{reason} | OSRM failed: {str(osrm_err)}"
            
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT ST_Distance(
                    ST_SetSRID(ST_Point(%s, %s), 4326)::geography,
                    ST_SetSRID(ST_Point(%s, %s), 4326)::geography
                )
            """, [start_lng, start_lat, end_lng, end_lat])
            row = cursor.fetchone()
            distance_m = row[0] if (row and row[0] is not None) else 0.0
        
        # Sinuosidad estándar 1.27
        distance_km = (distance_m * 1.27) / 1000.0
        
        route_geojson = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[start_lng, start_lat], [end_lng, end_lat]]
                },
                "properties": {
                    "name": "Trayecto Estimado (Sinuosidad 1.27)",
                    "highway_type": "motorway",
                    "length_m": distance_m * 1.27
                }
            }],
            "metadata": {
                "total_distance_m": distance_m * 1.27,
                "note": f"Fallback applied: {reason}"
            }
        }
        
        return {
            "distance_km": round(distance_km, 2),
            "motorway_pct": 60.0,
            "nacional_pct": 20.0,
            "urban_pct": 20.0,
            "route_geojson": route_geojson
        }

    if not start_node or not end_node:
        return fallback_route("Nodos no encontrados en la red vial")
        
    if start_node == end_node:
        return fallback_route("Puntos demasiado cercanos")

    # Bounding box dinámico ampliado
    lon_dist = abs(end_lng - start_lng)
    lat_dist = abs(end_lat - start_lat)
    buffer = max(max(lon_dist, lat_dist) * 1.5, 0.2)

    min_lon = min(start_lng, end_lng) - buffer
    max_lon = max(start_lng, end_lng) + buffer
    min_lat = min(start_lat, end_lat) - buffer
    max_lat = max(start_lat, end_lat) + buffer

    bbox_filter = (
        f"AND the_geom && ST_MakeEnvelope({min_lon}, {min_lat}, {max_lon}, {max_lat}, 4326)"
    )

    drivable_tags_sql = (
        "SELECT tag_id FROM configuration WHERE tag_value IN ("
        "''motorway'', ''motorway_link'', ''trunk'', ''trunk_link'', "
        "''primary'', ''primary_link'', ''secondary'', ''secondary_link'', "
        "''tertiary'', ''tertiary_link'', ''residential'', ''unclassified'', ''service''"
        ")"
    )

    query = f"""
        SELECT
            ST_AsGeoJSON(ways.the_geom) as geometry,
            ways.name,
            di.cost,
            di.agg_cost,
            c.tag_value as highway_type,
            ways.length_m
        FROM pgr_dijkstra(
            'SELECT gid as id, source, target, 
                    CASE WHEN length_m <= 0 THEN 0.1 ELSE length_m END as cost,
                    CASE WHEN length_m <= 0 THEN 0.1 ELSE length_m END as reverse_cost 
             FROM ways
             WHERE tag_id IN ({drivable_tags_sql}) {bbox_filter}',
            %s, %s, directed := false
        ) AS di
        JOIN ways ON di.edge = ways.gid
        JOIN configuration c ON ways.tag_id = c.tag_id
        ORDER BY di.seq
    """

    try:
        with connection.cursor() as cursor:
            cursor.execute(query, [start_node, end_node])
            rows = cursor.fetchall()
            
        if not rows:
            return fallback_route("No hay conexión topológica en la red OSM")
            
        features = []
        total_distance_m = 0.0
        autopista_m = 0.0
        nacional_m = 0.0
        urbano_m = 0.0
        
        high_speed_types = {"motorway", "trunk", "motorway_link", "trunk_link"}
        secondary_types = {"primary", "primary_link", "secondary", "secondary_link"}
        
        for row in rows:
            length_m = row[5] or 0.0
            total_distance_m += length_m
            hw_type = row[4]
            
            if hw_type in high_speed_types:
                autopista_m += length_m
            elif hw_type in secondary_types:
                nacional_m += length_m
            else:
                urbano_m += length_m
                
            features.append({
                "type": "Feature",
                "geometry": json.loads(row[0]),
                "properties": {
                    "name": row[1],
                    "highway_type": hw_type,
                    "length_m": length_m
                }
            })
            
        if total_distance_m > 0:
            motorway_pct = (autopista_m / total_distance_m) * 100.0
            nacional_pct = (nacional_m / total_distance_m) * 100.0
            urban_pct = (urbano_m / total_distance_m) * 100.0
        else:
            motorway_pct = 50.0
            nacional_pct = 25.0
            urban_pct = 25.0
            
        route_geojson = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "total_distance_m": total_distance_m,
                "start_node": start_node,
                "end_node": end_node
            }
        }
        
        return {
            "distance_km": round(total_distance_m / 1000.0, 2),
            "motorway_pct": round(motorway_pct, 1),
            "nacional_pct": round(nacional_pct, 1),
            "urban_pct": round(urban_pct, 1),
            "route_geojson": route_geojson
        }
        
    except Exception as e:
        return fallback_route(f"Error en consulta pgRouting: {str(e)}")


def find_nearest_drivable_node(lon: float, lat: float) -> Optional[int]:
    from django.db import connection
    query = """
        WITH nearest_edge AS (
            SELECT source, target 
            FROM ways
            WHERE tag_id IN (
                SELECT tag_id FROM configuration WHERE tag_value IN (
                    'motorway', 'motorway_link', 'trunk', 'trunk_link', 
                    'primary', 'primary_link', 'secondary', 'secondary_link', 
                    'tertiary', 'tertiary_link', 'residential', 'unclassified', 'service'
                )
            )
            ORDER BY the_geom <-> ST_SetSRID(ST_Point(%s, %s), 4326)
            LIMIT 1
        )
        SELECT v.id 
        FROM ways_vertices_pgr v
        JOIN nearest_edge e ON v.id = e.source OR v.id = e.target
        ORDER BY v.the_geom <-> ST_SetSRID(ST_Point(%s, %s), 4326)
        LIMIT 1
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, [lon, lat, lon, lat])
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception:
        return None

