import pandas as pd
import streamlit as st
from pathlib import Path

# =========================================================================
# Data Loading Functions
# =========================================================================

# The path to the data directory is now relative to the parent of the parent 
# of this script, then into 'data/clean_data'.
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "clean_data"

def normalize_state_name(name: str) -> str:
    """Normalizes a state name for consistent matching."""
    if not isinstance(name, str):
        return name
    s = name.strip().title().replace(" & ", " And ").replace(" Of ", " of ")
    return s

def harmonize_state_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Harmonizes state names across different data sources to ensure consistency.
    This function now applies the mapping universally after normalization.
    
    Args:
        df (pd.DataFrame): The DataFrame to process.
    
    Returns:
        pd.DataFrame: The DataFrame with harmonized state names.
    """
    # This mapping is used to group various union territories into a single category
    # to match the GBD data, which treats them as 'Union Territories Other Than Delhi'.
    state_mapping_to_ut = {
        'Dadra And Nagar Haveli': 'Union Territories Other Than Delhi',
        'Daman And Diu': 'Union Territories Other Than Delhi',
        'Dadra And Nagar Haveli And Daman And Diu': 'Union Territories Other Than Delhi',
        'Ladakh': 'Union Territories Other Than Delhi',
        'Lakshadweep': 'Union Territories Other Than Delhi',
        'Andaman And Nicobar Islands': 'Union Territories Other Than Delhi',
        'Puducherry': 'Union Territories Other Than Delhi',
        'Chandigarh': 'Union Territories Other Than Delhi'
    }

    if 'state' in df.columns:
        # Normalize the state names first
        df['state'] = df['state'].apply(normalize_state_name)
        
        # Apply the UT mapping universally to align all data with the GBD format
        df['state'] = df['state'].replace(state_mapping_to_ut)
            
    return df

@st.cache_data(ttl=3600)
def load_aqi_table(merge_ut: bool = True) -> pd.DataFrame:
    """Loads and cleans the AQI data."""
    csv_file = DATA_DIR / "aqi_clean.csv"
    if not csv_file.exists():
        st.error(f"File not found: {csv_file}")
        return pd.DataFrame()

    df = pd.read_csv(
        csv_file,
        usecols=[
            "date",
            "state",
            "area",
            "number_of_monitoring_stations",
            "prominent_pollutants",
            "aqi_value",
            "air_quality_status",
        ],
        parse_dates=["date"],
        dtype={
            "state": "string",
            "area": "string",
            "prominent_pollutants": "string",
            "air_quality_status": "string",
            "number_of_monitoring_stations": "Int64",
            "aqi_value": "Int64",
        },
    )

    

    df.sort_values(["state", "area", "date"], inplace=True, ignore_index=True)
    return df

@st.cache_data(ttl=3600)
def load_vahan_table() -> pd.DataFrame:
    """Loads the vahan_clean.csv file."""
    csv_file = DATA_DIR / "vahan_clean.csv"
    if not csv_file.exists():
        st.error(f"File not found: {csv_file}")
        return pd.DataFrame()
    df = pd.read_csv(
        csv_file,
        dtype={
            "year": "Int64",
            "month": "string",
            "state": "string",
            "vehicle_class": "string",
            "fuel": "string",
            "value": "Int64",
        },
    )
    df.columns = df.columns.str.strip()
    return df

@st.cache_data(ttl=3600)
def load_idsp_table() -> pd.DataFrame:
    """Loads the IDSP (disease surveillance) data."""
    csv_file = DATA_DIR / "idsp_clean.csv"
    if not csv_file.exists():
        st.error(f"File not found: {csv_file}")
        return pd.DataFrame()
    df = pd.read_csv(
        csv_file,
        usecols=[
            "year",
            "week",
            "outbreak_starting_date",
            "reporting_date",
            "state",
            "district",
            "disease",
            "status",
        ],
        parse_dates=["outbreak_starting_date", "reporting_date"],
        dtype={
            "year": "Int64",
            "week": "Int64",
            "state": "string",
            "district": "string",
            "disease": "string",
            "status": "string",
        },
    )
    df["state"] = df["state"].apply(normalize_state_name)
    return df

@st.cache_data(ttl=3600)
def load_gbdhealth_df() -> pd.DataFrame:
    """Loads and cleans the GBD Health data."""
    path = DATA_DIR / "gbdhealth.csv"
    if not path.exists():
        st.error(f"File not found: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path)
    # Harmonize state names after initial loading and normalization
    df = harmonize_state_names(df)
    return df

@st.cache_data(ttl=3600)
def load_population_df() -> pd.DataFrame:
    """Loads and cleans the Population data."""
    path = DATA_DIR / "population_clean.csv"
    if not path.exists():
        st.error(f"File not found: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path)
    # Harmonize state names after initial loading and normalization
    df = harmonize_state_names(df)
    return df
