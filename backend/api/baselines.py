"""Baseline trajectory generators for forecast comparison."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

CONSTANTS: dict[str, Any] = {
    "HISTORICAL_YEARS": [2021, 2022, 2023, 2024, 2025],
    "FORECAST_YEARS": list(range(2026, 2037)),
    "LAST_HISTORICAL_YEAR": 2025,
}


def linear_trend_baseline(historical_scores: pd.DataFrame, counties: list[str]) -> list[dict[str, Any]]:
    """Extrapolate per-county score trends with first-degree polyfit."""
    rows: list[dict[str, Any]] = []
    years = np.array(CONSTANTS["HISTORICAL_YEARS"], dtype=np.float64)
    for county in counties:
        county_hist = historical_scores[historical_scores["county"] == county].sort_values("year")
        values = county_hist["score"].to_numpy(dtype=np.float64)
        if len(values) != len(years):
            continue
        slope, intercept = np.polyfit(years, values, deg=1)
        for year in CONSTANTS["FORECAST_YEARS"]:
            rows.append(
                {
                    "county": county,
                    "year": int(year),
                    "predicted_score": float(round(slope * float(year) + intercept, 1)),
                }
            )
    return rows


def county_mean_baseline(historical_scores: pd.DataFrame, counties: list[str]) -> list[dict[str, Any]]:
    """Project a flat county trajectory at each county's 2025 score."""
    rows: list[dict[str, Any]] = []
    for county in counties:
        county_last = historical_scores[
            (historical_scores["county"] == county)
            & (historical_scores["year"] == CONSTANTS["LAST_HISTORICAL_YEAR"])
        ]
        if county_last.empty:
            continue
        value = float(county_last.iloc[0]["score"])
        for year in CONSTANTS["FORECAST_YEARS"]:
            rows.append({"county": county, "year": int(year), "predicted_score": float(round(value, 1))})
    return rows

