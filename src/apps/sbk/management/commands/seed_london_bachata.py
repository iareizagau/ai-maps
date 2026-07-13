"""
Management command: seed_london_bachata
Dynamically scrapes Eventbrite for bachata events and inserts them into the DB.
Uses BeautifulSoup for HTML parsing and Nominatim for geocoding.

Usage:
    python manage.py seed_london_bachata
    python manage.py seed_london_bachata --url "https://www.eventbrite.com/d/..."
    python manage.py seed_london_bachata --pages 3
    python manage.py seed_london_bachata --proxy http://user:pass@host:port
    python manage.py seed_london_bachata --clear --dry-run

NOTE: Eventbrite blocks datacenter IPs (DigitalOcean, AWS, GCP, etc.) with 405.
      From a server, set SCRAPER_PROXY env var or pass --proxy to route through
      a residential/SOCKS proxy.
      Example: SCRAPER_PROXY=socks5://user:pass@host:1080
"""

import json
import os
import re
import time
import urllib.parse
from datetime import UTC, datetime, timedelta

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.sbk.models import DanceStyle, Event, EventOccurrence, EventType

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_URL = (
    "https://www.eventbrite.com/d/united-kingdom--london--18207/bachata/"
    "?start_date=2026-06-06&end_date=2026-06-13"
)

# Full browser-like headers — helps with sites that check common headers.
# Eventbrite still blocks cloud IPs regardless of headers, so use --proxy.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


# ---------------------------------------------------------------------------
# HTTP Session — shared across all requests in one command run.
# Proxy is set once here from env var; --proxy CLI flag overrides it.
# ---------------------------------------------------------------------------

_SESSION: requests.Session | None = None


def _get_session(proxy: str | None = None) -> requests.Session:
    """Return (and lazily create) a shared session with browser-like headers."""
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update(HEADERS)

        # Proxy: --proxy arg > SCRAPER_PROXY env var > none
        effective_proxy = proxy or os.environ.get("SCRAPER_PROXY")
        if effective_proxy:
            _SESSION.proxies = {"http": effective_proxy, "https": effective_proxy}

        # Warm up: GET the homepage first to collect cookies (helps avoid bot detection)
        try:
            _SESSION.get("https://www.eventbrite.com/", timeout=15)
        except Exception:
            pass

    return _SESSION


def _fetch(url: str, proxy: str | None = None) -> str:
    sess = _get_session(proxy)
    resp = sess.get(url, timeout=25)
    if resp.status_code == 405:
        raise requests.HTTPError(
            f"405 Method Not Allowed — Eventbrite is blocking this server's IP "
            f"(datacenter IPs are blacklisted). Run with --proxy or set SCRAPER_PROXY "
            f"env var to route through a residential proxy. URL: {url}",
            response=resp,
        )
    resp.raise_for_status()
    return resp.text


# ---------------------------------------------------------------------------
# JSON-LD extraction (schema.org/Event objects embedded in <script> tags)
# ---------------------------------------------------------------------------


def _extract_ld_json_events(soup: BeautifulSoup) -> list[dict]:
    events = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = []
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            if data.get("@type") == "ItemList":
                candidates = [
                    el.get("item", {}) for el in data.get("itemListElement", [])
                ]
            else:
                candidates = [data]

        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == "Event":
                events.append(item)

    return events


# ---------------------------------------------------------------------------
# Card-level extraction (BeautifulSoup — listing page cards)
# Eventbrite wraps each event in <li> / <article> tags with data-event-id
# or similar. We also look for the visible text structure as a fallback.
# ---------------------------------------------------------------------------


