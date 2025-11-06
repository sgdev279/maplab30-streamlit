from textwrap import dedent
from typing import Optional

import geopandas as gpd
import streamlit as st
from shapely.geometry import Polygon
import leafmap.foliumap as leafmap
from requests import RequestException

from utils.aoi import nominatim_bbox
from utils.osm import pois_by_keyvalue, pois_by_selectors

st.set_page_config(
    page_title="Agricultural Service Accessibility",
    page_icon="🌾",
    layout="wide",
)

st.markdown(
    """
    <style>
    .metric-label {font-size:0.9rem; color:#5f6368; text-transform:uppercase; letter-spacing:0.08em;}
    .metric-value {font-size:2.2rem; font-weight:600; color:#263238;}
    .streamlit-expanderHeader {font-weight:600;}
    </style>
    """,
    unsafe_allow_html=True,
)

ARC_GIS_BASEMAPS = {
    "ArcGIS Imagery (World Imagery)": "Esri.WorldImagery",
    "ArcGIS Topographic": "Esri.WorldTopoMap",
    "ArcGIS Light Gray Canvas": "Esri.WorldGrayCanvas",
    "ArcGIS Terrain": "Esri.WorldTerrain",
}

ARC_GIS_OVERLAY = {
    "name": "ArcGIS Global Cropland",
    "url": "https://services.arcgisonline.com/ArcGIS/rest/services/World_Cropland/MapServer/tile/{z}/{y}/{x}",
    "attribution": "Esri, FAO, NASA",
}

SERVICE_CATEGORIES = {
    "Krishi Vigyan Kendra": {
        "color": "#2f7d32",
        "selectors": ('["office"="government"]["name"~"krishi vigyan kendra",i]',),
    },
    "Agri Input & Fertilizer Dealer": {
        "color": "#ef6c00",
        "selectors": (
            '["shop"~"agrarian|agricultural_supplies|fertilizer|farm_supply",i]',
            '["amenity"="agricultural_service"]',
            '["shop"="garden_centre"]["name"~"seed|fertilizer",i]',
        ),
    },
    "Seed & Planting Material Centre": {
        "color": "#558b2f",
        "selectors": (
            '["shop"~"seed|nursery",i]',
            '["amenity"="marketplace"]["name"~"seed",i]',
        ),
    },
    "Cold Storage & Warehousing": {
        "color": "#1976d2",
        "selectors": (
            '["industrial"~"cold_storage",i]',
            '["man_made"="storage_tank"]["name"~"cold storage",i]',
            '["building"="warehouse"]["name"~"cold",i]',
        ),
    },
    "Soil & Agronomy Lab": {
        "color": "#8e24aa",
        "selectors": (
            '["amenity"="laboratory"]["name"~"soil|agro",i]',
            '["amenity"="research_institute"]["name"~"soil|agri",i]',
        ),
    },
    "Agri Machinery & Custom Hiring": {
        "color": "#c2185b",
        "selectors": (
            '["shop"~"agro_equipment|tractor|farm_machinery",i]',
            '["amenity"="workshop"]["name"~"tractor|agri",i]',
        ),
    },
    "Dairy & Collection Centre": {
        "color": "#0097a7",
        "selectors": (
            '["amenity"="milk_collection"]',
            '["amenity"="dairy"]',
            '["man_made"="works"]["name"~"chilling",i]',
        ),
    },
    "Farmer Producer Org / Cooperative": {
        "color": "#5d4037",
        "selectors": (
            '["office"="association"]["name"~"farmer|producer",i]',
            '["office"="cooperative"]["name"~"agri|milk",i]',
        ),
    },
}

ALL_SELECTORS = tuple(sorted({sel for cfg in SERVICE_CATEGORIES.values() for sel in cfg["selectors"]}))


@st.cache_data(show_spinner=False)
def fetch_facilities(area_name: str):
    bbox = nominatim_bbox(area_name)
    facilities = pois_by_selectors(bbox, ALL_SELECTORS)
    if facilities.empty:
        return bbox, facilities
    facilities = facilities.copy()
    facilities["category"] = facilities["tags"].apply(classify_service)
    facilities["color"] = facilities["category"].apply(
        lambda c: SERVICE_CATEGORIES.get(c, {"color": "#546e7a"})["color"]
    )
    return bbox, facilities


