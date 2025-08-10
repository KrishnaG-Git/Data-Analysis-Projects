import streamlit as st
from pathlib import Path
from streamlit_option_menu import option_menu
import base64

# ---------- Streamlit Config ----------
st.set_page_config(
    page_title="AQI Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Paths ----------
BASE_DIR = Path(__file__).resolve().parent
image_path = BASE_DIR / "assets" / "urban-air-pollution-monitoring.jpg"

# ---------- Convert Image to Base64 ----------
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# Encode image to base64
encoded_bg = get_base64_of_bin_file(image_path)

# ---------- Inject CSS for Background ----------
page_bg_img = f"""
<style>
.stApp {{
    background-image: url("data:image/jpg;base64,{encoded_bg}");
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
}}
</style>
"""
st.markdown(page_bg_img, unsafe_allow_html=True)

# ---------- Your Existing Imports ----------
APP_DIR = Path(__file__).parent

try:
    css_path = APP_DIR / "streamlit_app" / "css" / "styles.css"
    css_content = css_path.read_text()
    st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("Could not find the CSS file. Please ensure 'styles.css' is in the 'streamlit_app/css' subdirectory.")

from streamlit_app.pages.aqi_overview import app as aqi_overview_app
from streamlit_app.pages.executive_summary import app as executive_summary_app
from streamlit_app.pages.market_prioritization import app as market_prioritization_app
from streamlit_app.pages.health_burden_overview import app as health_burden_overview_app

# ---------- Pages ----------
PAGES = {
    "AQI Overview": aqi_overview_app,
    "Executive Summary": executive_summary_app,
    "Market Prioritization": market_prioritization_app,
    "Health Burden & Disease": health_burden_overview_app
}

with st.sidebar:
    choice = option_menu(
        menu_title="",
        options=list(PAGES.keys()),
        icons=["bar-chart", "clipboard-data", "map", "gear", "bandaid"],
        styles={
            "nav-link": {"font-size": "15px"},
            "nav-link-selected": {"font-size": "15px", "background-color": "#1f64e4"}
        }
    )

PAGES[choice]()
