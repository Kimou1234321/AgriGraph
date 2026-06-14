"""Phase A8 autoregressive STGNN pillar forecasting with derived sustainability scores."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import Tensor

from backend.pipeline.pillar_transform import load_frozen_transforms, pillar_matrix_to_scores
from backend.pipeline.stgnn import STGNN

CONSTANTS: dict[str, Any] = {
    "PHASE": "A8",
    "DATA_DIR": Path(__file__).resolve().parents[1] / "data",
    "ARTIFACTS_DIR": Path(__file__).resolve().parents[1] / "artifacts",
    "MODELS_DIR": Path(__file__).resolve().parents[1] / "models",
    "PILLAR_SCORES_FILENAME": "pillar_scores_augmented.csv",
    "PILLAR_TARGET_SCALER_FILENAME": "stgnn_pillar_target_scaler.pkl",
    "EDGE_INDEX_FILENAME": "edge_index.pt",
    "COUNTIES_FILENAME": "graph_counties.pkl",
    "FORECAST_WEIGHTS_FILENAME": "stgnn_forecast_weights.pt",
    "FORECAST_SCORES_FILENAME": "forecast_2026_2036.csv",
    "FORECAST_PILLARS_FILENAME": "forecast_pillars_2026_2036.csv",
    "REAL_VARIANT_ID": 0,
    "WINDOW_INPUT_YEARS": [2024, 2025],
    "FORECAST_YEARS": list(range(2026, 2037)),
    "PILLAR_LOWER_PERCENTILE": 5.0,
    "PILLAR_UPPER_PERCENTILE": 95.0,
    "PILLAR_DELTA_LIMIT_PERCENTILE": 95.0,
    "OOD_PILLAR_WEIGHT": 1.0,
    "OOD_MEDIUM_THRESHOLD": 1.15,
    "OOD_HIGH_THRESHOLD": 2.25,
    "BLEND_WEIGHT_LOW": 0.92,
    "BLEND_WEIGHT_MEDIUM": 0.72,
    "BLEND_WEIGHT_HIGH": 0.48,
    "FAILSAFE_INVALID_RATIO": 0.35,
    "SCORE_MIN": 0.0,
    "SCORE_MAX": 100.0,
    "EXPECTED_NODES": 26,
    "N_PILLARS": 4,
    "WINDOW_LEN": 2,
    "EPSILON": 1e-8,
}


def _print_header() -> None:
    """Print phase banner."""
    print("\n" + "=" * 72)
    print(f"[{CONSTANTS['PHASE']}] FORECASTING 2026-2036")
    print("=" * 72)


def load_pillar_target_scaler() -> tuple[np.ndarray, np.ndarray]:
    """Load pillar target normalization constants used in STGNN training."""
    path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["PILLAR_TARGET_SCALER_FILENAME"]
    with path.open("rb") as file:
        payload = pickle.load(file)
    target_mean = np.asarray(payload["target_mean"], dtype=np.float64)
    target_std = np.asarray(payload["target_std"], dtype=np.float64)
    return target_mean, target_std


def load_edge_index_and_counties() -> tuple[Tensor, list[str]]:
    """Load graph topology and node order."""
    edge_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["EDGE_INDEX_FILENAME"]
    county_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["COUNTIES_FILENAME"]
    edge_index = torch.load(edge_path, map_location="cpu")
    if not isinstance(edge_index, Tensor):
        edge_index = torch.as_tensor(edge_index)
    with county_path.open("rb") as file:
        counties = pickle.load(file)
    return edge_index.long(), list(counties)


def load_forecast_model(device: torch.device) -> STGNN:
    """Load STGNN weights trained in Phase A7b (forecast model only)."""
    weight_path = CONSTANTS["MODELS_DIR"] / CONSTANTS["FORECAST_WEIGHTS_FILENAME"]
    if not weight_path.exists():
        raise FileNotFoundError(f"[A8] Missing forecast weights: {weight_path}")
    payload = torch.load(weight_path, map_location=device)
    model = STGNN()
    model.load_state_dict(payload["state_dict"])
    model.to(device)
    model.eval()
    return model


def _pillar_matrix_for_year(
    pillars_df: pd.DataFrame,
    counties: list[str],
    year: int,
    variant_id: int,
) -> np.ndarray:
    """Return (N, 4) pillar matrix for one year and variant."""
    sub = pillars_df[
        (pillars_df["variant_id"] == variant_id) & (pillars_df["year"] == year)
    ].set_index("county")
    matrix = np.zeros((CONSTANTS["EXPECTED_NODES"], CONSTANTS["N_PILLARS"]), dtype=np.float64)
    for i, county in enumerate(counties):
        row = sub.loc[county]
        matrix[i, 0] = float(row["P1"])
        matrix[i, 1] = float(row["P2"])
        matrix[i, 2] = float(row["P3"])
        matrix[i, 3] = float(row["P4"])
    return matrix


def build_pillar_node_features(pillar_s: np.ndarray) -> Tensor:
    """Return pillar-only node features (N, 4)."""
    return torch.tensor(pillar_s, dtype=torch.float32)


def pillar_support_bounds(pillars_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Return historical real-data pillar percentile bounds for forecast clamping."""
    real = pillars_df[pillars_df["variant_id"] == CONSTANTS["REAL_VARIANT_ID"]]
    cols = [f"P{i + 1}" for i in range(CONSTANTS["N_PILLARS"])]
    lower = real[cols].quantile(CONSTANTS["PILLAR_LOWER_PERCENTILE"] / 100.0).to_numpy(dtype=np.float64)
    upper = real[cols].quantile(CONSTANTS["PILLAR_UPPER_PERCENTILE"] / 100.0).to_numpy(dtype=np.float64)
    return lower, upper


