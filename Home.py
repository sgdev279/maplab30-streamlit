import streamlit as st

st.set_page_config(page_title="MapLab 30 — Cross-Domain GIS Micro-Apps", layout="wide")
st.title("MapLab 30 — Cross-Domain GIS Micro-Apps")

st.markdown(
    """
Welcome! This is a tiny, open-source, Streamlit-based GIS app aligned with #30DayMapChallenge.
Each page is a micro-tool that solves a small, real problem using open data.

**How to run locally**
1. `pip install -r requirements.txt`
2. `streamlit run Home.py`

Use the sidebar to pick a day.
    """
)
