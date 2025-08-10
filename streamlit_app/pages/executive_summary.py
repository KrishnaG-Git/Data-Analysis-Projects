# aqi_analysis/streamlit_app/pages/aqi_overview.py

import json
from pathlib import Path

import pandas as pd
import streamlit as st
import altair as alt
from .state_risk import compute_state_risk
from ..data_loader import load_aqi_table, load_vahan_table
from .aqi_overview_components import get_pollution_composition

# Define the multi-stage filter description once
FILTER_TEXT = (
    "Pre-filter; "
    "H13/H14 HEPA; "
    "Act.Carbon; "
    "Cat.Filter (optional); "
    
    "4 or 4+ stages;"
)


def normalize_state_name(name: str) -> str:
    return name.strip().title()


@st.cache_data
def load_and_prepare_data() -> pd.DataFrame:
    df = load_aqi_table(merge_ut=False)
    df["date"] = pd.to_datetime(df["date"])
    df["aqi_value"] = pd.to_numeric(df["aqi_value"], errors="coerce")
    return df


@st.cache_data
def load_related_topics() -> pd.DataFrame:
    csv = Path(__file__).parents[2] / "data" / "clean_data" / "related_topic.csv"
    df = pd.read_csv(csv)
    df.rename(columns=str.capitalize, inplace=True)
    df["Topic"] = df["Topic"].str.capitalize()
    return df


@st.cache_data
def load_geo_states() -> pd.DataFrame:
    geo = Path(__file__).parents[2] / "data" / "clean_data" / "india_state.json"
    raw = json.loads(geo.read_text("utf-8"))
    feats = raw.get("features") or ([raw] if raw.get("type") == "Feature" else [])
    states = [
        normalize_state_name(
            f["properties"].get("name", "") or f["properties"].get("id", "")
        )
        for f in feats
    ]
    return pd.DataFrame({"state": states})


@st.cache_data
def load_web_geo_map() -> pd.DataFrame:
    csv = Path(__file__).parents[2] / "data" / "clean_data" / "web_geo_map.csv"
    return pd.read_csv(csv)


@st.cache_data
def load_city_shopping_map() -> pd.DataFrame:
    csv = Path(__file__).parents[2] / "data" / "clean_data" / "city_shopping_map.csv"
    df = pd.read_csv(csv)
    df.columns = df.columns.str.strip().str.lower()
    if not {"city", "count"}.issubset(df.columns):
        raise KeyError("city_shopping_map.csv must have 'city' and 'count' columns")
    df = df.rename(columns={"city": "City", "count": "Count"})
    df["City"] = df["City"].str.title()
    return df


@st.cache_data
def load_websearch_trends() -> pd.DataFrame:
    csv = Path(__file__).parents[2] / "data" / "clean_data" / "websearch_google_trend.csv"
    return pd.read_csv(csv, parse_dates=["date"])


@st.cache_data
def load_shopping_trends() -> pd.DataFrame:
    csv = Path(__file__).parents[2] / "data" / "clean_data" / "google_shopping_search.csv"
    return pd.read_csv(csv, parse_dates=["date"])


