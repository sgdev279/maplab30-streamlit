import requests
import geopandas as gpd
from shapely.geometry import Point, LineString

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = {"User-Agent": "MapLab30/1.0"}

def overpass(query: str):
    r = requests.post(OVERPASS, data={"data": query}, headers=UA, timeout=60)
    r.raise_for_status()
    return r.json()

def pois_by_keyvalue(bbox, key, values_regex):
    """Get points for a given OSM key and regex of values within bbox."""
    s, w, n, e = bbox
    q = f"""
    [out:json][timeout:25];
    (
      node["{key}"~"{values_regex}"]({s},{w},{n},{e});
      way["{key}"~"{values_regex}"]({s},{w},{n},{e});
      relation["{key}"~"{values_regex}"]({s},{w},{n},{e});
    );
    out center tags;
    """
    js = overpass(q)
    recs = []
    for el in js.get("elements", []):
        if "lon" in el and "lat" in el:
            lon, lat = el["lon"], el["lat"]
        elif "center" in el:
            lon, lat = el["center"]["lon"], el["center"]["lat"]
        else:
            continue
        recs.append({
            "name": el.get("tags", {}).get("name", ""),
            "key": key,
            "type": el.get("type",""),
            "lon": lon,
            "lat": lat,
            "tags": el.get("tags", {})
        })
    if not recs:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    gdf = gpd.GeoDataFrame(recs, geometry=gpd.points_from_xy(
        [r["lon"] for r in recs],[r["lat"] for r in recs]), crs="EPSG:4326")
    return gdf

def lines_by_key(bbox, key, extra_filter=""):
    """Get line features by key within bbox; optional extra filter clause."""
    s, w, n, e = bbox
    q = f"""
    [out:json][timeout:25];
    way["{key}"{extra_filter}]({s},{w},{n},{e});
    out tags geom;
    """
    js = overpass(q)
    recs = []
    for el in js.get("elements", []):
        if "geometry" not in el:
            continue
        coords = [(p["lon"], p["lat"]) for p in el["geometry"]]
        recs.append({
            "id": el.get("id"),
            "name": el.get("tags", {}).get("name",""),
            "tags": el.get("tags", {}),
            "geometry": LineString(coords)
        })
    if not recs:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    return gpd.GeoDataFrame(recs, crs="EPSG:4326")
