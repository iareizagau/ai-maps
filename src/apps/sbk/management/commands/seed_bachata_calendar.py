"""
Management command: seed_bachata_calendar
Scrapes bachatacalendar.co.uk (London) and seeds events into the DB.

Strategy:
  1. Parse sitemap.xml to discover all /event/<slug> URLs.
  2. Dynamically extract the Supabase anon JWT from the site's JS bundle.
  3. Query the Supabase REST API for structured event data (no JS execution needed).
  4. Geocode venue addresses via Nominatim.

Usage:
    python manage.py seed_bachata_calendar
    python manage.py seed_bachata_calendar --limit 50
    python manage.py seed_bachata_calendar --clear --dry-run

NOTE: bachatacalendar.co.uk is a Supabase-backed SPA. This command calls the
      Supabase REST API directly using the public anon key extracted from the JS
      bundle — no browser/JS rendering required, works from any server IP.
"""
import re
import time
import json
from datetime import datetime, timezone as dt_tz, timedelta
from xml.etree import ElementTree

import requests
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.sbk.models import Event, EventOccurrence, DanceStyle, EventType


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SITE_URL       = "https://www.bachatacalendar.co.uk"
SITEMAP_URL    = "https://bachatacalendar.co.uk/sitemap.xml"
SUPABASE_URL   = "https://stsdtacfauprzrdebmzg.supabase.co"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Known JS bundle filename (changes on each deploy — we rediscover it at runtime)
_KNOWN_BUNDLE_PATH = "/assets/index-DNuTsjp4.js"

# ---------------------------------------------------------------------------
# Step 1: Discover the current JS bundle URL
# ---------------------------------------------------------------------------

def _get_bundle_url() -> str:
    """Fetch the SPA homepage and extract the main JS bundle src."""
    r = requests.get(SITE_URL, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=15)
    r.raise_for_status()
    matches = re.findall(r'src="(/assets/index-[^"]+\.js)"', r.text)
    if matches:
        return SITE_URL + matches[0]
    # Fallback to known path
    return SITE_URL + _KNOWN_BUNDLE_PATH


# ---------------------------------------------------------------------------
# Step 2: Extract Supabase anon JWT from the bundle
# ---------------------------------------------------------------------------

def _extract_anon_key(bundle_url: str) -> str | None:
    """
    Find the full Supabase anon JWT in the minified JS bundle.
    The JWT format is: <header>.<payload>.<signature>  (all base64url segments).
    The payload we already know starts with eyJpc3MiOiJzdXBhYmFzZSIs...
    """
    r = requests.get(bundle_url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=20)
    r.raise_for_status()
    js = r.text

    # Find full JWT: three base64url segments separated by dots
    # The known payload starts with eyJpc3MiOiJzdXBhYmFzZSIs
    pattern = re.compile(
        r'(eyJ[A-Za-z0-9_\-]+'     # header
        r'\.'
        r'eyJpc3MiOiJzdXBhYmFzZSIs[A-Za-z0-9_\-]+'  # known payload prefix
        r'\.'
        r'[A-Za-z0-9_\-]+)'        # signature
    )
    m = pattern.search(js)
    if m:
        return m.group(1)

    # Fallback: find any long string (>200 chars) starting with eyJ
    long_keys = re.findall(r'"(eyJ[A-Za-z0-9_\-]{200,})"', js)
    return long_keys[0] if long_keys else None


# ---------------------------------------------------------------------------
# Step 3: Parse sitemap to get event slugs
# ---------------------------------------------------------------------------

def _get_event_slugs_from_sitemap() -> list[str]:
    """Parse sitemap.xml and return all /event/<slug> paths."""
    r = requests.get(SITEMAP_URL, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=15)
    r.raise_for_status()
    root = ElementTree.fromstring(r.content)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    slugs = []
    for url_el in root.findall("sm:url", ns):
        loc = url_el.findtext("sm:loc", "", ns)
        m = re.match(r'https?://[^/]+/event/([^/]+)$', loc)
        if m:
            slugs.append(m.group(1))
    return slugs


# ---------------------------------------------------------------------------
# Step 4: Query Supabase REST API
# ---------------------------------------------------------------------------

