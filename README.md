# Agricultural Service Accessibility Explorer (Streamlit)

An India-focused Streamlit experience for #30DayMapChallenge Day 01 (Points) that maps agricultural service points,
visualises their density with ArcGIS Living Atlas cartography, and measures village coverage gaps.

## Run locally
```
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Key capabilities
- ArcGIS imagery and terrain basemaps with optional cropland overlay for contextual cartography.
- Automated Overpass (OSM) queries for Krishi Vigyan Kendras, input retailers, soil labs, cold stores, dairy centres, and more.
- Village coverage analytics with configurable buffer distance and export-ready GeoJSON/CSV downloads.
