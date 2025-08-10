import datetime
import streamlit as st
import pandas as pd
import altair as alt

# Load helpers
from streamlit_app.data_loader import (
    load_idsp_table,
    load_gbdhealth_df,
    normalize_state_name
)
from streamlit_app.pages.health_burden_components import (
    get_health_burden_df,
    get_most_affected_age_groups
)

@st.cache_data
def load_and_prepare_data() -> pd.DataFrame:
    df = load_idsp_table()
    df["date"] = pd.to_datetime(df["outbreak_starting_date"])
    return df

def sanitize_df_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """Convert any Categorical columns to str and reset the index."""
    sanitized = df.copy()
    for col in sanitized.columns:
        if pd.api.types.is_categorical_dtype(sanitized[col]):
            sanitized[col] = sanitized[col].astype(str)
    return sanitized.reset_index(drop=True)

def capitalize_each(name: str) -> str:
    parts = [p.strip() for p in name.split(",")]
    return ", ".join(p.capitalize() for p in parts if p)

def app():
    # Load and filter outbreak data
    df = load_and_prepare_data()
    aqi_floor = datetime.date(2022, 4, 1)
    data_min = df["date"].dt.date.min()
    min_d = max(aqi_floor, data_min)
    max_d = df["date"].dt.date.max()

    st.sidebar.header("Historical Analysis Filters")
    start_d = st.sidebar.date_input("Start date", value=min_d, min_value=min_d, max_value=max_d)
    end_d = st.sidebar.date_input("End date", value=max_d, min_value=min_d, max_value=max_d)
    resp_only = st.sidebar.checkbox("Respiratory diseases only", value=False)

    if start_d > end_d:
        st.sidebar.error("Start must be on or before End")
        st.stop()

    mask = (df["date"].dt.date >= start_d) & (df["date"].dt.date <= end_d)
    filtered = df.loc[mask]
    if filtered.empty:
        st.warning(f"No outbreak records between {start_d} and {end_d}")
        st.stop()

    # View selector
    view = st.radio(
        "",
        ["Outbreak Analysis", "Age Group Health Burden"],
        horizontal=True
    )

    # -----------------------------------------------
    # Historical Outbreak Analysis
    # -----------------------------------------------
    if view == "Outbreak Analysis":
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
        

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Outbreaks", filtered.shape[0])
        c2.metric("Unique Diseases", filtered["disease"].nunique())
        c3.metric("States Affected", filtered["state"].nunique())

        st.markdown("---")

        state_counts = (
            filtered
            .groupby("state")["disease"].count()
            .reset_index(name="Total Outbreaks")
            .assign(State=lambda d: d["state"].str.title())
            .loc[:, ["State", "Total Outbreaks"]]
            .sort_values("Total Outbreaks", ascending=False)
        )

        hb_df = get_health_burden_df(
            pd.to_datetime(start_d),
            pd.to_datetime(end_d),
            respiratory_only=resp_only
        )
        hb_df["Disease"] = (
            hb_df["Disease"]
            .fillna("")
            .str.split(",")
            .apply(lambda lst: ", ".join(x.strip().capitalize() for x in lst if x))
        )

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Outbreaks by State")
            st.dataframe(
                sanitize_df_for_display(state_counts),
                use_container_width=True,
                hide_index=True
            )
        with col2:
            st.subheader("Top Illnesses & Avg AQI")
            if not hb_df.empty:
                st.dataframe(
                    sanitize_df_for_display(hb_df),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning("No data for these filters.")

    # -----------------------------------------------
    # Age Group Health Burden
    # -----------------------------------------------
    else:
        st.markdown("**Air Pollution Health Burden by Age Group (2021)**")
        

        gbd_df = load_gbdhealth_df()
        gbd_df["state"] = gbd_df["state"].apply(normalize_state_name)

        all_states = sorted(set(gbd_df["state"]))
        if "Union Territories Other Than Delhi" in all_states:
            all_states.remove("Union Territories Other Than Delhi")
        all_states.insert(0, "All States")

        selected_state = st.selectbox("", options=all_states)
        keys   = ("deaths", "dalys")
        labels = [k.capitalize() for k in keys]

        selection = st.radio("", labels, horizontal=True)
        # map back to your original key
        burden_type = keys[ labels.index(selection) ]

        # Bar chart data
        if selected_state == "All States":
            df_plot = (
                gbd_df[gbd_df["measure_name"] == burden_type]
                .groupby("age_range")["val"]
                .sum()
                .reset_index()
            )
            title = "All States"
        else:
            norm = normalize_state_name(selected_state)
            df_plot = (
                gbd_df[
                    (gbd_df["state"] == norm) &
                    (gbd_df["measure_name"] == burden_type)
                ]
                .groupby("age_range")["val"]
                .sum()
                .reset_index()
            )
            title = capitalize_each(selected_state)

        df_plot = df_plot.rename(columns={"val": f"Total {burden_type.title()}"})
        chart = (
            alt.Chart(df_plot)
            .mark_bar()
            .encode(
                x=alt.X("age_range:N", title="Age Group"),
                y=alt.Y(f"Total {burden_type.title()}:Q"),
                tooltip=["age_range", f"Total {burden_type.title()}"]
            )
            .properties(
                title=f"{burden_type.title()} by Age Group – {title}",
                width=500, height=265
            )
        )

         # Render chart & table in two columns
        col_chart, col_table = st.columns(2)

        with col_chart:
            st.altair_chart(chart, use_container_width=False)
            
        with col_table:
            col_table.markdown("**Most Affected Age Groups by Cause**")

            maf = get_most_affected_age_groups(burden_type, selected_state)

            if not maf.empty:
                display_df = (
                    maf
                    .rename(columns={
                        'cause_name_clean': 'Disease Cause',
                        'age_range': 'Most Affected Age Group',
                        'val': f'Total Health Burden ({burden_type.title()}) (2021)',
                        'state': 'State'
                    })
                    .drop(columns=['State'], errors='ignore')
                )

                # 1) Clean up disease names: remove underscores & Title Case
                display_df['Disease Cause'] = (
                    display_df['Disease Cause']
                    .str.replace('_', ' ')
                    .str.title()
                )

                # 2) Style: set all font color to black
                styled = (
                    display_df
                    .set_index('Disease Cause')
                    .style
                    .set_properties(**{'color': 'black'})
                )

                # render the styled table
                st.table(styled)
            else:
                st.warning(f"No data available for {selected_state}.")
        

if __name__ == "__main__":
            app()
