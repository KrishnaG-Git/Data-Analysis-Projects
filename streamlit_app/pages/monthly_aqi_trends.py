# monthly_aqi_trends.py

import pandas as pd
import plotly.express as px
from typing import Tuple
from plotly.graph_objs._figure import Figure

def display_monthly_aqi_chart_and_get_summary(
    aqi_df: pd.DataFrame
) -> Tuple[Figure, pd.DataFrame]:
    """
    Builds a 300×200 Plotly line‐chart of monthly AQI for the top-10 states
    (by distinct monitoring areas), and returns the figure plus a
    DataFrame of each state’s worst month.
    """

    # 1) Top 10 states by distinct areas
    state_counts = (
        aqi_df
        .groupby("state")["area"]
        .nunique()
        .reset_index(name="distinct_areas")
    )
    top_ten = state_counts.nlargest(15, "distinct_areas")["state"].tolist()

    # 2) Filter & compute monthly averages
    df_top = aqi_df[aqi_df["state"].isin(top_ten)].copy()
    df_top["Month"]     = df_top["date"].dt.strftime("%b")
    df_top["Month_Num"] = df_top["date"].dt.month

    monthly = (
        df_top
        .groupby(["state", "Month", "Month_Num"], as_index=False)["aqi_value"]
        .mean()
        .rename(columns={"aqi_value": "Average AQI"})
    )
    monthly["state"] = monthly["state"].str.title()
    monthly.sort_values(["state", "Month_Num"], inplace=True)

    # 3) Build figure (no st.* calls here)
    fig = px.line(
        monthly,
        x="Month",
        y="Average AQI",
        color="state",
        labels={
            "Month": "Month",
            "Average AQI": "Average AQI Value",
            "state": "State"
        },
        hover_data={"Month_Num": False}
    )
    fig.update_layout(
        title_text="",
        xaxis_title="",
        yaxis_title="",
        width=400,
        height=470,
        margin=dict(t=10, b=0, l=0, r=0)
    )

    # 4) Compute worst‐month summary
    rows = []
    for st in top_ten:
        st_title = st.title()
        df_st = monthly[monthly["state"] == st_title]
        if df_st.empty:
            continue
        worst = df_st.loc[df_st["Average AQI"].idxmax()]
        rows.append({
            "State":       st_title,
            "Worst Month": worst["Month"],
            "Highest AQI": f"{worst['Average AQI']:.2f}"
        })

    summary_df = pd.DataFrame(rows)
    return fig, summary_df