def _extract_card_events(soup: BeautifulSoup) -> list[dict]:
    """
    Parse event cards from the Eventbrite listing page HTML.
    Returns dicts with: name, date_str, venue_str, url.
    """
    results = []
    seen = set()

    # Strategy 1: <article> or <li> elements containing an event link + date
    # Eventbrite uses class names like 'search-event-card', 'event-card', etc.
    # We look for any <a> with an Eventbrite event URL and nearby date text.

    # Collect all event links (deduplicated by URL slug)
    event_links = []
    for a in soup.find_all("a", href=re.compile(r"/e/.+-tickets-\d+")):
        href = a.get("href", "").split("?")[0]
        if href in seen:
            continue
        seen.add(href)
        event_links.append(a)

    for a in event_links:
        name = a.get_text(separator=" ", strip=True)
        if not name or len(name) < 4:
            # Try the parent / grandparent for more context
            parent = a.parent
            name = parent.get_text(separator=" ", strip=True)[:200] if parent else name

        # Walk up to find a card container and extract date + venue from siblings
        card = a
        for _ in range(5):
            card = card.parent
            if card is None:
                break
            text = card.get_text(separator="\n", strip=True)
            # Look for date pattern within the card
            date_m = re.search(
                r"(\w{3},\s+\w{3}\s+\d+,\s+\d+:\d+\s+[AP]M)",
                text,
                re.IGNORECASE,
            )
            venue_m = re.search(r"([^\n]+\s*·\s*[^\n]+)", text)
            if date_m:
                results.append(
                    {
                        "name": a.get_text(separator=" ", strip=True),
                        "date_str": date_m.group(1),
                        "venue_str": venue_m.group(1) if venue_m else "",
                        "url": a.get("href", "").split("?")[0],
                    }
                )
                break

    return results


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------


def _parse_date(date_str: str) -> datetime | None:
    """Parse 'Wed, Jun 10, 7:00 PM' → UTC-aware datetime (assumes BST = UTC+1)."""
    date_str = re.sub(
        r"\s*\+\s*\d+\s*more.*", "", date_str, flags=re.IGNORECASE
    ).strip()
    m = re.search(
        r"(\w{3})\s+(\d+),\s+(\d+):(\d+)\s+([AP]M)",
        date_str,
        re.IGNORECASE,
    )
    if not m:
        return None

    month_abbr, day, hour_s, min_s, ampm = m.groups()
    month = MONTHS.get(month_abbr.lower())
    if not month:
        return None

    hour, minute = int(hour_s), int(min_s)
    if ampm.upper() == "PM" and hour != 12:
        hour += 12
    elif ampm.upper() == "AM" and hour == 12:
        hour = 0

    now = datetime.now()
    year = now.year if month >= now.month else now.year + 1

    # London is BST (UTC+1) in June — store as UTC
    bst = datetime(year, month, int(day), hour, minute, tzinfo=UTC)
    return bst - timedelta(hours=1)


# ---------------------------------------------------------------------------
# Geocoding (Nominatim, rate-limited to 1 req/s)
# ---------------------------------------------------------------------------


def _geocode(query: str) -> tuple[float | None, float | None]:
    params = {"q": query, "format": "json", "limit": 1, "countrycodes": "gb"}
    nom_headers = {"User-Agent": "SBK-App/1.0 (contact@iareizaga.com)"}
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            headers=nom_headers,
            timeout=10,
        )
        resp.raise_for_status()
        hits = resp.json()
        if hits:
            return float(hits[0]["lat"]), float(hits[0]["lon"])
    except Exception:
        pass
    return None, None


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


def _event_type(name: str) -> str:
    n = name.lower()
    if any(w in n for w in ("workshop", "class", "bootcamp", "lesson", "course")):
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


def _price_info(name: str) -> str:
    return "Free" if re.search(r"\bfree\b", name, re.IGNORECASE) else ""


# ---------------------------------------------------------------------------
# Normalise a scraped event dict (from either JSON-LD or card parsing)
# into the standard shape used for DB insertion.
# ---------------------------------------------------------------------------


