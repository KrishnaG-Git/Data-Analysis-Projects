#!/usr/bin/env python3
"""
health_cost_proj.py

Defines:
  - compute_health_cost_impacts(): runs the full pipeline and returns a DataFrame
  - make_health_cost_chart(): builds an Altair chart from that DataFrame
"""

import pandas as pd
import altair as alt
from pathlib import Path

# 1) Locate your clean_data folder
CANDIDATES = [
    Path("data") / "clean_data",
    Path(__file__).parent / "data" / "clean_data",
    Path(__file__).parent.parent / "data" / "clean_data",
]
for p in CANDIDATES:
    if p.exists():
        DATA_DIR = p
        break
else:
    raise FileNotFoundError("Could not locate data/clean_data")

# 2) Core pipeline extracted into one function
def compute_health_cost_impacts(
    target_year: int = 2024,
    cf_aqi: float = 35.0,
    data_dir: Path = DATA_DIR
) -> pd.DataFrame:
    hp_df = pd.read_csv(data_dir / "health_params_clean.csv")
    pop_df = pd.read_csv(data_dir / "population_clean.csv")
    aqi_df = pd.read_csv(data_dir / "aqi_clean.csv")

    # standardize state names & dates
    pop_df["state"] = pop_df["state"].str.lower().str.strip()
    aqi_df["state"] = aqi_df["state"].str.lower().str.strip()
    aqi_df["date"]  = pd.to_datetime(aqi_df["date"], dayfirst=True)
    aqi_df["year"]  = aqi_df["date"].dt.year

    # filter population to target year
    pop_year = pop_df[pop_df["year"] == target_year].copy()
    if "month" in pop_year:
        pop_year["mnum"] = (
            pop_year["month"]
            .str.lower()
            .map({
                "january":1, "february":2, "march":3, "april":4,
                "may":5,     "june":6,     "july":7,  "august":8,
                "september":9,"october":10,"november":11,"december":12
            })
        )
        pop_year = pop_year[pop_year["mnum"] == pop_year["mnum"].max()]
    pop_year = (
        pop_year
        .rename(columns={"pop_total": "population"})
        [["state", "population"]]
    )

    # annual AQI per state
    aqi_ann = (
        aqi_df
        .groupby(["state", "year"], as_index=False)["aqi_value"]
        .mean()
        .rename(columns={"aqi_value": "avg_aqi"})
    )
    aqi_ann["delta_aqi"] = aqi_ann["avg_aqi"] - cf_aqi

    # build state × outcome grid
    states = aqi_ann.loc[aqi_ann["year"] == target_year, "state"].unique()
    combo = pd.DataFrame({"state": states}).merge(hp_df, how="cross")

    # merge inputs
    combo = (
        combo
        .merge(
            aqi_ann.query("year == @target_year")[["state","avg_aqi","delta_aqi"]],
            on="state", how="left"
        )
        .merge(pop_year, on="state", how="left")
    )

    # PAF & cases
    combo["rr_total"]   = combo["rr_per_10ug"] ** (combo["delta_aqi"] / 10)
    combo["paf"]        = (combo["rr_total"] - 1) / combo["rr_total"]
    combo["attr_rate"]  = combo["paf"] * combo["baseline_incidence"]
    combo["attr_cases"] = combo["attr_rate"] * combo["population"] / 100_000

    # cost impacts (total)
    for kind in ["mean", "min", "max"]:
        combo[f"cost_{kind}_total"] = (
            combo["attr_cases"] * combo[f"cost_{kind}"]
        )

    # cost impacts per person
    for kind in ["mean", "min", "max"]:
        combo[f"cost_{kind}_person"] = combo[f"cost_{kind}"]

    # tidy casing
    combo["state"]   = combo["state"].str.title()
    combo["outcome"] = combo["outcome"].str.replace("_"," ").str.title()
    return combo

# 3) Altair chart builder
def make_health_cost_chart(df: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X(
                "state:N",
                sort=alt.EncodingSortField(
                    field="cost_mean_person", op="sum", order="descending"
                ),
                title="State"
            ),
            y=alt.Y("cost_mean_person:Q", title="Mean Cost per Person (₹)"),
            color=alt.Color("outcome:N", title="Outcome"),
            tooltip=[
                alt.Tooltip("state:N", title="State"),
                alt.Tooltip("outcome:N", title="Outcome"),
                alt.Tooltip("attr_cases:Q", title="Cases", format=","),
                alt.Tooltip("cost_min_person:Q", title="Min Cost per Person", format=",.0f"),
                alt.Tooltip("cost_max_person:Q", title="Max Cost per Person", format=",.0f"),
                alt.Tooltip("cost_mean_person:Q", title="Mean Cost per Person", format=",.0f"),
            ],
        )
        .properties(width="container", height=400)
    )

# 4) CLI fallback
if __name__ == "__main__":
    df = compute_health_cost_impacts()
    df.to_csv("state_health_cost_impacts.csv", index=False)
    chart = make_health_cost_chart(df)
    try:
        chart.show()
    except Exception:
        pass