def _supabase_headers(anon_key: str) -> dict:
    return {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Content-Type": "application/json",
    }


def _fetch_events_from_supabase(anon_key: str, city_slug: str = "london-gb", limit: int = 200) -> list[dict]:
    """
    Try common Supabase table/view names for events.
    Returns raw rows or [] if none found.
    """
    candidate_tables = ["events", "event", "london_events", "city_events", "bachata_events"]
    hdrs = _supabase_headers(anon_key)

    for table in candidate_tables:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        params = {
            "select": "*",
            "limit": str(limit),
            "order": "start_date.asc",
        }
        try:
            r = requests.get(url, headers=hdrs, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    return data, table
            # 404 = table doesn't exist, try next
        except Exception:
            continue

    return [], None


def _fetch_events_by_slug(anon_key: str, slug: str) -> dict | None:
    """Fetch a single event by slug from any matching table."""
    candidate_tables = ["events", "event"]
    hdrs = _supabase_headers(anon_key)
    for table in candidate_tables:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        params = {"select": "*", "slug": f"eq.{slug}", "limit": "1"}
        try:
            r = requests.get(url, headers=hdrs, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    return data[0]
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Step 5: Geocode via Nominatim
# ---------------------------------------------------------------------------

def _geocode(query: str) -> tuple[float | None, float | None]:
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "gb"},
            headers={"User-Agent": "SBK-App/1.0 (contact@iareizaga.com)"},
            timeout=10,
        )
        r.raise_for_status()
        hits = r.json()
        if hits:
            return float(hits[0]["lat"]), float(hits[0]["lon"])
    except Exception:
        pass
    return None, None


# ---------------------------------------------------------------------------
# Step 6: Normalise a raw Supabase row → standard event dict
# ---------------------------------------------------------------------------

KNOWN_FIELD_MAPS = {
    # Possible field name variations for key fields
    "name":        ["name", "title", "event_name"],
    "description": ["description", "desc", "details", "about"],
    "start_date":  ["start_date", "starts_at", "date", "event_date", "start"],
    "end_date":    ["end_date", "ends_at", "end"],
    "venue":       ["venue", "venue_name", "location_name", "place"],
    "address":     ["address", "full_address", "location"],
    "city":        ["city", "city_name"],
    "lat":         ["lat", "latitude"],
    "lng":         ["lng", "lon", "longitude"],
    "ticket_url":  ["ticket_url", "url", "link", "eventbrite_url", "tickets_url"],
    "image_url":   ["image_url", "image", "poster", "photo", "cover_image"],
    "price":       ["price", "price_info", "cost", "ticket_price"],
}


def _pick(row: dict, candidates: list[str], default=None):
    for key in candidates:
        if key in row and row[key] is not None:
            return row[key]
    return default


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _event_type(name: str) -> str:
    n = name.lower()
    if any(w in n for w in ("workshop", "class", "bootcamp", "lesson", "course", "styling")):
        return EventType.WORKSHOP
    if any(w in n for w in ("festival", "congress")):
        return EventType.FESTIVAL
    return EventType.PARTY


def _dance_style(name: str) -> str:
    n = name.lower()
    if "bachata" in n and "salsa" not in n and "kizomba" not in n:
        return DanceStyle.BACHATA
    if "kizomba" in n:
        return DanceStyle.KIZOMBA
    if "zouk" in n:
        return DanceStyle.ZOUK
    return DanceStyle.MIXED


