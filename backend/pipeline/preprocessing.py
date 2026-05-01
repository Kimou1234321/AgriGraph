"""Phase A2 preprocessing and artifact persistence."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.preprocessing import MinMaxScaler

CONSTANTS: dict[str, Any] = {
    "PHASE": "A2",
    "DATA_DIR": Path(__file__).resolve().parents[1] / "data",
    "ARTIFACTS_DIR": Path(__file__).resolve().parents[1] / "artifacts",
    "CLEAN_DATA_FILENAME": "icbf_clean.csv",
    "MINMAX_SCALER_FILENAME": "minmax_scaler.pkl",
    "COUNTY_ENCODER_FILENAME": "county_encoder.pkl",
    "NORMALIZED_PANEL_FILENAME": "x_normalized.csv",
    "SORT_COLS": ["county", "year"],
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
    print(f"[{CONSTANTS['PHASE']}] DATA PREPROCESSING")
    print("=" * 72)


def _load_clean_data() -> pd.DataFrame:
    """Load the cleaned A1 dataset from disk."""
    clean_path = CONSTANTS["DATA_DIR"] / CONSTANTS["CLEAN_DATA_FILENAME"]
    print(f"[A2] Loading clean data from: {clean_path}")
    if not clean_path.exists():
        raise FileNotFoundError(f"[A2] Missing required clean data file: {clean_path}")
    return pd.read_csv(clean_path)


def _assert_no_missing(df: pd.DataFrame) -> None:
    """Assert there are no missing values in A2 input."""
    missing_count = int(df.isna().sum().sum())
    if missing_count > 0:
        raise ValueError(f"[A2] Found {missing_count} missing values; Phase A1 cleanup required.")
    print("[A2] Missing value check passed.")


def _sort_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Sort rows by county and year for regular panel structure."""
    sorted_df = df.sort_values(CONSTANTS["SORT_COLS"]).reset_index(drop=True)
    print(f"[A2] Panel sorted by {CONSTANTS['SORT_COLS']}.")
    return sorted_df


def _fit_and_transform_minmax(df: pd.DataFrame) -> tuple[pd.DataFrame, MinMaxScaler]:
    """Fit MinMaxScaler and return normalized features."""
    scaler = MinMaxScaler()
    normalized_values = scaler.fit_transform(df[CONSTANTS["FEATURE_COLS"]])
    normalized_df = pd.DataFrame(normalized_values, columns=CONSTANTS["FEATURE_COLS"])
    print(f"[A2] Built X_normalized with shape {normalized_df.shape}.")
    return normalized_df, scaler


def _build_county_encoder(df: pd.DataFrame) -> dict[str, int]:
    """Create deterministic county to integer mapping."""
    counties = sorted(df["county"].astype(str).unique().tolist())
    encoder = {county: idx for idx, county in enumerate(counties)}
    print(f"[A2] County encoder created with {len(encoder)} counties.")
    return encoder


def _save_pickle(payload: Any, output_path: Path) -> None:
    """Serialize a Python object to a pickle file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as file:
        pickle.dump(payload, file)
    print(f"[A2] Saved artifact: {output_path}")


def _save_normalized_panel(base_df: pd.DataFrame, normalized_df: pd.DataFrame) -> None:
    """Persist normalized panel for audit and inspection."""
    panel_df = pd.concat([base_df[["county", "year"]].reset_index(drop=True), normalized_df], axis=1)
    output_path = CONSTANTS["DATA_DIR"] / CONSTANTS["NORMALIZED_PANEL_FILENAME"]
    panel_df.to_csv(output_path, index=False)
    print(f"[A2] Saved normalized panel to: {output_path}")


def run_preprocessing() -> pd.DataFrame:
    """Run Phase A2 preprocessing and save artifacts."""
    _print_phase_header()
    dataframe = _load_clean_data()
    _assert_no_missing(dataframe)
    dataframe = _sort_panel(dataframe)
    normalized_df, scaler = _fit_and_transform_minmax(dataframe)
    county_encoder = _build_county_encoder(dataframe)

    scaler_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["MINMAX_SCALER_FILENAME"]
    encoder_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["COUNTY_ENCODER_FILENAME"]
    _save_pickle(scaler, scaler_path)
    _save_pickle(county_encoder, encoder_path)
    _save_normalized_panel(dataframe, normalized_df)

    min_value = float(normalized_df.min().min())
    max_value = float(normalized_df.max().max())
    print(f"[A2] Normalized global range: min={min_value:.4f}, max={max_value:.4f}")
    print("[A2] Completed successfully.")
    return normalized_df

