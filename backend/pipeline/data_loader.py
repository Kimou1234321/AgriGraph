"""Phase A1 real ICBF data loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

CONSTANTS: dict[str, Any] = {
    "PHASE": "A1",
    "EXPECTED_ROWS": 130,
    "EXPECTED_COLS": 19,
    "EXPECTED_YEARS": [2021, 2022, 2023, 2024, 2025],
    "PERCENTAGE_COLUMN_KEYWORDS": ("pct", "rate", "mortality"),
    "DATA_DIR": Path(__file__).resolve().parents[1] / "data",
    "RAW_DATA_FILENAME": "icbf_real.csv",
    "CLEAN_DATA_FILENAME": "icbf_clean.csv",
    "RENAME_MAP": {"females_not_calved_in_period": "females_not_calved_pct"},
    "FEATURE_COLS": [
        "num_herds",
        "calving_interval",
        "six_wk_calving_rate",
        "calves_per_cow_per_year",
        "females_not_calved_pct",
        "avg_lactations",
        "current_replacement_rate",
        "potential_replacement_rate",
        "cows_culled_pct",
        "heifers_calved_22_26mo",
        "mortality_dead_at_birth",
        "mortality_dead_28days",
        "replacements_dairy_ai_pct",
        "births_known_sire_pct",
        "births_calving_survey_pct",
        "recycled_cows_pct",
        "autumn_6wk_calving_rate",
    ],
}


def _print_phase_header() -> None:
    """Print a readable phase header."""
    print("\n" + "=" * 72)
    print(f"[{CONSTANTS['PHASE']}] REAL ICBF DATA LOADING")
    print("=" * 72)


def _load_raw_data() -> pd.DataFrame:
    """Load the raw ICBF CSV from disk."""
    raw_path = CONSTANTS["DATA_DIR"] / CONSTANTS["RAW_DATA_FILENAME"]
    print(f"[A1] Loading raw data from: {raw_path}")
    if not raw_path.exists():
        raise FileNotFoundError(f"[A1] Missing required file: {raw_path}")
    return pd.read_csv(raw_path)


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Apply mandatory internal column renaming rules."""
    standardized_df = df.rename(columns=CONSTANTS["RENAME_MAP"]).copy()
    renamed_columns = [k for k in CONSTANTS["RENAME_MAP"] if k in df.columns]
    if renamed_columns:
        print(f"[A1] Applied column renames: {renamed_columns}")
    return standardized_df


def _assert_required_schema(df: pd.DataFrame) -> None:
    """Assert shape and required columns for the input dataset."""
    print(f"[A1] Observed shape: {df.shape}")
    expected_shape = (CONSTANTS["EXPECTED_ROWS"], CONSTANTS["EXPECTED_COLS"])
    if df.shape != expected_shape:
        raise ValueError(f"[A1] Invalid shape {df.shape}; expected {expected_shape}.")

    required_columns = ["county", "year", *CONSTANTS["FEATURE_COLS"]]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"[A1] Missing required columns: {missing_columns}")
    print("[A1] Required columns validated.")


def _assert_counties_and_years(df: pd.DataFrame) -> None:
    """Validate county count and year range constraints."""
    counties = sorted(df["county"].dropna().astype(str).unique().tolist())
    years = sorted(df["year"].dropna().astype(int).unique().tolist())
    print(f"[A1] Counties found ({len(counties)}): {counties}")
    print(f"[A1] Years found ({len(years)}): {years}")

    if len(counties) != 26:
        raise ValueError(f"[A1] Expected 26 unique counties, found {len(counties)}.")
    if years != CONSTANTS["EXPECTED_YEARS"]:
        raise ValueError(f"[A1] Expected years {CONSTANTS['EXPECTED_YEARS']}, found {years}.")


def _fill_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill then backward-fill missing values per county series."""
    missing_locations = np.argwhere(df.isna().to_numpy())
    if len(missing_locations) == 0:
        print("[A1] No missing values detected.")
        return df

    print(f"[A1] Missing values detected: {len(missing_locations)}")
    for row_idx, col_idx in missing_locations:
        col_name = df.columns[col_idx]
        county_value = df.iloc[row_idx]["county"] if "county" in df.columns else "UNKNOWN"
        print(f"[A1][WARN] Missing value at row={row_idx}, county={county_value}, column={col_name}.")

    filled_df = (
        df.sort_values(["county", "year"])
        .groupby("county", group_keys=False)
        .apply(lambda group: group.ffill().bfill())
        .reset_index(drop=True)
    )
    print("[A1] Applied forward-fill and backward-fill per county.")
    return filled_df


def _warn_impossible_values(df: pd.DataFrame) -> None:
    """Print warnings for negative values and invalid percentages."""
    for col in CONSTANTS["FEATURE_COLS"]:
        series = pd.to_numeric(df[col], errors="coerce")
        negative_indices = series[series < 0].index.tolist()
        for idx in negative_indices:
            print(f"[A1][WARN] Negative value in {col} at row={idx}: {series.loc[idx]}")

        is_percentage_col = any(key in col for key in CONSTANTS["PERCENTAGE_COLUMN_KEYWORDS"])
        if is_percentage_col:
            high_indices = series[series > 100].index.tolist()
            for idx in high_indices:
                print(f"[A1][WARN] Percentage >100 in {col} at row={idx}: {series.loc[idx]}")


def _save_clean_data(df: pd.DataFrame) -> Path:
    """Save the cleaned dataset to CSV for auditability."""
    output_path = CONSTANTS["DATA_DIR"] / CONSTANTS["CLEAN_DATA_FILENAME"]
    df.to_csv(output_path, index=False)
    print(f"[A1] Saved cleaned data to: {output_path}")
    return output_path


def _print_feature_summary(df: pd.DataFrame) -> None:
    """Print per-feature mean and std over all rows."""
    summary = df[CONSTANTS["FEATURE_COLS"]].agg(["mean", "std"]).transpose()
    print("[A1] Feature mean/std summary:")
    print(summary.to_string(float_format=lambda value: f"{value:.4f}"))


def run_data_loader() -> pd.DataFrame:
    """Run Phase A1 loading, validation, cleaning, and export."""
    _print_phase_header()
    dataframe = _load_raw_data()
    dataframe = _standardize_columns(dataframe)
    _assert_required_schema(dataframe)
    _assert_counties_and_years(dataframe)
    dataframe = _fill_missing_values(dataframe)
    _warn_impossible_values(dataframe)
    dataframe = dataframe.sort_values(["county", "year"]).reset_index(drop=True)
    _save_clean_data(dataframe)
    _print_feature_summary(dataframe)
    print(f"[A1] Completed successfully. Final shape: {dataframe.shape}")
    return dataframe

