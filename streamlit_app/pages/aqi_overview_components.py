import streamlit as st
import pandas as pd
from collections import Counter

# Define Southern Indian states for filtering. Lowercase them for robust matching.
SOUTHERN_INDIAN_STATES = [
    "andhra pradesh", "karnataka", "kerala", "tamil nadu", "telangana"
]

@st.cache_data
def get_pollution_composition(df: pd.DataFrame, region_type: str) -> pd.DataFrame:
    """
    Computes the top 2 and bottom 2 prominent pollutants for states 
    based on the selected region type (Southern India or Rest of India - Top Polluted).

    Args:
        df (pd.DataFrame): The DataFrame filtered by date range.
        region_type (str): The selected region type ('Southern India' or 'Rest of India').
    """
    processed_df = df.copy() # Work on a copy to avoid modifying original filtered_df

    # Ensure the 'state' column is in lowercase for consistent filtering
    # This also helps with the SOUTHERN_INDIAN_STATES list which is all lowercase.
    processed_df['state'] = processed_df['state'].str.lower()
    
    if region_type == 'Southern India':
        # Filter for Southern Indian states
        processed_df = processed_df[processed_df['state'].isin(SOUTHERN_INDIAN_STATES)]
        states_to_display = [s.title() for s in SOUTHERN_INDIAN_STATES]
    elif region_type == 'Rest of India':
        # Identify non-Southern states
        non_southern_states_df = processed_df[~processed_df['state'].isin(SOUTHERN_INDIAN_STATES)]
        
        if not non_southern_states_df.empty:
            # Calculate average AQI for non-Southern states within the current date range
            state_avg_aqi = non_southern_states_df.groupby('state')['aqi_value'].mean().reset_index()
            # Select top 5 most polluted states (highest average AQI)
            top_polluted_non_southern_states = state_avg_aqi.nlargest(10, 'aqi_value')['state'].tolist()
            
            # Filter the processed_df to include only these top polluted non-southern states
            processed_df = processed_df[processed_df['state'].isin(top_polluted_non_southern_states)]
            states_to_display = [s.title() for s in top_polluted_non_southern_states]
        else:
            # If no non-southern data, return empty DataFrame
            return pd.DataFrame(columns=["State", "Highest", "Lowest"])
    else:
        # Default or error case, return empty DataFrame
        return pd.DataFrame(columns=["State", "Highest", "Lowest"])

    # Proceed with pollutant composition calculation on the processed_df
    recent = processed_df.loc[processed_df["date"].dt.year >= 2022, ["state", "prominent_pollutants"]]
    
    # Check if 'recent' is empty. If so, return an empty dataframe with correct columns.
    if recent.empty:
        return pd.DataFrame(columns=["State", "Highest", "Lowest"])

    grouped = recent.groupby("state")["prominent_pollutants"].apply(list)
    
    rows = []
    for state, lst in grouped.items():
        cnt = Counter(lst)
        # Handle cases where there might not be 2 unique pollutants
        top_pollutant = [p for p, _ in cnt.most_common(2)]
        bot_pollutant = [p for p, _ in sorted(cnt.items(), key=lambda x: x[1])[:2]]
        rows.append({
            "State": state.title(),
            "Highest": ", ".join(top_pollutant) or "-",
            "Lowest": ", ".join(bot_pollutant) or "-"
        })

    # This check is also a good practice
    if not rows:
        return pd.DataFrame(columns=["State", "Highest", "Lowest"])

    df_comp = (
        pd.DataFrame(rows)
        .set_index("State")
        .reindex(states_to_display) # Reindex dynamically based on selected states
        .reset_index()
    )
    return df_comp

def display_pollution_composition_table(filtered_df: pd.DataFrame):
    """
    Displays the pollution composition table, allowing selection of region.
    
    Args:
        filtered_df (pd.DataFrame): The DataFrame filtered by date range.
    """
    
    # Add a selectbox for region selection
    region_selection = st.selectbox(
        "",
        ('Southern India', 'Rest of India'),
        key='pollution_composition_region_select' # Unique key for this widget
    )

    comp_df = get_pollution_composition(filtered_df, region_selection)
    
    if not comp_df.empty:
        # Calculate dynamic height for st.dataframe
        row_height_px = 35 
        header_height_px = 38 
        dynamic_height = header_height_px + (len(comp_df) * row_height_px)

        st.dataframe(comp_df, hide_index=True, width=700, height=246) # Increased width for better display
    else:
        st.info(f"No data available for {region_selection} in the selected date range or top states could not be identified.")