@st.cache_data(show_spinner=False)
def fetch_villages(bbox_tuple):
    return pois_by_keyvalue(bbox_tuple, "place", "^(village|hamlet)$")


def classify_service(tags: dict) -> str:
    name = (tags.get("name") or "").lower()
    amenity = (tags.get("amenity") or "").lower()
    shop = (tags.get("shop") or "").lower()
    office = (tags.get("office") or "").lower()
    industrial = (tags.get("industrial") or "").lower()
    building = (tags.get("building") or "").lower()

    if "krishi vigyan kendra" in name or (
        office == "government" and "krishi vigyan" in name
    ):
        return "Krishi Vigyan Kendra"
    if shop in {"agrarian", "agricultural_supplies", "fertilizer", "farm_supply"}:
        return "Agri Input & Fertilizer Dealer"
    if amenity == "agricultural_service" or "fertilizer" in name or "pesticide" in name:
        return "Agri Input & Fertilizer Dealer"
    if "seed" in name or shop in {"seed", "nursery", "garden_centre"}:
        return "Seed & Planting Material Centre"
    if ("soil" in name and ("lab" in name or "testing" in name)) or tags.get("laboratory:type"):
        return "Soil & Agronomy Lab"
    if amenity == "laboratory" and ("soil" in name or "agro" in name):
        return "Soil & Agronomy Lab"
    if amenity == "research_institute" and ("soil" in name or "agri" in name):
        return "Soil & Agronomy Lab"
    if industrial == "cold_storage" or ("cold" in name and "storage" in name):
        return "Cold Storage & Warehousing"
    if building == "warehouse" and "cold" in name:
        return "Cold Storage & Warehousing"
    if "machinery" in name or "tractor" in name or shop in {"agro_equipment", "tractor"}:
        return "Agri Machinery & Custom Hiring"
    if amenity == "workshop" and ("tractor" in name or "agri" in name):
        return "Agri Machinery & Custom Hiring"
    if amenity in {"milk_collection", "dairy"} or "milk" in name:
        return "Dairy & Collection Centre"
    if "producer company" in name or "fpo" in name or "farmers producer" in name:
        return "Farmer Producer Org / Cooperative"
    if office in {"association", "cooperative"} and ("farmer" in name or "milk" in name or "agri" in name):
        return "Farmer Producer Org / Cooperative"
    if "chilling" in name or "collection centre" in name:
        return "Dairy & Collection Centre"
    return "Other"


def add_bounds_layer(map_obj, bbox):
    south, west, north, east = bbox
    bounds_poly = gpd.GeoSeries(
        [Polygon([(west, south), (east, south), (east, north), (west, north), (west, south)])],
        crs="EPSG:4326",
    )
    map_obj.add_geojson(bounds_poly.__geo_interface__, layer_name="Search extent")


def render_map(
    facilities: gpd.GeoDataFrame,
    villages: gpd.GeoDataFrame,
    coverage_geo: Optional[gpd.GeoDataFrame],
    bbox,
    basemap_choice: str,
    show_heatmap: bool,
    overlay_cropland: bool,
):
    m = leafmap.Map(minimap_control=False, draw_export=False)
    basemap_key = ARC_GIS_BASEMAPS.get(basemap_choice, "Esri.WorldImagery")
    try:
        m.add_basemap(basemap_key)
    except Exception:
        m.add_basemap("CartoDB.Positron")
        st.info(
            "ArcGIS basemap could not be reached in this session. Showing CartoDB Positron instead."
        )
    if overlay_cropland:
        try:
            m.add_tile_layer(
                url=ARC_GIS_OVERLAY["url"],
                name=ARC_GIS_OVERLAY["name"],
                attribution=ARC_GIS_OVERLAY["attribution"],
                opacity=0.55,
            )
        except Exception:
            st.warning("ArcGIS cropland overlay unavailable right now.")

    if facilities.empty:
        m.set_center((bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2, 7)
        m.to_streamlit(height=600)
        return

    ctr_lat = facilities.geometry.y.mean()
    ctr_lon = facilities.geometry.x.mean()
    m.set_center(ctr_lon, ctr_lat, 8)
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
            layer_name="Other agri services",
            icon_colors=["#546e7a"] * len(other),
            popup=["name", "category"],
        )

    if show_heatmap and len(facilities) > 3:
        m.add_heatmap(
            facilities[["lat", "lon"]],
            latitude="lat",
            longitude="lon",
            name="Facility density",
        )

    if coverage_geo is not None and not coverage_geo.empty:
        m.add_geojson(coverage_geo.__geo_interface__, layer_name="Village coverage buffer")

    if not villages.empty:
        m.add_points_from_xy(
            villages,
            x="lon",
            y="lat",
            layer_name="Villages",
            icon_colors=["#9e9e9e"] * len(villages),
            popup=["name", "covered"],
        )

    legend = {category: cfg["color"] for category, cfg in SERVICE_CATEGORIES.items()}
    legend["Other agri services"] = "#546e7a"
    try:
        m.add_legend(title="Agricultural service types", legend_dict=legend)
    except Exception:
        # Leafmap legend helper is optional; ignore if unavailable in current runtime.
        pass

    m.to_streamlit(height=640)


