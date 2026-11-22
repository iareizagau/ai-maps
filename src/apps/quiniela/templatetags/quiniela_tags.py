"""Filtros de plantilla de la quiniela.

LANGUAGE_CODE='eu' formatea 0.53 como "0,53": para estilos CSS hace falta el
punto, así que estos filtros devuelven cadenas ya formateadas.
"""

from django import template

register = template.Library()


@register.filter
def pct(valor, decimales=0):
    """0.534 → '53 %' (texto visible)."""
    if valor is None:
        return "—"
    return f"{float(valor) * 100:.{int(decimales)}f} %"


@register.filter
def css_pct(valor):
    """0.534 → '53.4%' (para style="width: …")."""
    if valor is None:
        return "0%"
    return f"{max(0.0, min(1.0, float(valor))) * 100:.1f}%"


@register.filter
def get_item(diccionario, clave):
    if not diccionario:
        return None
    return diccionario.get(clave, diccionario.get(str(clave)))
