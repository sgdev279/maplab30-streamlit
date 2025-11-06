import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
from utils.aoi import nominatim_bbox
from utils.osm import pois_by_keyvalue

st.title("Day 01 — Essential Finder (Hospitals, ATMs, Pharmacies)")
st.caption("OpenStreetMap + Overpass • Interactive map • Download results • #30DayMapChallenge")

col1, col2 = st.columns([2,1], gap="large")
with col2:
    area = st.text_input("Area (city/district/campus):", "Ranchi, India")
    poi_type = st.selectbox("What to find?", ["hospital","pharmacy","atm","bank","school","fuel","supermarket"])
    limit = st.slider("Show top N nearest to map center", 10, 500, 100, 10)
    run = st.button("Fetch & Analyze")

with col1:
    m = leafmap.Map(minimap_control=False, draw_export=True)
    m.add_basemap("CartoDB.Positron")
    m.to_streamlit(height=640)

if run:
    try:
        bbox = nominatim_bbox(area)
        gdf = pois_by_keyvalue(bbox, "amenity", f"^{poi_type}$")
        if gdf.empty:
            st.warning("No POIs found. Try a broader area or a different type.")
        else:
            # center map by mean
            ctr = [gdf.geometry.y.mean(), gdf.geometry.x.mean()]
            m.set_center(ctr[1], ctr[0], 12)

            # compute simple 'distance to center' to rank within AOI
            gdf = gdf.copy()
            gdf["dist_deg"] = ((gdf.geometry.x - ctr[1])**2 + (gdf.geometry.y - ctr[0])**2) ** 0.5
            gdf = gdf.sort_values("dist_deg").head(limit)

            # show on map
            m.add_points_from_xy(
                gdf, x="lon", y="lat", layer_name=f"{poi_type}s",
                popup=["name","key","type"], icon_colors=["red"]*len(gdf)
            )
            m.to_streamlit(height=640)

            st.subheader("Top results")
            st.dataframe(gdf[["name","lon","lat"]])

            st.download_button("Download GeoJSON",
                               data=gdf.to_json(),
                               file_name=f"{poi_type}_{area.replace(',','_')}.geojson",
                               mime="application/geo+json")
    except Exception as e:
        st.error(str(e))
