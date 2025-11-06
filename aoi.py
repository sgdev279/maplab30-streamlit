import requests

UA = {"User-Agent": "MapLab30/1.0 (+https://example.com)"}

def nominatim_bbox(area_query: str):
    """Return (south, west, north, east) bbox for a place name using Nominatim."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": area_query, "format": "json", "limit": 1}
    r = requests.get(url, params=params, headers=UA, timeout=30)
    r.raise_for_status()
    js = r.json()
    if not js:
        raise ValueError("Area not found via Nominatim. Try a broader name (e.g., City, Country).")
    b = js[0]["boundingbox"]  # [south, north, west, east]
    south, north, west, east = map(float, b)
    return south, west, north, east
