"""FastAPI routes for AgriGraph prototype endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.api.baselines import county_mean_baseline, linear_trend_baseline
from backend.api.explanation import generate_explanation
from backend.api.state import AppState
from backend.pipeline.counterfactual import simulate_counterfactual, simulate_counterfactual_global
from backend.pipeline.pillar_transform import CONSTANTS as PT_CONST
from backend.pipeline.pillar_transform import raw_to_pillars

CONSTANTS: dict[str, Any] = {
    "ROUTER_PREFIX": "/api",
    "YEAR_2025": 2025,
    "DELTA_MIN": -1.0,
    "DELTA_MAX": 1.0,
    "HISTORICAL_END_YEAR": 2025,
    "FORECAST_END_YEAR": 2036,
    "ARTIFACTS_DIR": Path(__file__).resolve().parents[1] / "artifacts",
    "DATA_DIR": Path(__file__).resolve().parents[1] / "data",
    "INDICATOR_COLS": ["calving_interval", "six_wk_calving_rate", "cows_culled_pct"],
    "PILLAR_CLIP_MIN": -3.0,
    "PILLAR_CLIP_MAX": 3.0,
}

router = APIRouter(prefix=CONSTANTS["ROUTER_PREFIX"])


class PreviewRequest(BaseModel):
    """Input for slider-only pillar preview endpoint."""

    county: str
    interventions: dict[str, float] = Field(default_factory=dict)


class PreviewResponse(BaseModel):
    """Pillar preview payload."""

    before: dict[str, float]
    after: dict[str, float]
    delta: dict[str, float]


class CounterfactualRequest(BaseModel):
    """Input payload for full counterfactual simulation."""

    county: str
    interventions: dict[str, float] = Field(default_factory=dict)
    horizon: int = 25


class CounterfactualResponse(BaseModel):
    """Counterfactual endpoint payload."""

    baseline: list[dict[str, Any]]
    counterfactual: list[dict[str, Any]]
    uplift: list[dict[str, Any]]
    pillar_shifts: dict[str, float]
    explanation: str


class GlobalCounterfactualRequest(BaseModel):
    """Input payload for global multi-county counterfactual simulation."""

    scenarios: dict[str, dict[str, float]] = Field(default_factory=dict)
    horizon: int = 11


class GlobalCounterfactualResponse(BaseModel):
    """Global counterfactual endpoint payload."""

    horizon: list[int]
    final_year: int
    by_county: dict[str, dict[str, Any]]


def _state(request: Request) -> AppState:
    """Return app startup cache from request state."""
    cache = getattr(request.app.state, "cache", None)
    if cache is None:
        raise HTTPException(status_code=500, detail="API startup cache unavailable.")
    return cache


def _pillars_to_dict(values: np.ndarray) -> dict[str, float]:
    """Convert a 4-length numpy vector into P1..P4 dict."""
    return {f"P{index + 1}": float(values[index]) for index in range(4)}


def _pillar_norm(value: float) -> float:
    """Map standardized pillar value to a clipped 0-100 display scale."""
    clipped = float(np.clip(value, CONSTANTS["PILLAR_CLIP_MIN"], CONSTANTS["PILLAR_CLIP_MAX"]))
    return float(round((clipped - CONSTANTS["PILLAR_CLIP_MIN"]) / 6.0 * 100.0, 1))


def _trend_project_values(
    frame: pd.DataFrame,
    county: str,
    year: int,
    value_col: str,
    historical_end: int,
) -> float | None:
    """Project county feature by linear trend or return historical value."""
    county_rows = frame[frame["county"] == county].sort_values("year")
    if county_rows.empty:
        return None
    if year <= historical_end:
        match = county_rows[county_rows["year"] == year]
        if match.empty:
            return None
        return float(match.iloc[0][value_col])
    hist = county_rows[county_rows["year"] <= historical_end]
    if len(hist) < 2:
        last = hist[hist["year"] == historical_end]
        if last.empty:
            return None
        return float(last.iloc[0][value_col])
    years = hist["year"].to_numpy(dtype=np.float64)
    vals = hist[value_col].to_numpy(dtype=np.float64)
    slope, intercept = np.polyfit(years, vals, deg=1)
    return float(slope * float(year) + intercept)


@router.get("/counties")
async def get_counties(request: Request) -> dict[str, list[str]]:
    """Return canonical county list."""
    state = _state(request)
    return {"counties": sorted(state.counties)}


@router.get("/historical")
async def get_historical(request: Request) -> list[dict[str, Any]]:
    """Return historical sustainability rows."""
    state = _state(request)
    return state.historical_scores[["county", "year", "score"]].to_dict(orient="records")


@router.get("/forecast")
async def get_forecast(request: Request) -> list[dict[str, Any]]:
    """Return forecast rows merged with uncertainty bands."""
    state = _state(request)
    merged = state.forecast_scores.merge(state.uncertainty, on=["county", "year"], how="left")
    cols = ["county", "year", "predicted_score", "lower_5pct", "upper_95pct"]
    return merged[cols].to_dict(orient="records")


@router.get("/pillars/{county}")
async def get_pillars(county: str, request: Request) -> list[dict[str, Any]]:
    """Return historical plus forecast pillar timeline for one county."""
    state = _state(request)
    if county not in state.counties:
        raise HTTPException(status_code=404, detail=f"Unknown county: {county}")

    historical = state.pillars_augmented[state.pillars_augmented["county"] == county][
        ["year", "P1", "P2", "P3", "P4"]
    ]
    forecast = state.pillars_forecast[state.pillars_forecast["county"] == county][
        ["year", "P1", "P2", "P3", "P4"]
    ]
    combined = pd.concat([historical, forecast], ignore_index=True).sort_values("year")
    rows: list[dict[str, Any]] = []
    if not combined.empty:
        for _, row in combined.iterrows():
            rows.append(
                {
                    "year": int(row["year"]),
                    state.pillar_label_keys["P1"]: float(row["P1"]),
                    state.pillar_label_keys["P2"]: float(row["P2"]),
                    state.pillar_label_keys["P3"]: float(row["P3"]),
                    state.pillar_label_keys["P4"]: float(row["P4"]),
                    f"{state.pillar_label_keys['P1']}_norm": _pillar_norm(float(row["P1"])),
                    f"{state.pillar_label_keys['P2']}_norm": _pillar_norm(float(row["P2"])),
                    f"{state.pillar_label_keys['P3']}_norm": _pillar_norm(float(row["P3"])),
                    f"{state.pillar_label_keys['P4']}_norm": _pillar_norm(float(row["P4"])),
                }
            )
    return rows


@router.post("/pillars/preview", response_model=PreviewResponse)
async def preview_pillars(payload: PreviewRequest, request: Request) -> PreviewResponse:
    """Compute immediate pillar shifts from intervention deltas without STGNN inference."""
    state = _state(request)
    if payload.county not in state.counties:
        raise HTTPException(status_code=404, detail=f"Unknown county: {payload.county}")

    row = state.x_normalized[
        (state.x_normalized["county"] == payload.county) & (state.x_normalized["year"] == CONSTANTS["YEAR_2025"])
    ]
    if len(row) != 1:
        raise HTTPException(status_code=400, detail=f"Missing normalized 2025 row for {payload.county}")

    x_base = row[PT_CONST["FEATURE_COLS"]].to_numpy(dtype=np.float64).flatten()
    x_after = x_base.copy()
    for feature, delta in payload.interventions.items():
        if feature not in PT_CONST["FEATURE_COLS"]:
            continue
        idx = PT_CONST["FEATURE_COLS"].index(feature)
        clipped_delta = float(np.clip(float(delta), CONSTANTS["DELTA_MIN"], CONSTANTS["DELTA_MAX"]))
        x_after[idx] = x_after[idx] * (1.0 + clipped_delta)
    x_after = np.clip(x_after, 0.0, 1.0)

    before_vec = raw_to_pillars(x_base, state.frozen)
    after_vec = raw_to_pillars(x_after, state.frozen)
    delta_vec = after_vec - before_vec
    return PreviewResponse(
        before=_pillars_to_dict(before_vec),
        after=_pillars_to_dict(after_vec),
        delta=_pillars_to_dict(delta_vec),
    )


@router.post("/counterfactual", response_model=CounterfactualResponse)
async def counterfactual(payload: CounterfactualRequest, request: Request) -> CounterfactualResponse:
    """Run full counterfactual simulator and return score trajectories plus explanation."""
    state = _state(request)
    if payload.county not in state.counties:
        raise HTTPException(status_code=404, detail=f"Unknown county: {payload.county}")

    result = simulate_counterfactual(
        county=payload.county,
        interventions=payload.interventions,
        horizon=payload.horizon,
    )
    pillar_shifts = {
        "P1": float(result["pillar_shifts"]["P1_delta"]),
        "P2": float(result["pillar_shifts"]["P2_delta"]),
        "P3": float(result["pillar_shifts"]["P3_delta"]),
        "P4": float(result["pillar_shifts"]["P4_delta"]),
    }
    explanation = generate_explanation(
        county=payload.county,
        interventions=payload.interventions,
        pillar_shifts=pillar_shifts,
        uplift_final_year=float(result["uplift_final_year"]),
        final_year=int(result["final_year"]),
        pillar_label_keys=state.pillar_label_keys,
    )
    return CounterfactualResponse(
        baseline=result["baseline"],
        counterfactual=result["counterfactual"],
        uplift=result["uplift"],
        pillar_shifts=pillar_shifts,
        explanation=explanation,
    )


@router.post("/counterfactual/global", response_model=GlobalCounterfactualResponse)
async def counterfactual_global(
    payload: GlobalCounterfactualRequest,
    request: Request,
) -> GlobalCounterfactualResponse:
    """Run global counterfactual simulator over all selected county interventions."""
    state = _state(request)
    if not payload.scenarios:
        raise HTTPException(status_code=400, detail="scenarios cannot be empty")
    for county in payload.scenarios:
        if county not in state.counties:
            raise HTTPException(status_code=404, detail=f"Unknown county: {county}")

    result = simulate_counterfactual_global(scenarios=payload.scenarios, horizon=payload.horizon)
    for county, county_block in result["by_county"].items():
        if county not in payload.scenarios:
            continue
        shifts = {key: float(value) for key, value in county_block["pillar_shifts"].items()}
        county_block["explanation"] = generate_explanation(
            county=county,
            interventions=payload.scenarios[county],
            pillar_shifts=shifts,
            uplift_final_year=float(county_block["uplift_final_year"]),
            final_year=int(result["final_year"]),
            pillar_label_keys=state.pillar_label_keys,
        )
    return GlobalCounterfactualResponse(
        horizon=list(result["horizon"]),
        final_year=int(result["final_year"]),
        by_county=result["by_county"],
    )


@router.get("/comparison")
async def get_comparison(request: Request) -> dict[str, list[dict[str, Any]]]:
    """Return STGNN and baseline forecast trajectories for all counties."""
    state = _state(request)
    stgnn = state.forecast_scores[["county", "year", "predicted_score"]].to_dict(orient="records")
    linear = linear_trend_baseline(state.historical_scores, state.counties)
    county_mean = county_mean_baseline(state.historical_scores, state.counties)
    return {"stgnn": stgnn, "linear_trend": linear, "county_mean": county_mean}


@router.get("/metrics")
async def get_metrics(request: Request) -> dict[str, Any]:
    """Return held-out A7 metrics only."""
    state = _state(request)
    metrics = state.metrics
    return {
        "train_r2": float(metrics.get("training_r2_mean", 0.0)),
        "val_r2": float(metrics.get("validation_r2_mean", 0.0)),
        "test_r2": float(metrics.get("test_r2", 0.0)),
        "mae": float(metrics.get("test_mae", 0.0)),
        "mse": float(metrics.get("test_mse", 0.0)),
        "mae_score": float(metrics.get("test_mae", 0.0)),
        "mse_score": float(metrics.get("test_mse", 0.0)),
        "mae_norm": float(metrics.get("test_mae_norm", 0.0)),
        "mse_norm": float(metrics.get("test_mse_norm", 0.0)),
        "eval_train_variants": metrics.get("eval_train_variants", []),
        "eval_test_variant": int(metrics.get("eval_test_variant", 0)),
        "target_scaler": metrics.get("target_scaler", {}),
    }


@router.get("/county/{county}/indicators")
async def get_county_indicators(county: str, request: Request, year: int = 2025) -> dict[str, Any]:
    """Return score and three key raw indicators for one county-year."""
    state = _state(request)
    if county not in state.counties:
        raise HTTPException(status_code=404, detail=f"Unknown county: {county}")
    if year < 2021 or year > CONSTANTS["FORECAST_END_YEAR"]:
        raise HTTPException(status_code=400, detail="Year must be within 2021..2036.")

    indicators_df = pd.read_csv(CONSTANTS["DATA_DIR"] / "icbf_clean.csv")
    score_row: dict[str, Any] | None = None
    if year <= CONSTANTS["HISTORICAL_END_YEAR"]:
        hist = state.historical_scores[
            (state.historical_scores["county"] == county) & (state.historical_scores["year"] == year)
        ]
        if not hist.empty:
            score_row = hist.iloc[0].to_dict()
    else:
        forecast = state.forecast_scores[
            (state.forecast_scores["county"] == county) & (state.forecast_scores["year"] == year)
        ]
        if not forecast.empty:
            score_row = {"score": float(forecast.iloc[0]["predicted_score"])}

    response: dict[str, Any] = {
        "county": county,
        "year": year,
        "forecasted": bool(year > CONSTANTS["HISTORICAL_END_YEAR"]),
        "score": float(score_row["score"]) if score_row is not None else None,
    }
    for col in CONSTANTS["INDICATOR_COLS"]:
        response[col] = _trend_project_values(
            frame=indicators_df,
            county=county,
            year=year,
            value_col=col,
            historical_end=CONSTANTS["HISTORICAL_END_YEAR"],
        )
    return response


@router.get("/methodology/learning_curves")
async def get_learning_curves(_: Request) -> dict[str, Any]:
    """Return CVAE epoch loss history and STGNN fold metrics."""
    artifacts = CONSTANTS["ARTIFACTS_DIR"]
    with (artifacts / "cvae_training_history.json").open("r", encoding="utf-8") as file:
        cvae_history = json.load(file)
    with (artifacts / "stgnn_metrics.json").open("r", encoding="utf-8") as file:
        stgnn = json.load(file)
    folds = []
    train = stgnn.get("training_r2_per_fold", [])
    val = stgnn.get("validation_r2_per_fold", [])
    for idx in range(min(len(train), len(val))):
        folds.append({"fold": idx + 1, "train_r2": float(train[idx]), "val_r2": float(val[idx])})
    return {"cvae": cvae_history, "stgnn": folds}


@router.get("/methodology/cvae_validation")
async def get_cvae_validation(_: Request) -> dict[str, Any]:
    """Return per-year real-vs-synthetic feature means and summary metrics."""
    artifacts = CONSTANTS["ARTIFACTS_DIR"]
    data_df = pd.read_csv(CONSTANTS["DATA_DIR"] / "x_augmented.csv")
    with (artifacts / "cvae_validation_summary.json").open("r", encoding="utf-8") as file:
        summary = json.load(file)
    final_summary = summary.get("final_validation", summary)
    quality_gate = summary.get("quality_gate", {"passed": True, "fallback_used": False, "failures": []})
    years = sorted(data_df["year"].unique().tolist())
    features = list(PT_CONST["FEATURE_COLS"])
    real_means: list[list[float]] = []
    synth_means: list[list[float]] = []
    for year in years:
        year_df = data_df[data_df["year"] == year]
        real_df = year_df[year_df["variant_id"] == 0]
        synth_df = year_df[year_df["variant_id"] > 0]
        real_means.append([float(real_df[col].mean()) for col in features])
        synth_means.append([float(synth_df[col].mean()) for col in features])
    return {
        "years": years,
        "features": features,
        "real_means": real_means,
        "synth_means": synth_means,
        "summary": final_summary,
        "quality_gate": quality_gate,
    }

