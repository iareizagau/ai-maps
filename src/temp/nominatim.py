import requests
import time
import json
import hashlib
from pathlib import Path

BASE_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {
    "User-Agent": "MiGeocoderPersonal/1.0 (contacto: tuemail@example.com)"
}

CACHE_DIR = Path("./cache")
CACHE_DIR.mkdir(exist_ok=True)

DELAY_SECONDS = 1.2


def cache_path(query: str) -> Path:
    h = hashlib.sha256(query.encode()).hexdigest()
    return CACHE_DIR / f"{h}.json"


def search(query: str):
    path = cache_path(query)

    # Cache local
    if path.exists():
        print("[CACHE]")
        return json.loads(path.read_text())

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1
    }

    try:
        r = requests.get(
            BASE_URL,
            params=params,
            headers=HEADERS,
            timeout=20
        )

        if r.status_code == 429:
            print("Rate limit alcanzado.")
            return None

        r.raise_for_status()

        data = r.json()

        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

        return data

    except requests.RequestException as e:
        print("Error:", e)
        return None


def main():
    while True:
        query = input("\nBuscar dirección (ENTER para salir): ").strip()

        if not query:
            break

        result = search(query)

        if result:
            if len(result) == 0:
                print("Sin resultados")
            else:
                item = result[0]
                print("\nResultado:")
                print("Nombre :", item.get("display_name"))
                print("Latitud:", item.get("lat"))
                print("Longitud:", item.get("lon"))

        time.sleep(DELAY_SECONDS)


if __name__ == "__main__":
    main()