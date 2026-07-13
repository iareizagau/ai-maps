"""Shared schemas for mubil. Sub-module specific schemas live in
`advisor/schemas.py`, `ask/schemas.py`, etc. See PROPUESTA.md §3.
"""


from ninja import Schema


class HealthOut(Schema):
    status: str
    module: str
    version: str = "0.1.0"


class VehicleOut(Schema):
    id: int
    make: str
    model: str
    year: int
    propulsion: str
    battery_kwh: float | None = None
    range_wltp_km: int | None = None
    consumption_kwh_100km: float | None = None
    consumption_l_100km: float | None = None
    price_eur: int | None = None
