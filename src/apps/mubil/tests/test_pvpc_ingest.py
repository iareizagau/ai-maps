"""Tests for the PVPC ingest pipeline.

ESIOS HTTP is mocked — these tests do not hit api.esios.ree.es. To exercise
the live endpoint:  `python manage.py ingest_pvpc --hours 24 --dry-run`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings

from apps.mubil.data import esios_client, pvpc_ingest
from apps.mubil.models import EnergyPricePVPC

# Realistic ESIOS payload shape — `indicator.values[]` with ISO datetimes.
SAMPLE_PAYLOAD = {
    "indicator": {
        "id": 1001,
        "name": "Precio voluntario para el pequeño consumidor (PVPC) 2.0TD",
        "values": [
            # Madrid 2026-05-01 02:00 → P3 (valle), weekday but pre-08:00
            {
                "datetime": "2026-05-01T02:00:00.000+02:00",
                "value": 80.5,
                "geo_id": 8741,
                "geo_name": "España",
            },
            # Madrid 2026-05-01 11:00 → P1 (punta)
            {
                "datetime": "2026-05-01T11:00:00.000+02:00",
                "value": 145.2,
                "geo_id": 8741,
                "geo_name": "España",
            },
            # Madrid 2026-05-01 15:00 → P2 (llano)
            {
                "datetime": "2026-05-01T15:00:00.000+02:00",
                "value": 110.8,
                "geo_id": 8741,
                "geo_name": "España",
            },
            # Madrid 2026-05-02 11:00 → Saturday → P3 (weekend)
            {
                "datetime": "2026-05-02T11:00:00.000+02:00",
                "value": 70.0,
                "geo_id": 8741,
                "geo_name": "España",
            },
            # Malformed row — should be skipped, not crash
            {"datetime": None, "value": 99.9},
        ],
    }
}


def _mock_response(payload=None, status=200):
    r = mock.Mock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else SAMPLE_PAYLOAD
    r.raise_for_status = mock.Mock()
    return r


# ---------------------------------------------------------------- tariff classifier


class ClassifyTariffTests(TestCase):
    def test_weekday_morning_peak(self):
        # Madrid 11:00 on a Friday → P1
        ts = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)  # UTC 09:00 = Madrid 11:00 (CEST)
        self.assertEqual(pvpc_ingest.classify_tariff(ts), EnergyPricePVPC.Tariff.P1)

    def test_weekday_afternoon_flat(self):
        # Madrid 15:00 on a Friday → P2
        ts = datetime(2026, 5, 1, 13, 0, tzinfo=UTC)
        self.assertEqual(pvpc_ingest.classify_tariff(ts), EnergyPricePVPC.Tariff.P2)

    def test_weekday_night_valley(self):
        # Madrid 02:00 on a Friday → P3
        ts = datetime(2026, 5, 1, 0, 0, tzinfo=UTC)
        self.assertEqual(pvpc_ingest.classify_tariff(ts), EnergyPricePVPC.Tariff.P3)

    def test_weekend_always_valley(self):
        # Madrid 11:00 on a Saturday → P3 even though it would be P1 on a weekday
        ts = datetime(2026, 5, 2, 9, 0, tzinfo=UTC)
        self.assertEqual(pvpc_ingest.classify_tariff(ts), EnergyPricePVPC.Tariff.P3)


# ---------------------------------------------------------------- ESIOS client


@override_settings(ESIOS_TOKEN="fake-token-for-tests")
class FetchIndicatorTests(TestCase):
    @mock.patch("apps.mubil.data.esios_client.requests.get")
    def test_parses_values_and_normalizes_utc(self, get_mock):
        get_mock.return_value = _mock_response()

        values = esios_client.fetch_indicator(
            esios_client.INDICATOR_PVPC,
            start=datetime(2026, 5, 1, tzinfo=UTC),
            end=datetime(2026, 5, 2, tzinfo=UTC),
        )

        # Malformed row was dropped → 4 valid datapoints.
        self.assertEqual(len(values), 4)
        # All timestamps are UTC tz-aware.
        for v in values:
            self.assertEqual(v.timestamp.utcoffset().total_seconds(), 0)
        # Sorted ascending.
        self.assertEqual(
            [v.timestamp for v in values],
            sorted(v.timestamp for v in values),
        )

    @mock.patch("apps.mubil.data.esios_client.requests.get")
    def test_sends_token_header(self, get_mock):
        get_mock.return_value = _mock_response()

        esios_client.fetch_indicator(
            1001,
            start=datetime(2026, 5, 1, tzinfo=UTC),
            end=datetime(2026, 5, 2, tzinfo=UTC),
        )
        _, kwargs = get_mock.call_args
        self.assertEqual(kwargs["headers"]["x-api-key"], "fake-token-for-tests")

    @mock.patch("apps.mubil.data.esios_client.requests.get")
    def test_401_raises_esios_error(self, get_mock):
        get_mock.return_value = _mock_response(status=401)

        with self.assertRaises(esios_client.ESIOSError) as ctx:
            esios_client.fetch_indicator(
                1001,
                start=datetime(2026, 5, 1, tzinfo=UTC),
                end=datetime(2026, 5, 2, tzinfo=UTC),
            )
        self.assertIn("token", str(ctx.exception).lower())

    def test_naive_datetime_rejected(self):
        with self.assertRaises(esios_client.ESIOSError):
            esios_client.fetch_indicator(
                1001,
                start=datetime(2026, 5, 1),
                end=datetime(2026, 5, 2),
            )


@override_settings(ESIOS_TOKEN="")
class FetchIndicatorNoTokenTests(TestCase):
    def test_raises_when_token_missing(self):
        with self.assertRaises(esios_client.ESIOSError) as ctx:
            esios_client.fetch_indicator(
                1001,
                start=datetime(2026, 5, 1, tzinfo=UTC),
                end=datetime(2026, 5, 2, tzinfo=UTC),
            )
        self.assertIn("ESIOS_TOKEN", str(ctx.exception))


# ---------------------------------------------------------------- ingest orchestration


@override_settings(ESIOS_TOKEN="fake-token-for-tests")
class IngestWindowTests(TestCase):
    @mock.patch("apps.mubil.data.esios_client.requests.get")
    def test_creates_rows_with_classified_tariff(self, get_mock):
        get_mock.return_value = _mock_response()

        stats = pvpc_ingest.ingest_window(
            start=datetime(2026, 5, 1, tzinfo=UTC),
            end=datetime(2026, 5, 3, tzinfo=UTC),
        )

        self.assertEqual(stats.fetched, 4)
        self.assertEqual(stats.created, 4)
        self.assertEqual(stats.errors, 0)

        # Spot-check: weekend row is classified as P3 even at 11:00 local.
        sat = EnergyPricePVPC.objects.get(
            timestamp=datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
        )
        self.assertEqual(sat.tariff, EnergyPricePVPC.Tariff.P3)
        self.assertEqual(sat.price_eur_mwh, Decimal("70.000"))

    @mock.patch("apps.mubil.data.esios_client.requests.get")
    def test_idempotent_rerun_updates_existing(self, get_mock):
        get_mock.return_value = _mock_response()
        pvpc_ingest.ingest_window(
            start=datetime(2026, 5, 1, tzinfo=UTC),
            end=datetime(2026, 5, 3, tzinfo=UTC),
        )

        # Second run — same payload → 4 updates, 0 creates.
        stats = pvpc_ingest.ingest_window(
            start=datetime(2026, 5, 1, tzinfo=UTC),
            end=datetime(2026, 5, 3, tzinfo=UTC),
        )
        self.assertEqual(stats.created, 0)
        self.assertEqual(stats.updated, 4)
        self.assertEqual(EnergyPricePVPC.objects.count(), 4)

    @mock.patch("apps.mubil.data.esios_client.requests.get")
    def test_dry_run_makes_no_writes(self, get_mock):
        get_mock.return_value = _mock_response()

        stats = pvpc_ingest.ingest_window(
            start=datetime(2026, 5, 1, tzinfo=UTC),
            end=datetime(2026, 5, 3, tzinfo=UTC),
            dry_run=True,
        )

        self.assertEqual(stats.fetched, 4)
        self.assertEqual(stats.created, 0)
        self.assertEqual(EnergyPricePVPC.objects.count(), 0)

    @mock.patch("apps.mubil.data.esios_client.requests.get")
    def test_http_error_increments_errors_counter(self, get_mock):
        get_mock.return_value = _mock_response(status=401)

        stats = pvpc_ingest.ingest_window(
            start=datetime(2026, 5, 1, tzinfo=UTC),
            end=datetime(2026, 5, 3, tzinfo=UTC),
        )
        self.assertEqual(stats.fetched, 0)
        self.assertEqual(stats.errors, 1)
        self.assertEqual(EnergyPricePVPC.objects.count(), 0)


# ---------------------------------------------------------------- queries (advisor wiring)


def _seed_recent(*, tariff: str, prices_eur_mwh: list, hours_ago_each: list):
    """Helper: insert one EnergyPricePVPC row per (price, hours_ago) pair."""
    from datetime import datetime as _dt

    now = _dt.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
    for price, h in zip(prices_eur_mwh, hours_ago_each):
        EnergyPricePVPC.objects.create(
            timestamp=now - timedelta(hours=h),
            tariff=tariff,
            price_eur_mwh=Decimal(str(price)),
        )


class PVPCQueryTests(TestCase):
    def test_recent_avg_returns_none_when_table_empty(self):
        self.assertIsNone(pvpc_ingest.recent_avg_eur_kwh())

    def test_recent_avg_unit_conversion_mwh_to_kwh(self):
        # 200 €/MWh = 0.2 €/kWh
        _seed_recent(
            tariff=EnergyPricePVPC.Tariff.P1,
            prices_eur_mwh=[200, 200, 200],
            hours_ago_each=[1, 2, 3],
        )
        avg = pvpc_ingest.recent_avg_eur_kwh(tariff=EnergyPricePVPC.Tariff.P1)
        self.assertEqual(avg, Decimal("0.2000"))

    def test_recent_avg_filters_tariff(self):
        _seed_recent(
            tariff=EnergyPricePVPC.Tariff.P1,
            prices_eur_mwh=[200],
            hours_ago_each=[1],
        )
        _seed_recent(
            tariff=EnergyPricePVPC.Tariff.P3,
            prices_eur_mwh=[80],
            hours_ago_each=[1],
        )
        self.assertEqual(
            pvpc_ingest.recent_avg_eur_kwh(tariff=EnergyPricePVPC.Tariff.P1),
            Decimal("0.2000"),
        )
        self.assertEqual(
            pvpc_ingest.recent_avg_eur_kwh(tariff=EnergyPricePVPC.Tariff.P3),
            Decimal("0.0800"),
        )

    def test_recent_avg_excludes_rows_outside_window(self):
        _seed_recent(
            tariff=EnergyPricePVPC.Tariff.P1,
            prices_eur_mwh=[200, 1000],
            hours_ago_each=[1, 24 * 60],  # second row is 60 days old
        )
        # Default 30-day window → only the 1-hour-old row counts.
        avg = pvpc_ingest.recent_avg_eur_kwh(tariff=EnergyPricePVPC.Tariff.P1)
        self.assertEqual(avg, Decimal("0.2000"))

    def test_current_price_night_charging_uses_valle(self):
        _seed_recent(
            tariff=EnergyPricePVPC.Tariff.P3,
            prices_eur_mwh=[100],  # → 0.10 €/kWh
            hours_ago_each=[1],
        )
        _seed_recent(
            tariff=EnergyPricePVPC.Tariff.P1,
            prices_eur_mwh=[300],
            hours_ago_each=[1],
        )
        self.assertEqual(
            pvpc_ingest.current_price_eur_kwh(night_charging=True),
            Decimal("0.1000"),
        )

    def test_current_price_blended_average_when_not_night(self):
        _seed_recent(
            tariff=EnergyPricePVPC.Tariff.P1,
            prices_eur_mwh=[300],
            hours_ago_each=[1],
        )
        _seed_recent(
            tariff=EnergyPricePVPC.Tariff.P3,
            prices_eur_mwh=[100],
            hours_ago_each=[1],
        )
        # Unweighted blend = (300+100)/2 = 200 €/MWh = 0.20 €/kWh.
        self.assertEqual(
            pvpc_ingest.current_price_eur_kwh(night_charging=False),
            Decimal("0.2000"),
        )

    def test_current_price_falls_back_to_default_when_empty(self):
        from apps.mubil.data.price_defaults import (
            DEFAULT_PVPC_EUR_KWH,
            DEFAULT_PVPC_VALLE_EUR_KWH,
        )

        # No rows inserted at all.
        self.assertEqual(
            pvpc_ingest.current_price_eur_kwh(night_charging=True),
            DEFAULT_PVPC_VALLE_EUR_KWH,
        )
        self.assertEqual(
            pvpc_ingest.current_price_eur_kwh(night_charging=False),
            DEFAULT_PVPC_EUR_KWH,
        )
