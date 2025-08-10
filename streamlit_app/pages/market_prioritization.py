import altair as alt
import pandas as pd
import streamlit as st

from .ev_aqi_analysis import (
    load_aqi,
    load_geo,
    compute_avg_aqi,
    compute_ev_scores,
    create_ev_aqi_deck,
    make_summary,
)
from .citypop_aqi import get_state_aqi_metrics
from .state_risk import compute_state_risk

# IMPORT your projection functions
from streamlit_app.pages.health_cost_proj import compute_health_cost_impacts

# Optional CSS tweak
st.markdown(
    """
    <style>
      .main .block-container { min-height:100vh; }
      div[data-testid="deckgl-json-chart"],
      div[data-testid="vega-lite-chart"] { height:100% !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

def app():
    # 1) Load & date‐filter AQI
    with st.spinner("🔄 Loading AQI data..."):
        aqi_df = load_aqi()

    min_d = aqi_df["date"].dt.date.min()
    max_d = aqi_df["date"].dt.date.max()
    st.sidebar.header("Date Filter")
    start_date = st.sidebar.date_input("Start", min_d, min_d, max_d)
    end_date   = st.sidebar.date_input("End",   max_d, min_d, max_d)
    if start_date > end_date:
        st.sidebar.error("Start date must be on or before End date.")
        st.stop()

    start_ts, end_ts = pd.to_datetime(start_date), pd.to_datetime(end_date)

    # --- KPI Section ---
    state_metrics = get_state_aqi_metrics(start_ts, end_ts)
    total_states = state_metrics["State"].nunique()
    ev_df = compute_ev_scores()
    total_evs = ev_df["EVs"].sum() if "EVs" in ev_df.columns else ev_df.iloc[:,1].sum()

    

    # ───────────────────────────────────────────────────────────────────────────────
    # 2) Create three tabs
    # ───────────────────────────────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs([
        "📊 AQI, Population & Risk",
        "💸 Health Cost Projections",
        "🏆 Market Competitors & Features"
    ])

    # ───────────────────────────────────────────────────────────────────────────────
    # TAB 1: Market Prioritization (show metrics + your existing layout)
    # ───────────────────────────────────────────────────────────────────────────────
    with tab1:
        # KPI row – only here
        st.markdown("""
    <style>
    /* Target the metric value text */
    div[data-testid="stMetricValue"] {
        font-weight: 700 !important; /* 700 = bold */
        font-size: 20px !important; /* Default is ~36px */
    }
    /* Target the metric label text */
    div[data-testid="stMetricLabel"] {
        font-weight: 700 !important; /* 700 = bold */
        font-size: 14px !important; /* Default is ~14px but can shrink more */
    }
    </style>
    """,
    unsafe_allow_html=True
)
        kpi_col1, kpi_col2 = st.columns(2)
        kpi_col1.metric("Number of States", total_states)
        kpi_col2.metric("Total Number of EVs", f"{total_evs:,.0f}")

        # Row 1: Population vs AQI
        row1_col1, row1_col2 = st.columns([3, 2])
        with row1_col1:
            st.markdown("🏙️ **State Population vs Average AQI**")
            with st.spinner("🔢 Computing state‐level metrics…"):
                merged_state = get_state_aqi_metrics(start_ts, end_ts)

            if merged_state.empty:
                st.warning("No overlapping states between your AQI & population files.")
                return

            scatter = (
                alt.Chart(merged_state)
                  .mark_circle(size=60, opacity=0.6)
                  .encode(
                      x=alt.X("Population:Q", scale=alt.Scale(type="log"), title="Population (log)"),
                      y=alt.Y("Average AQI:Q", title="Average AQI"),
                      tooltip=["State", "Population", "Average AQI"],
                  )
                  .properties(width=350, height=350)
            )
            st.altair_chart(scatter, use_container_width=False)

        with row1_col2:
            st.markdown("🚗 **EV Adoption vs AQI Impact**")
            with st.spinner("🌍 Rendering EV vs AQI map..."):
                geo     = load_geo()
                aqi_avg = compute_avg_aqi(start_ts, end_ts)
                ev_df   = compute_ev_scores()

                if "topo" in geo and geo["topo"]:
                    key    = geo["object_key"]
                    geoms  = geo["topo"]["objects"][key]["geometries"]
                    states = [g["properties"]["name"] for g in geoms]
                else:
                    states = [f["properties"]["name"] for f in geo["features"]]

                base   = pd.DataFrame({"State": states})
                merged = (
                    base
                      .merge(aqi_avg, on="State", how="left")
                      .merge(ev_df, on="State", how="left")
                )

                deck = create_ev_aqi_deck(merged, geo)
            st.pydeck_chart(deck, use_container_width=False, height=350)

        # Row 2: Risk & Top Areas
        row2_col1, row2_col2 = st.columns([3, 2])
        with row2_col1:
            st.markdown("⚠️**State Risk Scores (2024–25)**")
            with st.spinner("🔢 Computing state‐level risk…"):
                risk_df, areas_df,_ = compute_state_risk(target_year=2025)

            if risk_df.empty:
                st.warning("No states found for risk computation.")
            else:
                bar = (
                    alt.Chart(risk_df.head(10))
                      .mark_bar()
                      .encode(
                          x=alt.X("risk_score:Q", title="Risk Score"),
                          y=alt.Y("state:N", sort="-x", title="State"),
                          tooltip=["avg_aqi", "population", "mpce_2024_25", "risk_score"],
                      )
                      .properties(width=350, height=300)
                )
                st.altair_chart(bar, use_container_width=False)

        with row2_col2:
            st.markdown("**Top AQI Areas in High-Risk States**")
            if not areas_df.empty:
                df = areas_df.copy()
                df["state"] = df["state"].str.title()
                df["area"]  = df["area"].str.title()
                df.columns  = df.columns.str.capitalize()

                options  = ["All States"] + df["State"].sort_values().unique().tolist()
                selected = st.selectbox("", options)
                if selected != "All States":
                    df = df[df["State"] == selected]

                st.dataframe(df.reset_index(drop=True), hide_index=True, height=230)
            else:
                st.warning("No area‐level AQI data available.")

    # ───────────────────────────────────────────────────────────────────────────────
    # TAB 2: Health Cost Projections (filters & chart removed)
    # ───────────────────────────────────────────────────────────────────────────────
    with tab2:
        st.markdown("### 💸 Health Cost Projections")
        with st.spinner("🔄 Running health‐cost pipeline…"):
            cost_df = compute_health_cost_impacts(target_year=2024)

        if cost_df.empty:
            st.warning("No health‐cost data returned. Check your data files.")
        else:
            df_india = (
                cost_df
                .assign(state="India")
                .groupby(["state","outcome"], as_index=False)
                .agg({
                    "attr_cases":       "sum",
                    "cost_min_person":  "first",
                    "cost_mean_person": "first",
                    "cost_max_person":  "first",
                })
                .query("attr_cases > 0")
                .dropna(
                    subset=["cost_min_person","cost_mean_person","cost_max_person"],
                    how="all"
                )
                .reset_index(drop=True)
            )

            st.dataframe(
                df_india[
                    ["state","outcome","cost_min_person","cost_mean_person","cost_max_person"]
                ],
                width=600, height=250, hide_index=True
            )

    # ───────────────────────────────────────────────────────────────────────────────
    # TAB 3: Market Competitors & Feature Gap
    # ───────────────────────────────────────────────────────────────────────────────
    with tab3:
        

        # 1) Build a single DataFrame with all brand info
        market_data = {
            "Brand": [
                "Philips",
                "Dyson",
                "Honeywell",
                "Sharp",
                "Xiaomi",
                "Coway",
            ],
            "Price Range (INR)": [
                "₹3,295 – ₹27,995",
                "₹23,844 – ₹68,900",
                "₹4,970 – ₹24,999",
                "₹5,990 – ₹32,999",
                "₹7,999 – ₹13,999",
                "₹500 – ₹83,455",
            ],
            "Coverage Area (Sq. Ft.)": [
                "215 – 851 (home); car model",
                "600 – 871; large/unspecified",
                "235 – 698",
                "25 – 680",
                "< 250 – 1,200",
                "21 – 1,256",
            ],
            "Filter Types": [
                "HEPA NanoProtect, Activated Carbon, Pre-filter, SelectFilter Plus",
                "HEPA H13, Activated Carbon, Catalytic filter",
                "Sponge Pre-filter, Pre-filter, H13 HEPA, Activated Carbon",
                "HEPA, True HEPA, Pre-filter, Activated Carbon, Deodorization, Ionizer, Humidifier Filter",
                "Primary Filter, True HEPA, Pre-filter, Activated Carbon",
                "Pre-filter, True HEPA (Anti-Flu, Bipolar), Urethane Carbon, Deodorization, EPA, 3-Stage",
            ],
            "Key Features": [
                "AQI Display, App Control, Auto Modes, Sleep Mode, Energy-Saving, Ultra-Quiet, 3-in-1, Compact",
                "Air Multiplier, 350° Oscillation, Real-time AQI (PM2.5/PM10), Enhanced NO₂ Capture, App/Remote Control, Heating & Cooling, Auto Sense, Quiet Operation, Formaldehyde Destruction, Wi-Fi, 2-yr Warranty",
                "CADR 450 m³/hr, Real-time PM2.5, Child Lock, < 30 dB Sleep Mode, 9 000-hr Filter Life, One-touch Control, 3D Airflow, Remote, 5-stage, Wi-Fi & Voice, AQI LED, Alexa, UV LED",
                "Plasmacluster Ion Tech, Mosquito Trap (UV + Glue), Humidification, Dehumidification, PM2.5/Temp/Humidity Display",
                "Wi-Fi & App Control, Voice Control, Real-time AQI, Fast Purification (7 min), Energy-Efficient, OLED Touch, 360° Filtration, Sleep Mode, CADR 380 m³/hr, Negative Ionizer, Triple-Layer, Alexa & Google",
                "Real-time AQI Monitor, Auto Mode, Filter-Clean Indicator, Virus Protection, Eco Mode, 7-yr Warranty, Ozone-Free, CARB & Energy Star",
            ],
        }
        market_df = pd.DataFrame(market_data)

        # 2) Brand selector
        brand_choice = st.selectbox("", market_df["Brand"].unique())

        # 3) Show the filtered table
        brand_df = market_df[market_df["Brand"] == brand_choice].set_index("Brand")
        st.dataframe(brand_df, use_container_width=True,width=250)

if __name__ == "__main__":
    app()
