import pandas as pd
from collections import Counter
import streamlit as st

# build a case-insensitive regex for respiratory conditions
RESP_PATTERN = r"(?i)\b(respiratory|influenza|flu|ari|urti|pneumonia|h1n1)\b"

@st.cache_data(ttl=3600)
def get_health_burden_df(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    respiratory_only: bool = False
) -> pd.DataFrame:
    """
    Returns per-state:
      - Top 2 reported illnesses (respiratory_only toggles filtering)
      - Average AQI in [start_date, end_date] (clamped to April 1, 2022)
    """
    # Import here to avoid circular imports
    from streamlit_app.data_loader import load_aqi_table, load_idsp_table, harmonize_state_names

    aqi_start = pd.Timestamp("2022-04-01")
    start_date = max(start_date, aqi_start)

    aqi_df = load_aqi_table()
    idsp_df = load_idsp_table()
    
    # Harmonize state names
    aqi_df = harmonize_state_names(aqi_df)
    idsp_df = harmonize_state_names(idsp_df)

    aqi_win = aqi_df[
        (aqi_df["date"] >= start_date) &
        (aqi_df["date"] <= end_date)
    ].copy()

    idsp_win = idsp_df[
        (idsp_df["outbreak_starting_date"] >= start_date) &
        (idsp_df["outbreak_starting_date"] <= end_date)
    ].copy()

    if respiratory_only:
        idsp_win = idsp_win[
            idsp_win["disease"].str.contains(RESP_PATTERN, na=False)
        ]

    avg_aqi = (
        aqi_win
            .groupby("state")["aqi_value"]
            .mean()
            .round(2)
            .reset_index(name="Avg AQI")
    )

    disease_lists = (
        idsp_win
            .groupby("state")["disease"]
            .apply(list)
            .reset_index(name="all_diseases")
    )

    def top_two(ds: list[str]) -> str:
        cnt = Counter(ds)
        return ", ".join([d for d, _ in cnt.most_common(2)]) or "-"

    disease_lists["Disease"] = disease_lists["all_diseases"].apply(top_two)

    result = (
        disease_lists[["state", "Disease"]]
            .merge(avg_aqi, on="state", how="left")
            .rename(columns={"state": "State"})
            .sort_values("Avg AQI", ascending=False)
            .reset_index(drop=True)
    )

    result['Avg AQI'] = result['Avg AQI'].fillna(0.0)

    return result

@st.cache_data(ttl=3600)
def get_most_affected_age_groups(burden_type: str, selected_state: str) -> pd.DataFrame:
    """
    Analyzes GBD data to find the most affected age group by state for each
    air pollution-related cause.
    """
    # Import here to avoid circular imports
    from streamlit_app.data_loader import load_gbdhealth_df, normalize_state_name

    gbd_health_df = load_gbdhealth_df()
    
    if gbd_health_df.empty:
        return pd.DataFrame()
    
    gbd_health_df['val'] = gbd_health_df['val'].fillna(0)

    # Merge COPD into chronic respiratory diseases
    gbd_health_df['cause_name_clean'] = gbd_health_df['cause_name_clean'].replace({
        'chronic_obstructive_pulmonary_disease': 'chronic_respiratory_diseases'
    })

    air_pollution_causes = [
        'respiratory_infections_and_tuberculosis', 'non_communicable_diseases',
        'chronic_respiratory_diseases', 
        'lower_respiratory_infections',
        'asthma', 'cancers'
    ]
    
    filtered_df = gbd_health_df[
        (gbd_health_df['cause_name_clean'].isin(air_pollution_causes)) & 
        (gbd_health_df['year'] == 2021) &
        (gbd_health_df['measure_name'] == burden_type)
    ]

    if selected_state == "All States":
        grouped_df = filtered_df.groupby(['cause_name_clean', 'age_range'])['val'].sum().reset_index()
        most_affected_df = (
            grouped_df.sort_values('val', ascending=False)
            .groupby(['cause_name_clean'], as_index=False)
            .first()
        )
        most_affected_df['state'] = "All States"
    else:
        harmonized_selected_state = normalize_state_name(selected_state)
        filtered_df = filtered_df[filtered_df['state'] == harmonized_selected_state].copy()
        
        if filtered_df.empty:
            return pd.DataFrame(columns=['State', 'Disease Cause', 'Most Affected Age Group', f'Total Health Burden ({burden_type.title()}) (2021)'])
            
        grouped_df = filtered_df.groupby(['state', 'cause_name_clean', 'age_range'])['val'].sum().reset_index()
        most_affected_df = (
            grouped_df.sort_values('val', ascending=False)
            .groupby(['state', 'cause_name_clean'], as_index=False)
            .first()
        )
        
    most_affected_df = most_affected_df.rename(columns={
        'state': 'State',
        'cause_name_clean': 'Disease Cause',
        'age_range': 'Most Affected Age Group',
        'val': f'Total Health Burden ({burden_type.title()}) (2021)'
    })

    return most_affected_df.sort_values(by=['State', 'Disease Cause']).reset_index(drop=True)