def _normalise_ld(ev: dict, stdout, style) -> dict | None:
    """Normalise a schema.org/Event dict."""
    name = ev.get("name", "").strip()
    if not name:
        return None

    # Dates
    try:
        start_dt = datetime.fromisoformat(ev["startDate"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        start_dt = None
    try:
        end_dt = datetime.fromisoformat(ev["endDate"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        end_dt = None

    # Location
    loc = ev.get("location", {})
    addr = loc.get("address", {})
    venue_name = loc.get("name", "")
    street = addr.get("streetAddress", "")
    locality = addr.get("addressLocality", "London")
    postal = addr.get("postalCode", "")

    address_parts = [p for p in [street, locality, postal] if p]
    address_str = ", ".join(address_parts) or venue_name

    geo = loc.get("geo", {})
    if geo.get("latitude") and geo.get("longitude"):
        lat, lng = float(geo["latitude"]), float(geo["longitude"])
    else:
        query = f"{venue_name}, {locality}, UK"
        stdout.write(f"    📍 Geocoding: {query!r}")
        lat, lng = _geocode(query)
        time.sleep(1.1)

    return {
        "name": name,
        "description": ev.get("description", ""),
        "city": locality or "London",
        "address": address_str,
        "country": "United Kingdom",
        "lat": lat,
        "lng": lng,
        "start_date": start_dt,
        "end_date": end_dt,
        "ticket_url": ev.get("url", ""),
        "image_url": ev.get("image", "") if isinstance(ev.get("image"), str) else "",
        "primary_style": _dance_style(name),
        "event_type": _event_type(name),
        "price_info": _price_info(name),
    }


def _normalise_card(ev: dict, stdout, style) -> dict | None:
    """Normalise a card-parsed dict."""
    name = ev.get("name", "").strip()
    if not name:
        return None

    start_dt = _parse_date(ev.get("date_str", ""))
    venue_str = ev.get("venue_str", "")

    # Split "Neighbourhood · Venue Name"
    parts = [p.strip() for p in venue_str.split("·", 1)]
    neighbourhood = parts[0] if len(parts) > 1 else ""
    venue_name = parts[-1]

    geocode_q = f"{venue_name}, {neighbourhood}, London, UK"
    stdout.write(f"    📍 Geocoding: {geocode_q!r}")
    lat, lng = _geocode(geocode_q)
    time.sleep(1.1)

    return {
        "name": name,
        "description": "",
        "city": "London",
        "address": f"{venue_name}, {neighbourhood}, London".strip(", "),
        "country": "United Kingdom",
        "lat": lat,
        "lng": lng,
        "start_date": start_dt,
        "end_date": None,
        "ticket_url": ev.get("url", ""),
        "image_url": "",
        "primary_style": _dance_style(name),
        "event_type": _event_type(name),
        "price_info": _price_info(name),
    }


# ---------------------------------------------------------------------------
# Top-level scraper
# ---------------------------------------------------------------------------


def scrape_eventbrite(
    base_url: str, max_pages: int, stdout, style, proxy: str | None = None
) -> list[dict]:
    all_events: list[dict] = []
    seen_names: set[str] = set()

    for page in range(1, max_pages + 1):
        parsed = urllib.parse.urlparse(base_url)
        qs = urllib.parse.parse_qs(parsed.query)
        qs["page"] = [str(page)]
        page_url = parsed._replace(
            query=urllib.parse.urlencode(qs, doseq=True)
        ).geturl()

        stdout.write(f"\n  📄 Page {page}: {page_url}")
        try:
            html = _fetch(page_url, proxy=proxy)
        except requests.RequestException as exc:
            stdout.write(style.ERROR(f"  HTTP error: {exc}"))
            break

        soup = BeautifulSoup(html, "html.parser")

        # Try JSON-LD first — highest fidelity
        ld_events = _extract_ld_json_events(soup)
        stdout.write(f"  JSON-LD events found: {len(ld_events)}")

        if ld_events:
            for raw in ld_events:
                norm = _normalise_ld(raw, stdout, style)
                if norm and norm["name"] not in seen_names:
                    seen_names.add(norm["name"])
                    all_events.append(norm)
            page_count = len(ld_events)
        else:
            # Fallback: parse visible card elements with BeautifulSoup
            card_events = _extract_card_events(soup)
            stdout.write(f"  Card events found (fallback): {len(card_events)}")
            if not card_events:
                stdout.write(style.WARNING("  No events found — stopping."))
                break
            for raw in card_events:
                norm = _normalise_card(raw, stdout, style)
                if norm and norm["name"] not in seen_names:
                    seen_names.add(norm["name"])
                    all_events.append(norm)
            page_count = len(card_events)

        if page_count < 18:
            stdout.write(f"  Partial page ({page_count}) — no more pages.")
            break

        time.sleep(2)

    return all_events


# ---------------------------------------------------------------------------
# Django management command
# ---------------------------------------------------------------------------


class Command(BaseCommand):
    help = "Scrapes Eventbrite for bachata events (with BeautifulSoup) and seeds them into the DB"

    def add_arguments(self, parser):
        parser.add_argument(
            "--url", default=DEFAULT_URL, help="Eventbrite search URL to scrape"
        )
        parser.add_argument(
            "--pages",
            type=int,
            default=4,
            help="Max result pages to scrape (default: 4)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete matching events before re-scraping",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Scrape and print without writing to DB",
        )
        parser.add_argument(
            "--proxy",
            default=None,
            help=(
                "HTTP/SOCKS proxy URL (e.g. http://user:pass@host:3128 or "
                "socks5://user:pass@host:1080). Overrides SCRAPER_PROXY env var. "
                "Required when running from cloud servers (DigitalOcean, AWS, etc.) "
                "because Eventbrite blocks datacenter IPs."
            ),
        )

    def handle(self, *args, **options):
        proxy = options.get("proxy") or os.environ.get("SCRAPER_PROXY")
        if proxy:
            self.stdout.write(self.style.WARNING(f"  🔀 Using proxy: {proxy}"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "  ⚠️  No proxy set. Will fail on cloud servers (Eventbrite blocks datacenter IPs).\n"
                    "     Set SCRAPER_PROXY env var or use --proxy flag."
                )
            )

        self.stdout.write(
            self.style.MIGRATE_HEADING(f"\n🕷  Scraping Eventbrite — {options['url']}\n")
        )

        events = scrape_eventbrite(
            options["url"], options["pages"], self.stdout, self.style, proxy=proxy
        )
        self.stdout.write(f"\n  ✅ Total scraped: {len(events)}\n")

        if not events:
            self.stdout.write(self.style.WARNING("Nothing scraped. Exiting."))
            return

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("--- DRY RUN — not saving ---"))
            for ev in events:
                self.stdout.write(
                    f"  • {ev['name']}\n"
                    f"    {ev['start_date']}  |  {ev['city']}  "
                    f"|  lat={ev['lat']} lng={ev['lng']}\n"
                )
            return

        if options["clear"]:
            names = [ev["name"] for ev in events]
            deleted, _ = Event.objects.filter(name__in=names).delete()
            self.stdout.write(
                self.style.WARNING(f"  Cleared {deleted} existing events.")
            )

        created = skipped = errors = 0

        for data in events:
            if not data.get("start_date"):
                self.stdout.write(
                    self.style.WARNING(f"  SKIP (no date): {data['name']}")
                )
                skipped += 1
                continue

            start = data["start_date"]
            slug = slugify(data["name"])[:180] + "-" + start.strftime("%Y-%m-%d")

            if Event.objects.filter(slug=slug).exists():
                self.stdout.write(f"  SKIP (exists): {data['name']}")
                skipped += 1
                continue

            end = data["end_date"] or (start + timedelta(hours=4))

            try:
                event = Event.objects.create(
                    slug=slug,
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
                    event=event,
                    start_date=start,
                    defaults={"end_date": end},
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  CREATED: {event.name}  ({data['city']}, {start.strftime('%a %d %b %H:%M UTC')})"
                    )
                )
                created += 1
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  ERROR {data['name']!r}: {exc}"))
                errors += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅  Done — {created} created, {skipped} skipped, {errors} errors."
            )
        )