def app():
    # 1) Load & filter AQI
    aqi_df = load_and_prepare_data()
    min_date, max_date = (
        aqi_df["date"].dt.date.min(),
        aqi_df["date"].dt.date.max(),
    )

    start_date = st.sidebar.date_input(
        "Start date", value=min_date, min_value=min_date, max_value=max_date
    )
    end_date = st.sidebar.date_input(
        "End date", value=max_date, min_value=min_date, max_value=max_date
    )
    if start_date > end_date:
        st.sidebar.error("Start date must be on or before End date")
        st.stop()

    mask = (aqi_df["date"].dt.date >= start_date) & (
        aqi_df["date"].dt.date <= end_date
    )
    filtered = aqi_df.loc[mask]

    # 2) Tabs (now 3 tabs)
    tab1, tab2, tab3 = st.tabs(["Google Trends", "Summary", "Pollutants & Filters"])

    # Tab 1: Trends & Counts
    with tab1:
        st.markdown("📋 **State‐level Air Purifier Google Search & Trend**")
        related_df = load_related_topics()
        states_df = load_geo_states()
        values_df = load_web_geo_map()
        city_df = load_city_shopping_map()
        trend_df = load_websearch_trends()
        shop_df = load_shopping_trends()

        merged_df = (
            states_df
            .merge(values_df, on="state", how="left")
            .dropna(subset=["count"])
            .sort_values("count", ascending=False)
            .reset_index(drop=True)
            .rename(columns={"state": "State", "count": "Count"})
        )

        col1, col2, col3 = st.columns([3, 3, 3])
        with col1:
            st.markdown("**State Purifier Counts**")
            st.dataframe(
                merged_df,
                hide_index=True,
                width=300,
                height=265,
            )
            st.markdown("**Related Topics**")
            st.dataframe(
                related_df,
                hide_index=True,
                width=300,
                height=265,
            )

        with col2:
            st.markdown("**Google Search Trend**")
            st.line_chart(
                trend_df.set_index("date")["count"],
                use_container_width=False,
                width=300,
                height=260,
            )
            st.markdown("**Google Shopping Trend**")
            st.line_chart(
                shop_df.set_index("date")["count"],
                use_container_width=False,
                width=300,
                height=250,
            )

        with col3:
            st.markdown("**City Shopping Count**")
            city_sorted = city_df.sort_values("Count", ascending=False).reset_index(drop=True)
            chart = (
                alt.Chart(city_sorted)
                .mark_circle(opacity=0.8, tooltip=True)
                .encode(
                    x=alt.X(
                        "City:N",
                        sort=alt.EncodingSortField(field="Count", order="descending"),
                    ),
                    y=alt.Y("Count:Q"),
                    size=alt.Size("Count:Q", legend=None, scale=alt.Scale(range=[100, 2000])),
                    tooltip=["City", "Count"],
                )
                .properties(width=300, height=600)
                .configure_axis(labelAngle=-45)
            )
            st.altair_chart(chart, use_container_width=False)

    # Tab 2: Executive Summary (removed pollution composition)
    with tab2:
        

        avg_aqi = round(filtered["aqi_value"].mean())
        
        crit_days = aqi_df[aqi_df["aqi_value"] > 300]["date"].nunique()
        num_states = (
            aqi_df["state"]
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
            .str.title()
            .nunique()
        )
        st.markdown(
    """
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
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Overall Average AQI", avg_aqi)
        c2.metric("Total Risk Areas", 20)
        c3.metric("Number of States", num_states)
        c4.metric("Critical AQI Days (>300)", crit_days)

        st.markdown("---")

        col_top5, col_ev = st.columns([1, 1])
        with col_top5:
            st.markdown("**Top-5 Polluted Areas**")
            area_avg = (
                filtered.groupby("area", as_index=False)["aqi_value"]
                .mean()
                .rename(columns={"area": "Area", "aqi_value": "Avg AQI"})
            )
            area_avg["Area"] = area_avg["Area"].str.title()
            top5 = area_avg.nlargest(5, "Avg AQI")
            row_df = pd.DataFrame([top5["Avg AQI"].values], columns=top5["Area"].values)
            st.dataframe(
                row_df,
                hide_index=True,
                width=450,
                height=70,
            )

        with col_ev:
            st.markdown("**Top-4 States by EV Count**")
            vahan_df = load_vahan_table()
            if not vahan_df.empty:
                vahan_df["state"] = vahan_df["state"].apply(normalize_state_name)
                ev_df = vahan_df[vahan_df["fuel"].str.lower() == "ev"]
                ev_by_state = (
                    ev_df
                    .groupby("state", as_index=False)["value"]
                    .sum()
                    .rename(columns={"state": "State", "value": "EV Count"})
                )
                top4 = ev_by_state.nlargest(4, "EV Count")
                row_ev = pd.DataFrame(
                    [top4["EV Count"].values],
                    columns=top4["State"].values
                )
                st.dataframe(
                    row_ev,
                    hide_index=True,
                    width=450,
                    height=70,
                )
            else:
                st.info("No EV data available.")

        st.markdown("---")

        st.subheader("Top 20 Polluted Areas Across India")
        risk_year = end_date.year
        _, _, global_areas_df = compute_state_risk(
            target_year=risk_year,
            top_states=0,
            top_areas_per_state=0,
            top_global_areas=1
        )
        global_areas_df = (
            global_areas_df
            .rename(columns={
                "state": "State",
                "area":  "Area",
                "avg_aqi": "Avg AQI"
            })
        )
        global_areas_df["Area"]  = global_areas_df["Area"].str.title()
        global_areas_df["State"] = global_areas_df["State"].str.title()
        height_px = 50 + len(global_areas_df) * 30
        st.dataframe(
            global_areas_df,
            hide_index=True,
            width=700,
            height=height_px
        )

    # Tab 3: Pollutants & Filters (moved tables here)
    with tab3:
        col_si, col_ri = st.columns([1, 1])
        row_height = 35
        header_height = 38

        with col_si:
            st.markdown("**Pollution Composition — Southern India**")
            comp_si = get_pollution_composition(filtered, "Southern India")
            if not comp_si.empty:
                comp_si = comp_si.drop(columns=["Lowest"], errors="ignore")
                comp_si["Filters and Pre-filter"] = FILTER_TEXT
                height_si = header_height + len(comp_si) * row_height
                st.dataframe(
                    comp_si,
                    hide_index=True,
                    width=820,
                    height=height_si,
                )
            else:
                st.info("No Southern India data available for the selected date range.")

        with col_ri:
            st.markdown("**Pollution Composition — Rest of India (Top 10)**")
            comp_ri = get_pollution_composition(filtered, "Rest of India")
            if not comp_ri.empty:
                comp_ri = comp_ri.drop(columns=["Lowest"], errors="ignore")
                comp_ri["Filters and Pre-filter"] = FILTER_TEXT
                height_ri = header_height + len(comp_ri) * row_height
                st.dataframe(
                    comp_ri,
                    hide_index=True,
                    width=820,
                    height=height_ri,
                )
            else:
                st.info("No Rest of India data available for the selected date range.")



if __name__ == "__main__":
    app()
