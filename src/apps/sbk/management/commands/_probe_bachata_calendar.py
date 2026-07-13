"""Quick probe: find full Supabase anon key JWT from BachataCalendar JS bundle."""

import re

import requests

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
}

r = requests.get(
    "https://www.bachatacalendar.co.uk/assets/index-DNuTsjp4.js",
    headers=headers,
    timeout=20,
)
js = r.text
print(f"Bundle size: {len(js)} bytes")

# Full JWT: header.payload.signature
jwts = re.findall(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", js)
print(f"\nFull JWTs found ({len(jwts)}):")
for j in jwts[:5]:
    print(f"  {j[:120]}...")

# Also look for the anon key string literal assignment pattern
key_patterns = re.findall(r'["\']([A-Za-z0-9_\-]{200,})["\']', js)
print(f"\nLong string literals ({len(key_patterns)}):")
for k in key_patterns[:5]:
    print(f"  {k[:120]}...")

# Table names via supabase .from or rpc patterns
table_candidates = re.findall(r'from\(["\'`]([a-z_]{3,40})["\'`]\)', js)
print(f"\nTable names: {list(set(table_candidates))[:20]}")

rpc_candidates = re.findall(r'rpc\(["\'`]([a-z_]{3,60})["\'`]\)', js)
print(f"\nRPC functions: {list(set(rpc_candidates))[:20]}")
