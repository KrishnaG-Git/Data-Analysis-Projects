import json
from pathlib import Path

import pandas as pd
import streamlit as st
import pydeck as pdk

from streamlit_app.data_loader import load_aqi_table as _load_aqi, load_vahan_table as _load_vahan

def normalize_state(name: str) -> str:
    if not isinstance(name, str):
        return ""
    s = name.strip().title().replace(" & ", " And ")
    if s.endswith(" Islands"):
        s = s[: -len(" Islands")]
    return s

@st.cache_data
def load_aqi() -> pd.DataFrame:
    df = _load_aqi().rename(columns=str.lower)
    df["state"] = df["state"].map(normalize_state)
    df["date"]  = pd.to_datetime(df["date"])
    return df

@st.cache_data
def load_vahan() -> pd.DataFrame:
    df = _load_vahan().rename(columns=str.lower)
    df["state"] = df["state"].map(normalize_state)
    return df

@st.cache_resource
def load_geo() -> dict:
    geo_path = Path(__file__).parents[2] / "data" / "clean_data" / "india_state.json"
    raw = json.loads(geo_path.read_text(encoding="utf-8"))
    # GeoJSON branch
    if raw.get("type") == "FeatureCollection":
        feats = raw["features"]
    elif raw.get("type") == "Feature":
        feats = [raw]
    else:
        feats = raw.get("features", [])
    for feat in feats:
        nm = feat["properties"].get("name") or feat["properties"].get("id","")
        feat["properties"]["name"] = normalize_state(nm)
    return {"features": feats}

@st.cache_data
def compute_avg_aqi(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    aqi = load_aqi()
    mask = (aqi.date >= start) & (aqi.date <= end)
    return (
        aqi.loc[mask]
           .groupby("state", as_index=False)["aqi_value"]
           .mean()
           .rename(columns={"state":"State","aqi_value":"Average AQI"})
    )

@st.cache_data
def compute_ev_scores() -> pd.DataFrame:
    v = load_vahan()
    ev = v[v.fuel.str.lower()=="ev"]
    return (
        ev.groupby("state", as_index=False)["value"]
          .sum()
          .rename(columns={"state":"State","value":"EV_Adoption_Score"})
    )

def make_summary(md: pd.DataFrame) -> str:
    valid = md.dropna(subset=["Average AQI","EV_Adoption_Score"])
    top5 = valid.nlargest(5,"EV_Adoption_Score")
    bot5 = valid.nsmallest(5,"EV_Adoption_Score")
    avg_top = top5["Average AQI"].mean() if not top5.empty else float("nan")
    avg_bot = bot5["Average AQI"].mean() if not bot5.empty else float("nan")
    text = (f"**Avg AQI (Top-5 EV):** {avg_top:.1f}  \n"
            f"**Avg AQI (Bottom-5 EV):** {avg_bot:.1f}  \n\n")
    text += ("✅ Higher-EV states have lower AQI."
             if avg_top < avg_bot else
             "⚠️ No clear AQI benefit for higher-EV states.")
    return text
def create_ev_aqi_deck(merged: pd.DataFrame, geo: dict) -> pdk.Deck:
    merged["AQI_for_plot"] = pd.to_numeric(merged.get("Average AQI"), errors="coerce").fillna(-1)
    amin, amax = merged["AQI_for_plot"].replace(-1, pd.NA).agg(["min", "max"])

    def aqi_to_rgb(val):
        if val < 0 or pd.isna(val): return [220, 220, 220]
        frac = (val - amin) / (amax - amin) if amax > amin else 0.5
        return [int(255 * frac), int(255 * (1 - frac)), 0]  # yellow to red

    # ── 1. Annotate GeoJSON features with color and data
    features = geo.get("features", [])
    for feat in features:
        state = feat["properties"]["name"]
        row = merged[merged["State"] == state]
        if not row.empty:
            aqi = row["AQI_for_plot"].values[0]
            ev  = row["EV_Adoption_Score"].values[0]
            feat["properties"]["fill_color"] = aqi_to_rgb(aqi)
            feat["properties"]["State"] = state
            feat["properties"]["Average AQI"] = f"{aqi:.1f}" if pd.notna(aqi) else "N/A"
            feat["properties"]["EV_Adoption_Score"] = f"{int(ev):,}" if pd.notna(ev) else "N/A"
        else:
            feat["properties"]["fill_color"] = [220, 220, 220]
            feat["properties"]["State"] = state
            feat["properties"]["Average AQI"] = "N/A"
            feat["properties"]["EV_Adoption_Score"] = "N/A"

    geo_fc = {"type": "FeatureCollection", "features": features}
    choropleth = pdk.Layer(
        "GeoJsonLayer",
        geo_fc,
        pickable=True,
        stroked=True,
        filled=True,
       
        get_fill_color="properties.fill_color",
        get_line_color=[255, 255, 255],
        line_width_min_pixels=1,
    )

    # ── 2. Compute centroids and merge with data for bubbles
    centroids = []
    for feat in features:
        coords = feat["geometry"]["coordinates"]
        pts = []

        def gather(x):
            if isinstance(x, (list, tuple)):
                if len(x) == 2 and all(isinstance(i, (int, float)) for i in x):
                    pts.append(x)
                else:
                    for sub in x:
                        gather(sub)

        gather(coords)
        if not pts: continue

        lon = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        state = feat["properties"]["name"]
        row = merged[merged["State"] == state]
        if not row.empty:
            aqi = row["AQI_for_plot"].values[0]
            ev  = row["EV_Adoption_Score"].values[0]
        else:
            aqi = ev = None
        centroids.append({
    "State": state,
    "longitude": lon,
    "latitude": lat,
    "Average AQI": f"{aqi:.1f}" if pd.notna(aqi) else "N/A",
    "EV_Adoption_Score": f"{int(ev):,}" if pd.notna(ev) else "N/A",
    "raw_ev": 0 if pd.isna(ev) else ev
})

    cent_df = pd.DataFrame(centroids)
    max_ev = cent_df["raw_ev"].max() or 1
    cent_df["radius"] = cent_df["raw_ev"] / max_ev * 45000 + 5000

    bubble = pdk.Layer(
        "ScatterplotLayer",
        cent_df,
        pickable=True,
        opacity=0.8,
        get_position=["longitude", "latitude"],
        get_fill_color=[0, 0, 0],
        get_radius="radius",
    )

    # ── 3. Render
    view = pdk.ViewState(latitude=22.5, longitude=82.0, zoom=3.5)
    deck = pdk.Deck(
        layers=[choropleth, bubble],
        initial_view_state=view,
        map_style="light",
        tooltip={
            "html": "<b>{State}</b><br>AQI: {Average AQI}<br>EVs: {EV_Adoption_Score}",
            "style": {"backgroundColor": "black", "color": "white"}
        }
    )
    return deck

def get_ev_aqi_map_and_analysis(start,end):
    geo   = load_geo()
    a_df  = compute_avg_aqi(start,end)
    e_df  = compute_ev_scores()
    states = [f["properties"]["name"] for f in geo["features"]]
    base  = pd.DataFrame({"State":states})
    merged= base.merge(a_df,on="State",how="left").merge(e_df,on="State",how="left")
    summary = make_summary(merged)
    deck    = create_ev_aqi_deck(merged, geo)
    return deck, summary
