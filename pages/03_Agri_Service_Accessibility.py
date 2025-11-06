import streamlit as st
import geopandas as gpd
import leafmap.foliumap as leafmap
from shapely.geometry import Polygon

from utils.aoi import nominatim_bbox
from utils.osm import pois_by_keyvalue, pois_by_selectors


st.title("Day 01 — Agricultural Service Accessibility (Points)")
st.caption(
    "OSM agricultural support facilities • Density + coverage • Download-ready • #30DayMapChallenge"
)

col_map, col_controls = st.columns([2, 1], gap="large")

with col_controls:
    area = st.text_input("District / City / Block:", "Ranchi, Jharkhand")
    buffer_km = st.slider("Village coverage buffer (km)", 1, 25, 10)
    heatmap_on = st.checkbox("Show density heatmap", value=True)
    show_villages = st.checkbox("Overlay villages", value=True)
    run = st.button("Fetch accessibility view", type="primary")

m = leafmap.Map(minimap_control=False, draw_export=False)
m.add_basemap("CartoDB.Positron")

SERVICE_CATEGORIES = {
    "Krishi Vigyan Kendra": {
        "color": "#2e7d32",
        "selectors": ['["office"="government"]["name"~"krishi vigyan kendra",i]'],
    },
    "Fertilizer & Input Retailer": {
        "color": "#ef6c00",
        "selectors": [
            '["shop"~"agrarian|agricultural_supplies|fertilizer|farm_supply",i]',
            '["amenity"="agricultural_service"]',
        ],
    },
    "Cold Storage": {
        "color": "#1e88e5",
        "selectors": [
            '["industrial"~"cold_storage",i]',
            '["man_made"="storage_tank"]["name"~"cold storage",i]',
            '["building"="warehouse"]["name"~"cold storage",i]',
        ],
    },
    "Soil Testing Lab": {
        "color": "#8e24aa",
        "selectors": [
            '["amenity"="laboratory"]["name"~"soil",i]',
            '["amenity"="research_institute"]["name"~"soil|agri",i]',
        ],
    },
}

ALL_SELECTORS = sorted({sel for cfg in SERVICE_CATEGORIES.values() for sel in cfg["selectors"]})


def classify_service(tags: dict) -> str:
    """Assign a human-friendly category based on tags."""

    name = (tags.get("name") or "").lower()
    amenity = (tags.get("amenity") or "").lower()
    shop = (tags.get("shop") or "").lower()
    office = (tags.get("office") or "").lower()
    industrial = (tags.get("industrial") or "").lower()

    if "krishi vigyan kendra" in name or (
        office == "government" and "krishi vigyan" in name
    ):
        return "Krishi Vigyan Kendra"
    if shop in {"agrarian", "agricultural_supplies", "fertilizer", "farm_supply"}:
        return "Fertilizer & Input Retailer"
    if amenity == "agricultural_service" or "fertilizer" in name or "seed" in name:
        return "Fertilizer & Input Retailer"
    if ("soil" in name and ("lab" in name or "testing" in name)) or tags.get("laboratory:type"):
        return "Soil Testing Lab"
    if amenity == "laboratory" and "soil" in name:
        return "Soil Testing Lab"
    if industrial == "cold_storage" or ("cold" in name and "storage" in name) or tags.get("cold_storage"):
        return "Cold Storage"
    if amenity == "research_institute" and "soil" in name:
        return "Soil Testing Lab"
    return "Other"


def aggregate_services(bbox):
    facilities = pois_by_selectors(bbox, ALL_SELECTORS)
    if facilities.empty:
        return facilities
    facilities = facilities.copy()
    facilities["category"] = facilities["tags"].apply(classify_service)
    facilities["color"] = facilities["category"].apply(
        lambda c: SERVICE_CATEGORIES.get(c, {"color": "#455a64"})["color"]
    )
    return facilities


def add_bounds_layer(map_obj, bbox):
    south, west, north, east = bbox
    bounds_poly = gpd.GeoSeries(
        [Polygon([(west, south), (east, south), (east, north), (west, north), (west, south)])],
        crs="EPSG:4326",
    )
    map_obj.add_geojson(bounds_poly.__geo_interface__, layer_name="AOI extent")