def _normalise_row(row: dict, stdout, style) -> dict | None:
    name = _pick(row, KNOWN_FIELD_MAPS["name"], "").strip()
    if not name:
        return None

    start_dt = _parse_iso(_pick(row, KNOWN_FIELD_MAPS["start_date"]))
    end_dt   = _parse_iso(_pick(row, KNOWN_FIELD_MAPS["end_date"]))

    venue    = _pick(row, KNOWN_FIELD_MAPS["venue"], "")
    address  = _pick(row, KNOWN_FIELD_MAPS["address"], venue)
    city     = _pick(row, KNOWN_FIELD_MAPS["city"], "London") or "London"

    lat = _pick(row, KNOWN_FIELD_MAPS["lat"])
    lng = _pick(row, KNOWN_FIELD_MAPS["lng"])

    if not (lat and lng) and (venue or address):
        query = f"{venue or address}, {city}, UK"
        stdout.write(f"    📍 Geocoding: {query!r}")
        lat, lng = _geocode(query)
        time.sleep(1.1)  # Nominatim rate limit

    return {
        "name":         name,
        "description":  _pick(row, KNOWN_FIELD_MAPS["description"], ""),
        "city":         city,
        "address":      address or venue,
        "country":      "United Kingdom",
        "lat":          float(lat) if lat else None,
        "lng":          float(lng) if lng else None,
        "start_date":   start_dt,
        "end_date":     end_dt,
        "ticket_url":   _pick(row, KNOWN_FIELD_MAPS["ticket_url"], f"{SITE_URL}/event/{row.get('slug', '')}"),
        "image_url":    _pick(row, KNOWN_FIELD_MAPS["image_url"], ""),
        "primary_style": _dance_style(name),
        "event_type":   _event_type(name),
        "price_info":   str(_pick(row, KNOWN_FIELD_MAPS["price"], "") or ""),
        "source":       "bachatacalendar",
    }


# ---------------------------------------------------------------------------
# Slug-based fallback: normalise from slug name alone (no Supabase data)
# ---------------------------------------------------------------------------

def _normalise_slug(slug: str) -> dict:
    """Minimal event dict built from the slug string when Supabase is unavailable."""
    name = slug.replace("-", " ").title()
    return {
        "name":         name,
        "description":  "",
        "city":         "London",
        "address":      "",
        "country":      "United Kingdom",
        "lat":          None,
        "lng":          None,
        "start_date":   None,
        "end_date":     None,
        "ticket_url":   f"{SITE_URL}/event/{slug}",
        "image_url":    "",
        "primary_style": _dance_style(name),
        "event_type":   _event_type(name),
        "price_info":   "",
        "source":       "bachatacalendar",
    }


