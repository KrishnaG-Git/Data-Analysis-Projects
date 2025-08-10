from pathlib import Path
import pandas as pd
import streamlit as st

# Go up two levels (…/analysis → …/streamlit_app → project root), then into data/clean_data
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "clean_data"


@st.cache_data(ttl=3600)
def get_city_aqi_metrics(start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.DataFrame:
    """
    - Loads aqi_clean.csv & population_clean.csv
    - Filters AQI by [start_ts, end_ts] and population by year-2024
    - Returns DataFrame with columns: City, Population, Average AQI
    """
    # 1) City-level AQI
    aqi_df = pd.read_csv(
        DATA_DIR / "aqi_clean.csv",
        parse_dates=["date"],
        usecols=["date", "area", "aqi_value"],
    )
    df_aqi = (
        aqi_df[(aqi_df.date >= start_ts) & (aqi_df.date <= end_ts)]
        .groupby("area")["aqi_value"]
        .mean()
        .reset_index(name="Average AQI")
        .rename(columns={"area": "City"})
    )

    # 2) City population (pop_total in thousands → persons)
    pop_df = pd.read_csv(DATA_DIR / "population_clean.csv")
    if "year" in pop_df.columns:
        pop_df = pop_df[pop_df.year == 2024]

    pop_df["Population"] = pop_df["pop_total"] * 1_000
    df_pop = (
        pop_df
        .rename(columns={"state": "City"})
        [["City", "Population"]]
    )

    # 3) Merge on City
    return df_pop.merge(df_aqi, on="City", how="inner")


@st.cache_data(ttl=3600)
def get_state_aqi_metrics(
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    pop_year: int = 2024
) -> pd.DataFrame:
    """
    - Loads aqi_clean.csv & population_clean.csv
    - Filters AQI by [start_ts, end_ts] and population by pop_year
    - Returns DataFrame with columns: State, Population, Average AQI
    """
    # 1) State-level AQI
    aqi_df = pd.read_csv(
        DATA_DIR / "aqi_clean.csv",
        parse_dates=["date"],
        usecols=["date", "state", "aqi_value"],
    )
    df_aqi = (
        aqi_df[(aqi_df.date >= start_ts) & (aqi_df.date <= end_ts)]
        .groupby("state")["aqi_value"]
        .mean()
        .reset_index(name="Average AQI")
        .rename(columns={"state": "State"})
    )

    # 2) State population (pop_total in thousands → persons)
    pop_df = pd.read_csv(DATA_DIR / "population_clean.csv")
    if "year" in pop_df.columns:
        pop_df = pop_df[pop_df.year == pop_year]

    pop_df["Population"] = pop_df["pop_total"]
    df_pop = (
        pop_df
        .rename(columns={"state": "State"})
        [["State", "Population"]]
    )

    # 3) Merge on State
    return df_pop.merge(df_aqi, on="State", how="inner")
