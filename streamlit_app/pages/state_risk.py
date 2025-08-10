# streamlit_app/pages/state_risk.py

import pandas as pd
from pathlib import Path
from sklearn.preprocessing import MinMaxScaler
from typing import List, Tuple

# -------------------------------------------------------------------
# 1) Smart DATA_DIR resolution (tries a few likely locations)
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent    # …/streamlit_app/pages
CANDIDATES = [
    BASE_DIR / "data" / "clean_data",          
    BASE_DIR.parent / "data" / "clean_data",   
    BASE_DIR.parent.parent / "data" / "clean_data",
]

for d in CANDIDATES:
    if d.exists():
        DATA_DIR = d
        break
else:
    raise FileNotFoundError(
        "Could not locate clean_data folder. Checked:\n  "
        + "\n  ".join(str(p) for p in CANDIDATES)
    )

# -------------------------------------------------------------------
# 2) Annualize AQI by calendar year (Jan–Dec)
# -------------------------------------------------------------------
def annual_state_aqi_calendar(df_aqi: pd.DataFrame) -> pd.DataFrame:
    df = df_aqi.copy()
    df["date"] = pd.to_datetime(df["date"], dayfirst=True)
    df["year"] = df["date"].dt.year

    return (
        df
        .groupby(["state", "year"], as_index=False)["aqi_value"]
        .mean()
        .rename(columns={"aqi_value": "avg_aqi"})
    )

# -------------------------------------------------------------------
# 3) Project MPCE forward to 2024–25
# -------------------------------------------------------------------
def project_mpce_2425(mpce_df: pd.DataFrame) -> pd.DataFrame:
    df = mpce_df.copy()

    df["proj_rural_2425"] = (
        df["average_mpce_2023_2024_rural"]
        * (1 + df["percentage_increase_mpce_2023_24_from_2022_23_rural"] / 100)
    )
    df["proj_urban_2425"] = (
        df["average_mpce_2023_2024_urban"]
        * (1 + df["percentage_increase_mpce_2023_24_from_2022_23_urban"] / 100)
    )
    df["mpce_2024_25"] = df[["proj_rural_2425", "proj_urban_2425"]].mean(axis=1)
    df["state"] = df["State/UT"].str.lower().str.strip()

    return df[["state", "mpce_2024_25"]]

# -------------------------------------------------------------------
# 4) Extract population for a given calendar year (last available month)
# -------------------------------------------------------------------
def get_population_by_year(pop_df: pd.DataFrame, year: int) -> pd.DataFrame:
    df = pop_df.copy()
    df["state"] = df["state"].str.lower().str.strip()

    df_year = df[df["year"] == year].copy()

    if "month" in df_year.columns:
        month_map = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12
        }
        df_year = df_year.assign(
            month_num = df_year["month"].str.lower().map(month_map)
        )
        max_m = df_year["month_num"].max()
        df_sel = df_year[df_year["month_num"] == max_m]
    else:
        df_sel = df_year

    df_sel = df_sel.assign(population=df_sel["pop_total"])
    return df_sel[["state", "population"]]

# -------------------------------------------------------------------
# 5) Extract high‐AQI areas for each given state
# -------------------------------------------------------------------
def extract_high_aqi_areas(
    aqi_df: pd.DataFrame,
    states: List[str],
    year: int,
    top_n: int = 4
) -> pd.DataFrame:
    """
    For each state in `states`, compute the average AQI of each 'area'
    during calendar `year`, then return the top_n areas with highest avg_aqi.
    """
    df = aqi_df.copy()
    df["date"] = pd.to_datetime(df["date"], dayfirst=True)
    df["year"] = df["date"].dt.year
    df["state"] = df["state"].str.lower().str.strip()
    df["area"] = df["area"].str.lower().str.strip()

    # filter to our target year and the states of interest
    df = df[(df["year"] == year) & (df["state"].isin(states))]

    # average AQI by state & area
    avg_area = (
        df
        .groupby(["state", "area"], as_index=False)["aqi_value"]
        .mean()
        .rename(columns={"aqi_value": "avg_aqi"})
    )

    # pick top_n areas per state
    top_areas = (
        avg_area
        .sort_values(["state", "avg_aqi"], ascending=[True, False])
        .groupby("state")
        .head(top_n)
        .reset_index(drop=True)
    )

    return top_areas

# -------------------------------------------------------------------
# 6) Full Risk‐Score Pipeline + area extraction
# -------------------------------------------------------------------
def compute_state_risk(
    target_year: int = 2025,
    top_states: int = 10,
    top_areas_per_state: int = 4,
    top_global_areas: int = 3
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Returns:
      risk_df — DataFrame of state risk scores (sorted desc).
      areas_df — DataFrame of top areas by avg AQI for the top_states high‐risk states.
    """
    # load cleaned CSVs
    aqi_df  = pd.read_csv(DATA_DIR / "aqi_clean.csv")
    pop_df  = pd.read_csv(DATA_DIR / "population_clean.csv")
    mpce_df = pd.read_csv(DATA_DIR / "mpce_clean.csv")

    # annualize AQI & filter to target year
    aqi_ann    = annual_state_aqi_calendar(aqi_df)
    aqi_target = aqi_ann[aqi_ann["year"] == target_year].copy()

    # project MPCE & extract population
    mpce_proj  = project_mpce_2425(mpce_df)
    pop_target = get_population_by_year(pop_df, target_year)

    # merge all drivers
    df = (
        aqi_target
        .merge(pop_target, on="state", how="inner")
        .merge(mpce_proj,  on="state", how="inner")
    )

    # normalize each metric to [0, 1]
    scaler = MinMaxScaler()
    df[["aqi_n", "pop_n", "mpce_n"]] = scaler.fit_transform(
        df[["avg_aqi", "population", "mpce_2024_25"]]
    )

    # weighted‐sum risk score
    w_aqi, w_pop, w_mpce = 0.7, 0.2, 0.1
    df["risk_score"] = (
        w_aqi  * df["aqi_n"]
      + w_pop  * df["pop_n"]
      + w_mpce * (1 - df["mpce_n"])
    )

    risk_df = df.sort_values("risk_score", ascending=False).reset_index(drop=True)

    # identify top N high‐risk states
    high_states = risk_df.head(top_states)["state"].tolist()

    # extract their top areas by avg AQI
    areas_df = extract_high_aqi_areas(
        aqi_df, high_states, target_year, top_n=top_areas_per_state
    )
    all_states = aqi_df["state"].str.lower().str.strip().unique().tolist()
    global_areas_df = extract_high_aqi_areas(
        aqi_df, all_states, target_year, top_n=top_global_areas
    )
    return risk_df, areas_df,global_areas_df

# -------------------------------------------------------------------
# 7) CLI/demo entrypoint (optional)
# -------------------------------------------------------------------
if __name__ == "__main__":
    risk_df, high_areas_df = compute_state_risk(target_year=2025)

    print("=== State Risk Scores (2025) ===")
    print(risk_df.to_string(index=False))

    print("\n=== Top AQI Areas in High‐Risk States ===")
    print(high_areas_df.to_string(index=False))
