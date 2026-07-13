"""Postal-code centroids for the `advisor` demo.

Hardcoded for F0 (la demo del jurado teclea un CP fijo). Cubre 10 CPs de
Gipuzkoa y los principales del entorno. Coordenadas WGS84 (lat, lon).

Sustituir por geocoding real (Nominatim sobre OSM Euskadi) en F2/F3 una
vez tengamos un servicio interno estable. Mantener este fichero como
fallback offline para la defensa.
"""


CP_CENTROIDS: dict[str, tuple[float, float, str]] = {
    # Gipuzkoa — núcleos principales
    "20018": (43.300, -2.000, "Donostia / San Sebastián (centro)"),
    "20011": (43.310, -1.985, "Donostia (Egia)"),
    "20100": (43.317, -1.901, "Errenteria"),
    "20200": (43.050, -2.197, "Beasain"),
    "20300": (43.262, -1.787, "Irun"),
    "20400": (43.135, -2.106, "Tolosa"),
    "20500": (43.187, -2.471, "Arrasate / Mondragón"),
    "20600": (43.187, -2.469, "Eibar"),
    "20700": (43.180, -2.469, "Zumarraga"),
    "20800": (43.282, -2.169, "Zarautz"),
    # Bizkaia capital — útil para destino EV
    "48001": (43.262, -2.935, "Bilbao (Abando)"),
    # Araba capital
    "01001": (42.846, -2.672, "Vitoria-Gasteiz"),
}


def lookup(cp: str) -> tuple[float, float, str] | None:
    """Return (lat, lon, name) for a known CP, or None if unknown."""
    return CP_CENTROIDS.get(cp.strip())