def clamp_pillars_to_support(pillars: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    """Clamp forecast pillar inputs to historical training support."""
    return np.clip(pillars, lower.reshape(1, -1), upper.reshape(1, -1))


def pillar_delta_limits(pillars_df: pd.DataFrame, counties: list[str]) -> np.ndarray:
    """Compute per-pillar absolute delta caps from real historical year-over-year changes."""
    deltas = np.zeros((0, CONSTANTS["N_PILLARS"]), dtype=np.float64)
    for county in counties:
        sub = pillars_df[
            (pillars_df["county"] == county) & (pillars_df["variant_id"] == CONSTANTS["REAL_VARIANT_ID"])
        ].sort_values("year")
        mat = sub[[f"P{i + 1}" for i in range(CONSTANTS["N_PILLARS"])]].to_numpy(dtype=np.float64)
        if len(mat) >= 2:
            county_delta = np.abs(mat[1:] - mat[:-1])
            deltas = np.vstack([deltas, county_delta]) if deltas.size else county_delta
    if deltas.size == 0:
        return np.ones(CONSTANTS["N_PILLARS"], dtype=np.float64)
    limits = np.percentile(deltas, CONSTANTS["PILLAR_DELTA_LIMIT_PERCENTILE"], axis=0)
    limits = np.where(limits <= CONSTANTS["EPSILON"], 1.0, limits)
    return limits


def clamp_pillar_deltas(pillars: np.ndarray, previous_pillars: np.ndarray, delta_limits: np.ndarray) -> np.ndarray:
    """Clamp forecast pillars by year-over-year change limits."""
    lower = previous_pillars - delta_limits.reshape(1, -1)
    upper = previous_pillars + delta_limits.reshape(1, -1)
    return np.clip(pillars, lower, upper)


def extrapolate_pillar_slopes(
    pillars_df: pd.DataFrame,
    counties: list[str],
    historical_years: list[int],
) -> tuple[np.ndarray, np.ndarray]:
    """Fit per-county per-pillar linear trend and return slopes (N,4) and intercepts (N,4)."""
    years = np.array(historical_years, dtype=np.float64)
    slopes = np.zeros((CONSTANTS["EXPECTED_NODES"], CONSTANTS["N_PILLARS"]), dtype=np.float64)
    intercepts = np.zeros_like(slopes)
    for pi in range(CONSTANTS["N_PILLARS"]):
        col = f"P{pi + 1}"
        for i, county in enumerate(counties):
            series = []
            for y in historical_years:
                val = pillars_df[
                    (pillars_df["county"] == county)
                    & (pillars_df["year"] == y)
                    & (pillars_df["variant_id"] == CONSTANTS["REAL_VARIANT_ID"])
                ][col].iloc[0]
                series.append(float(val))
            coeffs = np.polyfit(years, np.array(series, dtype=np.float64), deg=1)
            slopes[i, pi] = coeffs[0]
            intercepts[i, pi] = coeffs[1]
    return slopes, intercepts


def extrapolated_pillars_at_year(
    slopes: np.ndarray,
    intercepts: np.ndarray,
    year: int,
) -> np.ndarray:
    """Evaluate linear pillar extrapolation for all nodes at integer year t."""
    t = float(year)
    return slopes * t + intercepts


def inverse_scale_pillar_matrix(
    values: np.ndarray,
    target_mean: np.ndarray,
    target_std: np.ndarray,
) -> np.ndarray:
    """Map standardized pillar predictions back to pillar units."""
    return (values * np.maximum(target_std.reshape(1, -1), CONSTANTS["EPSILON"])) + target_mean.reshape(1, -1)


def compute_ood_score(
    pillars: np.ndarray,
    pillar_lower: np.ndarray,
    pillar_upper: np.ndarray,
) -> np.ndarray:
    """Compute OOD score from pillar distance to historical support."""
    center = (pillar_lower + pillar_upper) / 2.0
    radius = np.maximum((pillar_upper - pillar_lower) / 2.0, CONSTANTS["EPSILON"])
    pillar_dist = np.mean(np.abs((pillars - center.reshape(1, -1)) / radius.reshape(1, -1)), axis=1)
    return CONSTANTS["OOD_PILLAR_WEIGHT"] * pillar_dist


def adaptive_blend_with_fallback(
    raw_pillars: np.ndarray,
    fallback_pillars: np.ndarray,
    ood_scores: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Blend model pillar outputs with fallback based on OOD risk."""
    weights = np.full(raw_pillars.shape[0], CONSTANTS["BLEND_WEIGHT_LOW"], dtype=np.float64)
    medium_mask = ood_scores >= CONSTANTS["OOD_MEDIUM_THRESHOLD"]
    high_mask = ood_scores >= CONSTANTS["OOD_HIGH_THRESHOLD"]
    weights[medium_mask] = CONSTANTS["BLEND_WEIGHT_MEDIUM"]
    weights[high_mask] = CONSTANTS["BLEND_WEIGHT_HIGH"]
    blended = (weights.reshape(-1, 1) * raw_pillars) + ((1.0 - weights.reshape(-1, 1)) * fallback_pillars)
    return blended, weights


def apply_fail_safe_policy(
    pillars: np.ndarray,
    fallback_pillars: np.ndarray,
    invalid_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, str]:
    """Replace invalid pillar predictions with fallback."""
    invalid_ratio = float(np.mean(invalid_mask))
    mode = "normal"
    if invalid_ratio >= CONSTANTS["FAILSAFE_INVALID_RATIO"]:
        mode = "safe"
        affected = np.ones(pillars.shape[0], dtype=bool)
    elif np.any(invalid_mask):
        mode = "degraded"
        affected = invalid_mask.copy()
    else:
        affected = np.zeros(pillars.shape[0], dtype=bool)
    out = pillars.copy()
    out[affected] = fallback_pillars[affected]
    return out, affected, mode


def run_forecast() -> None:
    """Run Phase A8: autoregressive pillar STGNN with derived score outputs."""
    _print_header()
    device = torch.device("cpu")
    target_mean, target_std = load_pillar_target_scaler()
    edge_index, counties = load_edge_index_and_counties()
    model = load_forecast_model(device)
    edge_index = edge_index.to(device)
    frozen = load_frozen_transforms()

    pillar_path = CONSTANTS["DATA_DIR"] / CONSTANTS["PILLAR_SCORES_FILENAME"]
    pillars_df = pd.read_csv(pillar_path)
    historical_years = CONSTANTS["WINDOW_INPUT_YEARS"]
    pillar_lower, pillar_upper = pillar_support_bounds(pillars_df)
    pillar_delta_limit = pillar_delta_limits(pillars_df, counties)
    slopes, intercepts = extrapolate_pillar_slopes(pillars_df, counties, historical_years)

    window_tensors: list[Tensor] = []
    for wy in CONSTANTS["WINDOW_INPUT_YEARS"]:
        p_mat = _pillar_matrix_for_year(pillars_df, counties, wy, CONSTANTS["REAL_VARIANT_ID"])
        window_tensors.append(build_pillar_node_features(p_mat).to(device))

    pillar_prev = _pillar_matrix_for_year(
        pillars_df, counties, CONSTANTS["WINDOW_INPUT_YEARS"][-1], CONSTANTS["REAL_VARIANT_ID"]
    )
    predicted_rows: list[dict[str, Any]] = []
    pillar_forecast_rows: list[dict[str, Any]] = []
    fallback_replacements = 0

    for fy in CONSTANTS["FORECAST_YEARS"]:
        seq = torch.stack(window_tensors, dim=0)
        with torch.no_grad():
            pred_scaled = model(seq, edge_index).cpu().numpy()
        raw_pillars = inverse_scale_pillar_matrix(pred_scaled, target_mean, target_std)
        fallback_pillars = clamp_pillars_to_support(
            extrapolated_pillars_at_year(slopes, intercepts, fy),
            pillar_lower,
            pillar_upper,
        )
        ood_scores = compute_ood_score(raw_pillars, pillar_lower, pillar_upper)
        blended, blend_w = adaptive_blend_with_fallback(raw_pillars, fallback_pillars, ood_scores)
        blended = clamp_pillar_deltas(blended, pillar_prev, pillar_delta_limit)
        blended = clamp_pillars_to_support(blended, pillar_lower, pillar_upper)
        invalid_mask = ~np.isfinite(blended).all(axis=1)
        p_hat, affected_mask, mode = apply_fail_safe_policy(blended, fallback_pillars, invalid_mask)
        fallback_replacements += int(np.count_nonzero(affected_mask))
        derived_scores = pillar_matrix_to_scores(p_hat, frozen)
        derived_scores = np.clip(derived_scores, CONSTANTS["SCORE_MIN"], CONSTANTS["SCORE_MAX"])

        high_ratio = float(np.mean(ood_scores >= CONSTANTS["OOD_HIGH_THRESHOLD"]))
        print(
            f"[A8][{fy}] high_risk_ratio={high_ratio:.2f} avg_blend_weight={float(np.mean(blend_w)):.2f} "
            f"fail_safe_mode={mode}"
        )
        for i, county in enumerate(counties):
            predicted_rows.append(
                {
                    "county": county,
                    "year": fy,
                    "predicted_score": float(derived_scores[i]),
                    "blend_weight": float(round(blend_w[i], 4)),
                    "ood_score": float(round(ood_scores[i], 4)),
                    "forecast_policy": mode,
                }
            )
        for i, county in enumerate(counties):
            pillar_forecast_rows.append(
                {
                    "county": county,
                    "year": fy,
                    "P1": float(p_hat[i, 0]),
                    "P2": float(p_hat[i, 1]),
                    "P3": float(p_hat[i, 2]),
                    "P4": float(p_hat[i, 3]),
                }
            )
        pillar_prev = p_hat.copy()
        x_fy = build_pillar_node_features(p_hat).to(device)
        window_tensors = [window_tensors[1], x_fy]

    out_scores = pd.DataFrame(predicted_rows)
    out_pillars = pd.DataFrame(pillar_forecast_rows)
    score_path = CONSTANTS["DATA_DIR"] / CONSTANTS["FORECAST_SCORES_FILENAME"]
    pillar_path_out = CONSTANTS["DATA_DIR"] / CONSTANTS["FORECAST_PILLARS_FILENAME"]
    out_scores.to_csv(score_path, index=False)
    out_pillars.to_csv(pillar_path_out, index=False)

    print(f"[A8] Forecast saved: rows={len(out_scores)}, year_range=2026-2036")
    print(f"[A8] Files: {score_path}, {pillar_path_out}")
    print(
        f"[A8] Score range: min={out_scores['predicted_score'].min():.1f}, "
        f"max={out_scores['predicted_score'].max():.1f}, mean_2036="
        f"{out_scores[out_scores['year'] == 2036]['predicted_score'].mean():.1f}, "
        f"fallback_replacements={fallback_replacements}"
    )
