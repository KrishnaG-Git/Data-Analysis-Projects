# aqi_analysis/streamlit_app/pages/aqi_overview.py
import streamlit as st
import streamlit.components.v1 as components
from streamlit_extras.stylable_container import stylable_container
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
# Use relative imports to ensure modules are found correctly within the package
from ..data_loader import load_aqi_table
from .aqi_overview_components import display_pollution_composition_table
from .monthly_aqi_trends import display_monthly_aqi_chart_and_get_summary
from .weekend_vs_weekday_aqi import (
    load_and_prepare_metro_aqi_data,
    get_weekend_weekday_analysis_components,
    get_city_aqi_category_breakdown_data,
)
def load_css(css_path: Path):
    """
    Load and inject styles.css from streamlit_app/css into your Streamlit app.
    """
    css_path = Path(__file__).parent / "css" / "styles.css"
    if css_path.is_file():
        css = css_path.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# --- Cache raw AQI load + typing ---
@st.cache_data
def load_and_prepare_data() -> pd.DataFrame:
    # Request without UT merge → keeps 32 states
    df = load_aqi_table(merge_ut=False)
    df["date"] = pd.to_datetime(df["date"])
    df["aqi_value"] = pd.to_numeric(df["aqi_value"], errors="coerce")
    return df
    
def app():
    """
    The main function for the AQI Overview page.
    This sets up the layout, loads the data, and displays charts and metrics.
    """
    css_path = Path.cwd() / "css" / "styles.css"
    load_css(css_path)
    # 1) Load full AQI dataset
    aqi_df = load_and_prepare_data()
    min_d, max_d = aqi_df["date"].dt.date.min(), aqi_df["date"].dt.date.max()

    # 2) Sidebar date picker
    start_d = st.sidebar.date_input(
        "Start date", value=min_d, min_value=min_d, max_value=max_d
    )
    end_d = st.sidebar.date_input(
        "End date", value=max_d, min_value=min_d, max_value=max_d
    )
    if start_d > end_d:
        st.sidebar.error("Start date must be on or before end date")
        st.stop()

    # 3) Filter the slice for tab1 metrics
    mask = (aqi_df["date"].dt.date >= start_d) & (aqi_df["date"].dt.date <= end_d)
    filtered = aqi_df.loc[mask]

    # c) Four metrics
    total_stations = (
        aqi_df[['state','area','number_of_monitoring_stations']]
        .drop_duplicates('area')
        .sum()['number_of_monitoring_stations']
    )
    num_states = (
    aqi_df['state']
    .astype(str)                # ensure strings
    .str.strip()                 # remove spaces
    .str.replace(r'\s+', ' ', regex=True)  # collapse multiple spaces
    .str.title()                 # consistent casing
    .nunique()
)
    crit_days  = aqi_df[aqi_df['aqi_value'] > 300]['date'].nunique()

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
    avg_aqi = round(filtered["aqi_value"].mean())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall Average AQI", avg_aqi)
    c2.metric("Total Monitoring Stations", total_stations)
    c3.metric("Number of States", num_states)
    c4.metric("Critical AQI Days ( >300 )", crit_days)

    # 4) Prepare Tab layout
    tab1, tab2 = st.tabs(["AQI Insights", "Metro AQI Insights"])

    # --- Tab 1: City AQI Insights ---
    with tab1:
        # a) Overall avg gauge
        avg_aqi = round(filtered["aqi_value"].mean())
        

        # b) Top-5 / Bottom-5 areas
        area_avg = (
            filtered.groupby("area", as_index=False)["aqi_value"]
            .mean().rename(columns={"aqi_value":"avg_aqi"})
        )
        area_avg["area"] = area_avg["area"].str.title()
        top_five = area_avg.nlargest(5, "avg_aqi")
        bot_five = area_avg.nsmallest(5, "avg_aqi")

        fig_top = px.bar(
        top_five,
        x="avg_aqi",
        y="area",
        orientation="h",
        text="avg_aqi"
    )

        fig_top.update_traces(
            texttemplate="%{x:.0f}",
            textfont=dict(color="white", size=11)
        )

        fig_top.update_layout(
            title_text='',          # clear out undefined
            height=200,
            width=350,
            bargap=0.3,
            title_font_size=13,
            margin=dict(t=30, b=0, l=60, r=0),
            xaxis=dict(
                title=None,
                showticklabels=False,
                showgrid=False
            ),
            yaxis=dict(
                title=None,
                showticklabels=True,
                categoryorder="total ascending"
            )
        )


        fig_bot = px.bar(
        bot_five,
        x="avg_aqi",
        y="area",
        orientation="h",
        text="avg_aqi"
    )

        fig_bot.update_traces(
            texttemplate="%{x:.0f}",
            textfont=dict(color="white", size=11)
        )

        # Option A: clear with title_text
        fig_bot.update_layout(
            title_text='',         # <- blank out the title
            height=200,
            width=350,
            bargap=0.3,
            margin=dict(t=30, b=0, l=60, r=0),
            xaxis=dict(title=None, showticklabels=False, showgrid=False),
            yaxis=dict(title=None, showticklabels=True, categoryorder="total ascending")
        )
        fig_monthly, worst_summary = display_monthly_aqi_chart_and_get_summary(filtered)
        
        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            st.markdown("**Top-5 Polluted Areas**")
            st.plotly_chart(fig_top, use_container_width=False, width=350, height=200)
            st.markdown("**Bottom-5 Polluted Areas**")
            st.plotly_chart(fig_bot, use_container_width=False, width=350, height=200)

        with col2:
            st.markdown("**Worst AQI Months**")
            if not worst_summary.empty:
                st.dataframe(
                    worst_summary,
                    hide_index=True,
                    use_container_width=True,
                    width=300,
                    height=470
                )
            else:
                st.info("No monthly data available.")

        with col3:
            st.markdown("**Monthly AQI Trends**")
            st.plotly_chart(
                fig_monthly,
                use_container_width=False,
                width=300,
                height=500
            )
        

    # --- Tab 2: Metro AQI Analyses ---
    with tab2:
        
        ts, te = pd.to_datetime(start_d), pd.to_datetime(end_d)
        metro_df = load_and_prepare_metro_aqi_data(ts, te)

        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            st.subheader("Weekday vs Weekend AQI")
            st.markdown("____")
            fig, raw_cmp, styled_cmp, _ = get_weekend_weekday_analysis_components(ts, te)
            if raw_cmp.empty:
                st.warning("No metro-city data for selected dates.")
            else:
                st.dataframe(styled_cmp, use_container_width=True,hide_index=True,height=265)

        with col2:
            st.subheader("AQI Category Breakdown")
            if metro_df.empty:
                st.info("No metro-city data to break down.")
            else:
                city = st.selectbox(
                    "",
                    sorted(metro_df["area_title"].unique()),
                    key="overview_city"
                )
                breakdown_df = get_city_aqi_category_breakdown_data(metro_df, city)
                if breakdown_df.empty:
                    st.info(f"No breakdown data for {city}.")
                else:
                    st.dataframe(breakdown_df, hide_index=True, use_container_width=True)

        with col3:
            st.subheader("Pollution Composition")
            display_pollution_composition_table(filtered)

if __name__ == "__main__":
    app()
