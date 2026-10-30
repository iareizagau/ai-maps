from apps.amenabar.services import (
    _classify_element,
    _classify_estado,
    _extract_percent,
)


def test_classify_estado_percent_sold_is_en_curso():
    assert _classify_estado("80% vendido") == "EN_CURSO"


def test_classify_estado_100_percent_is_vendida():
    assert _classify_estado("100% vendido") == "VENDIDA"


def test_classify_estado_proxima():
    assert _classify_estado("Próxima promoción") == "PROXIMA"


def test_classify_estado_default_is_en_venta():
    assert _classify_estado("Nueva promoción") == "EN_VENTA"


def test_extract_percent():
    assert _extract_percent("80% vendido") == 80
    assert _extract_percent("sin porcentaje") is None
    assert _extract_percent("200% vendido") is None  # fuera de rango


def test_classify_element_pharmacy():
    cat, sub = _classify_element({"amenity": "pharmacy", "name": "Botika"})
    assert cat == "SALUD"
    assert sub == "pharmacy"


def test_classify_element_buyer_essentials():
    assert _classify_element({"shop": "supermarket"}) == ("COMPRAS", "supermarket")
    assert _classify_element({"amenity": "school"}) == ("EDUCACION", "school")


def test_classify_element_pitch_is_no_longer_collected():
    assert _classify_element({"leisure": "pitch"}) is None


def test_classify_element_unknown_returns_none():
    assert _classify_element({"random": "nope"}) is None