if run:
    try:
        bbox = nominatim_bbox(area)
        facilities = aggregate_services(bbox)
        villages = (
            pois_by_keyvalue(bbox, "place", "^(village|hamlet)$") if show_villages else gpd.GeoDataFrame()
        )

        if facilities.empty:
            st.warning("No agricultural service facilities found in this area via OSM.")
        else:
            ctr_lat = facilities.geometry.y.mean()
            ctr_lon = facilities.geometry.x.mean()
            m.set_center(ctr_lon, ctr_lat, 9)
            add_bounds_layer(m, bbox)

            for category, cfg in SERVICE_CATEGORIES.items():
                subset = facilities[facilities["category"] == category]
                if subset.empty:
                    continue
                m.add_points_from_xy(
                    subset,
                    x="lon",
                    y="lat",
                    layer_name=category,
                    icon_colors=[cfg["color"]] * len(subset),
                    popup=["name", "category"],
                )

            other = facilities[facilities["category"] == "Other"]
            if not other.empty:
                m.add_points_from_xy(
                    other,
                    x="lon",
                    y="lat",
                    layer_name="Other Agri Services",
                    icon_colors=["#546e7a"] * len(other),
                    popup=["name", "category"],
                )

            if heatmap_on and len(facilities) > 3:
                m.add_heatmap(
                    facilities[["lat", "lon"]],
                    latitude="lat",
                    longitude="lon",
                    name="Density heatmap",
                )

            if not villages.empty:
                st.info(
                    "Villages sourced from OSM `place=village/hamlet`. Coverage uses straight-line distance."
                )
                buffer_m = buffer_km * 1000
                facilities_m = facilities.to_crs(3857)
                coverage_area = facilities_m.buffer(buffer_m)
                coverage_union = coverage_area.unary_union
                villages_m = villages.to_crs(3857)
                villages["covered"] = villages_m.geometry.apply(lambda g: coverage_union.contains(g))
                total_villages = len(villages)
                covered = int(villages["covered"].sum())
                pct = (covered / total_villages) * 100 if total_villages else 0

                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Facilities mapped", f"{len(facilities):,}")
                col_b.metric(
                    "Villages within buffer",
                    f"{covered:,}/{total_villages:,}" if total_villages else "0",
                    f"{pct:.1f}%" if total_villages else None,
                )
                col_c.metric("Buffer radius", f"{buffer_km} km")

                uncovered = villages[~villages["covered"]]
                if not uncovered.empty:
                    st.warning(
                        f"{len(uncovered):,} villages fall outside the {buffer_km} km reach of mapped facilities."
                    )

                coverage_geo = gpd.GeoSeries([coverage_union], crs=3857).to_crs(4326)
                m.add_geojson(coverage_geo.__geo_interface__, layer_name=f"{buffer_km} km coverage")
                m.add_points_from_xy(
                    villages,
                    x="lon",
                    y="lat",
                    layer_name="Villages",
                    icon_colors=["#9e9e9e"] * len(villages),
                    popup=["name", "covered"],
                )
            elif show_villages:
                st.info("Village centroids unavailable in this area via OSM; coverage metric skipped.")

            st.subheader("Facility breakdown")
            summary = facilities.groupby("category").size().reset_index(name="count").sort_values(
                "count", ascending=False
            )
            st.dataframe(summary)

            st.download_button(
                "Download facilities GeoJSON",
                data=facilities.to_json(),
                file_name=f"agri_services_{area.replace(',', '_').replace(' ', '_')}.geojson",
                mime="application/geo+json",
            )

            if not villages.empty:
                st.download_button(
                    "Download villages with coverage flag (GeoJSON)",
                    data=villages.to_json(),
                    file_name=f"villages_coverage_{area.replace(',', '_').replace(' ', '_')}.geojson",
                    mime="application/geo+json",
                )

    except Exception as exc:
        st.error(str(exc))

with col_map:
    m.to_streamlit(height=640)