# ---------------------------------------------------------------------------
# Django management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = "Scrapes bachatacalendar.co.uk (London) via Supabase REST API and seeds events into the DB"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=200,
            help="Max events to fetch from Supabase (default: 200)",
        )
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete previously seeded BachataCalendar events before re-importing",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Scrape and print without writing to DB",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n🕷  Scraping bachatacalendar.co.uk via Supabase REST API\n"
        ))

        # ------------------------------------------------------------------
        # 1. Discover JS bundle & extract anon key
        # ------------------------------------------------------------------
        self.stdout.write("  🔍 Discovering JS bundle…")
        try:
            bundle_url = _get_bundle_url()
            self.stdout.write(f"  Bundle: {bundle_url}")
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"  Failed to get bundle URL: {exc}"))
            bundle_url = SITE_URL + _KNOWN_BUNDLE_PATH

        self.stdout.write("  🔑 Extracting Supabase anon key…")
        anon_key = _extract_anon_key(bundle_url)
        if anon_key:
            self.stdout.write(self.style.SUCCESS(f"  Anon key found ({len(anon_key)} chars)"))
        else:
            self.stdout.write(self.style.WARNING("  Anon key NOT found — will use slug-only fallback"))

        # ------------------------------------------------------------------
        # 2. Fetch events
        # ------------------------------------------------------------------
        raw_rows = []
        table_name = None

        if anon_key:
            self.stdout.write(f"  📡 Querying Supabase REST API (limit={options['limit']})…")
            raw_rows, table_name = _fetch_events_from_supabase(anon_key, limit=options["limit"])
            if raw_rows:
                self.stdout.write(self.style.SUCCESS(
                    f"  Found {len(raw_rows)} rows in table '{table_name}'"
                ))
                # Show field names to help debug schema
                if raw_rows:
                    self.stdout.write(f"  Fields: {list(raw_rows[0].keys())}")
            else:
                self.stdout.write(self.style.WARNING(
                    "  No rows found in Supabase (table name unknown or RLS blocks anon). "
                    "Falling back to sitemap slugs."
                ))

        # Fallback: use sitemap slugs (no dates/addresses available)
        if not raw_rows:
            self.stdout.write("  🗺  Parsing sitemap.xml for event slugs…")
            try:
                slugs = _get_event_slugs_from_sitemap()
                self.stdout.write(f"  Found {len(slugs)} event slugs")
                raw_rows = [{"slug": s} for s in slugs]
                table_name = "sitemap"
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  Sitemap error: {exc}"))
                return

        # ------------------------------------------------------------------
        # 3. Normalise rows
        # ------------------------------------------------------------------
        events = []
        seen = set()
        for row in raw_rows:
            if table_name == "sitemap":
                norm = _normalise_slug(row["slug"])
            else:
                norm = _normalise_row(row, self.stdout, self.style)
            if norm and norm["name"] not in seen:
                seen.add(norm["name"])
                events.append(norm)

        self.stdout.write(f"\n  ✅ Total normalised: {len(events)}\n")

        if not events:
            self.stdout.write(self.style.WARNING("Nothing to import."))
            return

        # ------------------------------------------------------------------
        # 4. Dry run
        # ------------------------------------------------------------------
        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("--- DRY RUN — not saving ---"))
            for ev in events:
                self.stdout.write(
                    f"  • {ev['name']}\n"
                    f"    {ev['start_date']}  |  {ev['city']}  "
                    f"|  lat={ev['lat']} lng={ev['lng']}\n"
                )
            return

        # ------------------------------------------------------------------
        # 5. Clear
        # ------------------------------------------------------------------
        if options["clear"]:
            deleted, _ = Event.objects.filter(
                ticket_url__startswith=SITE_URL
            ).delete()
            self.stdout.write(self.style.WARNING(f"  Cleared {deleted} existing BachataCalendar events."))

        # ------------------------------------------------------------------
        # 6. Insert into DB
        # ------------------------------------------------------------------
        created = skipped = errors = 0

        for data in events:
            if not data.get("start_date"):
                # Events without a date get skipped (slug-only fallback rows)
                self.stdout.write(self.style.WARNING(f"  SKIP (no date): {data['name']}"))
                skipped += 1
                continue

            start = data["start_date"]
            raw_slug = slugify(data["name"])[:180] + "-" + start.strftime("%Y-%m-%d")

            if Event.objects.filter(slug=raw_slug).exists():
                self.stdout.write(f"  SKIP (exists): {data['name']}")
                skipped += 1
                continue

            end = data["end_date"] or (start + timedelta(hours=4))

            try:
                event = Event.objects.create(
                    slug=raw_slug,
                    name=data["name"],
                    description=data.get("description", ""),
                    city=data["city"],
                    address=data.get("address", ""),
                    country=data.get("country", "United Kingdom"),
                    lat=data.get("lat"),
                    lng=data.get("lng"),
                    start_date=start,
                    end_date=end,
                    primary_style=data["primary_style"],
                    event_type=data["event_type"],
                    price_info=data.get("price_info") or "",
                    ticket_url=data.get("ticket_url") or "",
                    image_url=data.get("image_url") or "",
                    is_verified=True,
                    moderation_status="verified",
                )
                EventOccurrence.objects.get_or_create(
                    event=event, start_date=start,
                    defaults={"end_date": end},
                )
                self.stdout.write(self.style.SUCCESS(
                    f"  CREATED: {event.name}  ({data['city']}, {start.strftime('%a %d %b %H:%M')})"
                ))
                created += 1
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  ERROR {data['name']!r}: {exc}"))
                errors += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n✅  Done — {created} created, {skipped} skipped, {errors} errors."
        ))

        # ------------------------------------------------------------------
        # 7. Debug hint if Supabase had no data
        # ------------------------------------------------------------------
        if table_name == "sitemap":
            self.stdout.write(self.style.WARNING(
                "\n⚠️  Imported from sitemap only (no dates/addresses). "
                "If the Supabase anon key is found, re-run to get full data.\n"
                "To inspect Supabase tables manually:\n"
                f"  curl '{SUPABASE_URL}/rest/v1/' "
                f"-H 'apikey: <anon_key>' -H 'Authorization: Bearer <anon_key>'"
            ))
