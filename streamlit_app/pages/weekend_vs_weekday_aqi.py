import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# Assuming data_loader is in the same package structure or accessible
from streamlit_app.data_loader import load_aqi_table

# Define the metro cities for analysis
METRO_CITIES = [
    "Delhi", "Mumbai", "Chennai", "Kolkata", "Bengaluru", "Hyderabad", "Ahmedabad", "Pune", "Surat","Patna","Jaipur","Lucknow"
]

# Define AQI bands and their categories/colors (used by get_aqi_category)
AQI_BANDS = {
    "Good": {"range": [0, 50], "color": "#009966"},
    "Satisfactory": {"range": [51, 100], "color": "#ffde33"},
    "Moderate": {"range": [101, 200], "color": "#ff9933"},
    "Poor": {"range": [201, 300], "color": "#cc0033"},
    "Very Poor": {"range": [301, 400], "color": "#991900"},
    "Severe": {"range": [401, 500], "color": "#7e0023"},
}

# Helper function to get AQI category from value
def get_aqi_category(aqi_value):
    if pd.isna(aqi_value):
        return "N/A"
    for category, band in AQI_BANDS.items():
        if band["range"][0] <= aqi_value <= band["range"][1]:
            return category
    return "Beyond Scale" # For values > 500

# Cached function to load and prepare data for this specific analysis
@st.cache_data
def load_and_prepare_metro_aqi_data(start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    df = load_aqi_table()
    df["date"] = pd.to_datetime(df["date"])
    df["aqi_value"] = pd.to_numeric(df["aqi_value"], errors="coerce")
    
    # Apply the date filter first
    mask = (df["date"].dt.date >= start_date.date()) & (df["date"].dt.date <= end_date.date())
    df_filtered_by_date = df.loc[mask].copy()

    # Filter for the specified metro cities (case-insensitive matching)
    df_filtered_by_date['area_title'] = df_filtered_by_date['area'].str.title()
    df_metro = df_filtered_by_date[df_filtered_by_date['area_title'].isin(METRO_CITIES)].copy()

    # Add a 'Day_Type' column: 'Weekend' or 'Weekday'
    df_metro['Day_Type'] = df_metro['date'].dt.dayofweek.apply(
        lambda x: 'Weekend' if x >= 5 else 'Weekday' # Saturday (5) and Sunday (6) are weekends
    )
    
    return df_metro

# Function to highlight rows based on Weekend vs Weekday AQI comparison
def highlight_aqi_comparison(row):
    # Ensure both 'Weekday' and 'Weekend' values are present and not NaN
    if pd.notna(row['Weekday']) and pd.notna(row['Weekend']):
        if row['Weekend'] > row['Weekday']:
            # Apply light orange/peach background if Weekend AQI is higher
            return ['background-color: #ffbc85'] * len(row) # Light orange/peach
        elif row['Weekday'] > row['Weekend']:
            # Apply light green background if Weekday AQI is higher
            return ['background-color: #e0f7e0'] * len(row) # Light green
    return [''] * len(row) # No styling for other rows or if values are missing

def get_weekend_weekday_analysis_components(start_date: pd.Timestamp, end_date: pd.Timestamp):
    """
    Calculates the AQI comparison data for weekdays vs. weekends in metro cities.

    Args:
        start_date (pd.Timestamp): The start date for filtering data.
        end_date (pd.Timestamp): The end date for filtering data.
    
    Returns:
        tuple: A tuple containing (plotly_figure, raw_aqi_dataframe, styled_aqi_dataframe, warning_message_string).
               Returns (None, pd.DataFrame(), pd.DataFrame().style, warning_message_string) if no data.
    """
    metro_aqi_df = load_and_prepare_metro_aqi_data(start_date, end_date)

    if metro_aqi_df.empty:
        all_data_cities = load_aqi_table()['area'].str.title().unique()
        missing_cities = [city for city in METRO_CITIES if city not in all_data_cities]
        
        warning_msg = "No data available for the specified metro cities in the selected date range to perform this analysis."
        if missing_cities:
            warning_msg += f"\n\n**Note:** The following cities from your list were not found in the loaded data: {', '.join(missing_cities)}"

        return None, pd.DataFrame(), pd.DataFrame().style, warning_msg # Return empty DataFrame and empty Styler

    # Calculate average AQI for weekdays and weekends per city
    aqi_comparison = metro_aqi_df.groupby(['area_title', 'Day_Type'])['aqi_value'].mean().unstack().reset_index()
    aqi_comparison.rename(columns={'area_title': 'City'}, inplace=True)

    # Handle cases where a city might only have data for one day type
    if 'Weekday' not in aqi_comparison.columns:
        aqi_comparison['Weekday'] = None
    if 'Weekend' not in aqi_comparison.columns:
        aqi_comparison['Weekend'] = None
    # Round 'Weekday' and 'Weekend' columns to 2 decimal places
    if 'Weekday' in aqi_comparison.columns:
        aqi_comparison['Weekday'] = aqi_comparison['Weekday'].round(2)
    if 'Weekend' in aqi_comparison.columns:
        aqi_comparison['Weekend'] = aqi_comparison['Weekend'].round(2)
    # Apply row-level highlighting
    styled_aqi_comparison = aqi_comparison.style.apply(highlight_aqi_comparison, axis=1)
    styled_aqi_comparison = styled_aqi_comparison.format({
        'Weekday': "{:.2f}",
        'Weekend': "{:.2f}"
    })
    
    fig = None # Explicitly set fig to None as the chart is removed from this function's output

    observation_notes = "" # Set to empty string
    
    # Return fig, the raw DataFrame, the styled DataFrame, and notes
    return fig, aqi_comparison, styled_aqi_comparison, observation_notes

# New function to get AQI category breakdown for a selected city
def get_city_aqi_category_breakdown_data(metro_aqi_df: pd.DataFrame, selected_city: str) -> pd.DataFrame:
    """
    Calculates the number of days for each AQI category for a specific city.
    Aggregates to daily average AQI before categorization to count unique days.

    Args:
        metro_aqi_df (pd.DataFrame): The DataFrame containing metro AQI data, already filtered by date.
        selected_city (str): The city for which to get the breakdown.

    Returns:
        pd.DataFrame: A DataFrame with AQI categories and their day counts.
    """
    if metro_aqi_df.empty:
        return pd.DataFrame(columns=["AQI Category", "Number of Days"])

    city_data = metro_aqi_df[metro_aqi_df['area_title'] == selected_city].copy()

    if city_data.empty:
        return pd.DataFrame(columns=["AQI Category", "Number of Days"])

    # IMPORTANT CHANGE: Aggregate to daily average AQI first
    # This ensures we count unique days, not multiple readings per day
    daily_avg_aqi = city_data.groupby(city_data['date'].dt.date)['aqi_value'].mean().reset_index()
    daily_avg_aqi.columns = ['date', 'aqi_value'] # Rename columns for clarity

    # Apply AQI categorization to the daily average values
    daily_avg_aqi['AQI_Category'] = daily_avg_aqi['aqi_value'].apply(get_aqi_category)

    # Count days for each category
    category_counts = daily_avg_aqi['AQI_Category'].value_counts().reset_index()
    category_counts.columns = ["AQI Category", "Number of Days"]

    # Filter out "Beyond Scale" and "N/A" before ensuring all categories are present and ordering
    filtered_categories = [cat for cat in category_counts['AQI Category'] if cat not in ["Beyond Scale", "N/A"]]
    category_counts = category_counts[category_counts['AQI Category'].isin(filtered_categories)].copy()

    # Ensure all *desired* categories are present, even if count is 0, and order them
    ordered_categories = list(AQI_BANDS.keys()) # Only include the defined AQI bands
    category_counts['AQI Category'] = pd.Categorical(
        category_counts['AQI Category'],
        categories=ordered_categories,
        ordered=True
    )
    category_counts = category_counts.sort_values("AQI Category").reset_index(drop=True)

    # Fill in missing categories with 0 days
    full_category_df = pd.DataFrame(ordered_categories, columns=["AQI Category"])
    category_counts = pd.merge(full_category_df, category_counts, on="AQI Category", how="left").fillna(0)
    category_counts["Number of Days"] = category_counts["Number of Days"].astype(int)

    return category_counts


# This ensures the app() function runs when the script is executed by Streamlit
# if __name__ == "__main__": block is for standalone execution of this file.
# When imported by app.py, this block is skipped.
if __name__ == "__main__":
    st.set_page_config(layout="wide") # Needed for standalone run
    full_aqi_df = load_aqi_table()
    full_aqi_df["date"] = pd.to_datetime(full_aqi_df["date"])
    min_d, max_d = full_aqi_df["date"].dt.date.min(), full_aqi_df["date"].dt.date.max()
    
    st.sidebar.header("Standalone Date Filter") 
    start_d_standalone = st.sidebar.date_input("Start date (Standalone)", value=min_d, min_value=min_d, max_value=max_d, key="standalone_start_date")
    end_d_standalone = st.sidebar.date_input("End date (Standalone)", value=max_d, min_value=min_d, max_value=max_d, key="standalone_end_date")
    
    if start_d_standalone > end_d_standalone:
        st.sidebar.error("Start date must be on or before end date")
        st.stop()
    
    # Call the function and display components for standalone execution
    chart_fig, raw_aqi_table_data, styled_aqi_table_data, notes = get_weekend_weekday_analysis_components(pd.to_datetime(start_d_standalone), pd.to_datetime(end_d_standalone))
    
    if not raw_aqi_table_data.empty: # Check raw DataFrame for emptiness
        st.title("AQI Comparison: Weekdays vs. Weekends in Metro Cities") # Title for standalone page
        st.markdown("""
            <p style="font-size:18px; color:#555;">
            This page analyzes whether Air Quality Index (AQI) differs on weekdays compared to weekends
            in major Indian metro cities.
            </p>
        """, unsafe_allow_html=True)
        st.markdown("---")
        # Removed: st.markdown(notes)
        st.subheader("Detailed AQI Comparison Table")
        # Set width for the Detailed AQI Comparison Table
        st.dataframe(styled_aqi_table_data, use_container_width=False,height=200) 
    else:
        st.warning(notes) # Display the warning message if no data

    st.markdown("---")
    st.subheader("AQI Category Breakdown for Selected City")
    
    # Get the full metro AQI data for city selection
    metro_aqi_df_for_breakdown = load_and_prepare_metro_aqi_data(pd.to_datetime(start_d_standalone), pd.to_datetime(end_d_standalone))
    
    if not metro_aqi_df_for_breakdown.empty:
        available_cities = sorted(metro_aqi_df_for_breakdown['area_title'].unique().tolist())
        if available_cities:
            selected_city_standalone = st.selectbox(
                "Select a city for AQI category breakdown (Standalone):",
                available_cities,
                key="standalone_city_select"
            )
            aqi_breakdown_df = get_city_aqi_category_breakdown_data(metro_aqi_df_for_breakdown, selected_city_standalone)
            if not aqi_breakdown_df.empty:
                # Set width for the AQI Category Breakdown table
                st.dataframe(aqi_breakdown_df, hide_index=True)
            else:
                st.info(f"No AQI category data for {selected_city_standalone} in the selected date range.")
        else:
            st.info("No cities available for breakdown in the selected date range.")
    else:
        st.info("No metro city data available to perform AQI category breakdown.")
