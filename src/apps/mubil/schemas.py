"""Shared schemas for mubil. Sub-module specific schemas live in
`advisor/schemas.py`, `ask/schemas.py`, etc. See PROPUESTA.md §3.
"""

from typing import Optional

from ninja import Schema


class HealthOut(Schema):
    status: str
    module: str
    version: str = '0.1.0'


class VehicleOut(Schema):
    id: int
    make: str
    model: str
    year: int
    propulsion: str
    battery_kwh: Optional[float] = None
    range_wltp_km: Optional[int] = None
    consumption_kwh_100km: Optional[float] = None
    consumption_l_100km: Optional[float] = None
    price_eur: Optional[int] = None
