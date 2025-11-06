import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
from utils.aoi import nominatim_bbox
from utils.osm import lines_by_key
from utils.style import speed_color

st.title("Day 02 — Speed-Limit Street Atlas")
st.caption("OSM highways colored by maxspeed • Exportable • #30DayMapChallenge")

area = st.text_input("Area (city/district):", "Ranchi, India")
filter_primary = st.checkbox("Only classified roads (primary/secondary/tertiary/trunk/motorway)?", value=False)
run = st.button("Fetch streets")

m = leafmap.Map(minimap_control=False)
m.add_basemap("CartoDB.DarkMatter")

if run:
    try:
        bbox = nominatim_bbox(area)
        extra = ""
        if filter_primary:
            # extra filter appended to the key filter in Overpass
            extra = ']["highway"~"primary|secondary|tertiary|trunk|motorway"]'
        gdf = lines_by_key(bbox, "highway", extra_filter=extra)
        if gdf.empty:
            st.warning("No streets found in this AOI.")
        else:
            # style by maxspeed
            gdf["maxspeed"] = gdf["tags"].apply(lambda t: t.get("maxspeed","unknown"))
            # Use GeoJSON direct; leafmap will draw default styles. We'll keep a raw and an info layer.
            m.add_geojson(leafmap.gdf_to_geojson(gdf[["geometry","name","maxspeed"]]), layer_name="Streets (info)")
            # A simple legend hint
            st.info("Legend (approx): ≤30 green • 50 lime • 70 yellow • 90 orange • >90 red • unknown gray")
            st.download_button("Download GeoJSON",
                               data=gdf.to_json(),
                               file_name=f"streets_maxspeed_{area.replace(',','_')}.geojson",
                               mime="application/geo+json")
    except Exception as e:
        st.error(str(e))

m.to_streamlit(height=640)