def compute_coverage(facilities: gpd.GeoDataFrame, villages: gpd.GeoDataFrame, buffer_km: int):
    if facilities.empty or villages.empty:
        return {
            "total_villages": len(villages),
            "covered": 0,
            "pct": 0.0,
            "coverage_geo": gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"),
            "villages": villages,
        }

    buffer_m = buffer_km * 1000
    facilities_m = facilities.to_crs(3857)
    coverage_area = facilities_m.buffer(buffer_m)
    coverage_union = coverage_area.unary_union
    villages_m = villages.to_crs(3857)
    villages = villages.copy()
    villages["covered"] = villages_m.geometry.apply(lambda g: coverage_union.contains(g))
    total_villages = len(villages)
    covered = int(villages["covered"].sum())
    pct = (covered / total_villages) * 100 if total_villages else 0
    coverage_geo = gpd.GeoSeries([coverage_union], crs=3857).to_crs(4326)
    return {
        "total_villages": total_villages,
        "covered": covered,
        "pct": pct,
        "coverage_geo": coverage_geo.to_frame(name="geometry"),
        "villages": villages,
    }


def main():
    hero_col, info_col = st.columns([2.5, 1])
    with hero_col:
        st.title("Agricultural Service Accessibility Explorer")
        st.markdown(
            """
            Visualise agricultural support nodes across India, measure rural coverage, and export ready-to-use
            datasets for further analysis. Powered by OpenStreetMap, ArcGIS Living Atlas basemaps, and entirely open data.
            """
        )
    with info_col:
        st.markdown(
            """
            **How to use**

            1. Choose a district, city, or block in the sidebar.
            2. Select the ArcGIS basemap and analytical overlays.
            3. Click **Update map** to fetch the latest open data snapshot.
            """
        )

    with st.sidebar:
        st.header("Analysis controls")
        with st.form("controls"):
            area = st.text_input("District / City / Block", "Ranchi, Jharkhand")
            basemap_choice = st.selectbox("ArcGIS basemap", list(ARC_GIS_BASEMAPS.keys()))
            buffer_km = st.slider("Village coverage buffer (km)", 1, 25, 10)
            show_villages = st.toggle("Overlay villages (OSM place=village/hamlet)", value=True)
            heatmap_on = st.toggle("Show density heatmap", value=True)
            overlay_cropland = st.toggle(
                "ArcGIS global cropland overlay", value=False,
                help="Adds the FAO/NASA cropland raster from ArcGIS Living Atlas"
            )
            submitted = st.form_submit_button("Update map", type="primary")
        st.caption(
            "ArcGIS basemaps and cropland layers © Esri, FAO, NASA (open for non-commercial use)."
        )

    tabs = st.tabs(["Interactive map", "Insights", "Data & downloads"])

    if not submitted:
        with tabs[0]:
            st.info("Configure the study area in the sidebar and click **Update map** to draw the accessibility view.")
        return

    try:
        with st.spinner("Fetching geographies and facilities..."):
            bbox, facilities = fetch_facilities(area)
            bbox_tuple = tuple(bbox)
            villages = (
                fetch_villages(bbox_tuple)
                if show_villages
                else gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
            )
    except ValueError as exc:
        with tabs[0]:
            st.error(str(exc))
        with tabs[1]:
            st.info("Update the place name or broaden the search region to continue.")
        return
    except RequestException as exc:
        msg = "Unable to reach the open data services right now. Please retry in a few minutes."
        with tabs[0]:
            st.error(msg)
        with tabs[1]:
            st.info("Network connectivity or public API limits may temporarily block the request.")
        st.caption(f"Debug info: {exc}")
        return

    if facilities.empty:
        with tabs[0]:
            st.warning("No agricultural support facilities found in this area via OpenStreetMap.")
        with tabs[1]:
            st.info("Try a neighbouring district or adjust the search name for broader coverage.")
        return

    coverage = compute_coverage(facilities, villages, buffer_km)
    coverage_geo = coverage["coverage_geo"] if not coverage["coverage_geo"].empty else None

    with tabs[0]:
        render_map(
            facilities,
            coverage["villages"],
            coverage_geo,
            bbox,
            basemap_choice,
            heatmap_on,
            overlay_cropland,
        )

    with tabs[1]:
        st.subheader("Coverage metrics")
        metric_cols = st.columns(4)
        metric_cols[0].metric("Facilities mapped", f"{len(facilities):,}")
        metric_cols[1].metric("Village coverage", f"{coverage['covered']:,}/{coverage['total_villages']:,}" if coverage["total_villages"] else "0")
        metric_cols[2].metric("Coverage %", f"{coverage['pct']:.1f}%" if coverage["total_villages"] else "0%")
        metric_cols[3].metric("Buffer radius", f"{buffer_km} km")

        st.markdown(
            """
            **Facility mix** — Understand which support services dominate and where diversification is required.
            """
        )
        summary = (
            facilities.groupby("category").size().reset_index(name="count").sort_values("count", ascending=False)
        )
        if not summary.empty:
            st.dataframe(summary, use_container_width=True)
            chart_data = summary.set_index("category")
            st.bar_chart(chart_data)

        if coverage["total_villages"] and coverage["total_villages"] > coverage["covered"]:
            st.warning(
                f"{coverage['total_villages'] - coverage['covered']:,} villages fall outside the {buffer_km} km reach of mapped facilities."
            )
        elif coverage["total_villages"]:
            st.success("All mapped villages lie within the specified coverage radius.")
        else:
            st.info("Village centroids unavailable in this area via OSM; coverage metric limited to facility counts.")

        with st.expander("Methodology & data sources", expanded=False):
            st.markdown(
                dedent(
                    """
                    - **Geocoding** — Boundary derived via Nominatim (OpenStreetMap).
                    - **Facilities** — Queried live from OpenStreetMap using curated tag selectors for agricultural infrastructure.
                    - **Villages** — OSM `place=village|hamlet` centroids to approximate settlement coverage.
                    - **Basemap & cropland overlay** — ArcGIS Living Atlas services for contextual cartography and cropland intensity.
                    - **Distance metric** — Straight-line (Euclidean) buffer in Web Mercator. Consider road networks for routing-based studies.
                    """
                )
            )

    with tabs[2]:
        st.subheader("Download datasets")
        st.download_button(
            "Download facilities (GeoJSON)",
            data=facilities.to_json(),
            file_name=f"agri_services_{area.replace(',', '_').replace(' ', '_')}.geojson",
            mime="application/geo+json",
        )
        st.download_button(
            "Download facilities (CSV)",
            data=facilities.drop(columns=["geometry"]).to_csv(index=False),
            file_name=f"agri_services_{area.replace(',', '_').replace(' ', '_')}.csv",
            mime="text/csv",
        )
        if coverage["total_villages"]:
            st.download_button(
                "Download villages with coverage flag (GeoJSON)",
                data=coverage["villages"].to_json(),
                file_name=f"villages_coverage_{area.replace(',', '_').replace(' ', '_')}.geojson",
                mime="application/geo+json",
            )

        st.markdown("### Data preview")
        st.dataframe(facilities.head(100), use_container_width=True)
        if coverage["total_villages"]:
            st.dataframe(coverage["villages"].head(100), use_container_width=True)


if __name__ == "__main__":
    main()
