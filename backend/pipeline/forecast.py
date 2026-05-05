"""Phase A8 autoregressive STGNN forecasting from extrapolated pillar trends."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import Tensor

from backend.pipeline.stgnn import STGNN

CONSTANTS: dict[str, Any] = {
    "PHASE": "A8",
    "DATA_DIR": Path(__file__).resolve().parents[1] / "data",
    "ARTIFACTS_DIR": Path(__file__).resolve().parents[1] / "artifacts",
    "MODELS_DIR": Path(__file__).resolve().parents[1] / "models",
    "PILLAR_SCORES_FILENAME": "pillar_scores_augmented.csv",
    "SCORES_REAL_FILENAME": "sustainability_scores.csv",
    "LAG_NORM_FILENAME": "lag_norm.pkl",
    "TARGET_SCALER_FILENAME": "stgnn_target_scaler.pkl",
    "EDGE_INDEX_FILENAME": "edge_index.pt",
    "COUNTIES_FILENAME": "graph_counties.pkl",
    "FORECAST_WEIGHTS_FILENAME": "stgnn_forecast_weights.pt",
    "FORECAST_SCORES_FILENAME": "forecast_2026_2036.csv",
    "FORECAST_PILLARS_FILENAME": "forecast_pillars_2026_2036.csv",
    "REAL_VARIANT_ID": 0,
    "HISTORICAL_YEARS_FOR_TREND": [2021, 2022, 2023, 2024, 2025],
    "WINDOW_INPUT_YEARS": [2022, 2023, 2024, 2025],
    "FORECAST_YEARS": list(range(2026, 2037)),
    "PILLAR_LOWER_PERCENTILE": 5.0,
    "PILLAR_UPPER_PERCENTILE": 95.0,
    "PILLAR_DELTA_LIMIT_PERCENTILE": 95.0,
    "LAG_LOWER_PERCENTILE": 5.0,
    "LAG_UPPER_PERCENTILE": 95.0,
    "SCORE_VELOCITY_PERCENTILE": 95.0,
    "SCORE_ACCEL_PERCENTILE": 95.0,
    "OOD_PILLAR_WEIGHT": 0.45,
    "OOD_LAG_WEIGHT": 0.25,
    "OOD_SCORE_WEIGHT": 0.30,
    # OOD tiers: raised slightly so routine multi-year extrapolation stays in low/medium blend,
    # not forced toward linear fallback.
    "OOD_MEDIUM_THRESHOLD": 1.15,
    "OOD_HIGH_THRESHOLD": 2.25,
    # Weight on *raw* STGNN output in convex blend with linear fallback (higher = trust model more).
    "BLEND_WEIGHT_LOW": 0.92,
    "BLEND_WEIGHT_MEDIUM": 0.72,
    "BLEND_WEIGHT_HIGH": 0.48,
    # Fail-safe: only full-grid replacement when many nodes are non-finite/out-of-range.
    # High OOD is handled by adaptive_blend_with_fallback only — no second hard replace by OOD.
    "FAILSAFE_INVALID_RATIO": 0.35,
    "SCORE_MIN": 0.0,
    "SCORE_MAX": 100.0,
    "FIRST_YEAR_LAG_ZERO": 2021,
    "EXPECTED_NODES": 26,
    "N_PILLARS": 4,
    "EPSILON": 1e-8,
}


def _print_header() -> None:
    """Print phase banner."""
    print("\n" + "=" * 72)
    print(f"[{CONSTANTS['PHASE']}] FORECASTING 2026-2036")
    print("=" * 72)


def load_lag_norm() -> tuple[float, float]:
    """Load global score mean and std for lag feature."""
    path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["LAG_NORM_FILENAME"]
    with path.open("rb") as file:
        payload = pickle.load(file)
    return float(payload["y_bar"]), float(payload["sigma_y"])


def load_target_scaler() -> tuple[float, float]:
    """Load target normalization constants used in STGNN training."""
    path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["TARGET_SCALER_FILENAME"]
    with path.open("rb") as file:
        payload = pickle.load(file)
    return float(payload["target_mean"]), float(payload["target_std"])


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


def _scores_vector_for_year(
    scores_df: pd.DataFrame,
    counties: list[str],
    year: int,
    variant_id: int,
) -> np.ndarray:
    """Return (N,) scores for one year and variant."""
    sub = scores_df[
        (scores_df["variant_id"] == variant_id) & (scores_df["year"] == year)
    ].set_index("county")
    vec = np.zeros(CONSTANTS["EXPECTED_NODES"], dtype=np.float64)
    for i, county in enumerate(counties):
        vec[i] = float(sub.loc[county, "score"])
    return vec


def _load_real_scores_wide() -> pd.DataFrame:
    """Load real sustainability scores (variant 0 implied)."""
    path = CONSTANTS["DATA_DIR"] / CONSTANTS["SCORES_REAL_FILENAME"]
    if not path.exists():
        raise FileNotFoundError(f"[A8] Missing {path}")
    return pd.read_csv(path)


def extrapolate_pillar_slopes(
    pillars_df: pd.DataFrame,
    counties: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    """Fit per-county per-pillar linear trend a*t + b over 2021-2025; return slopes (N,4) and intercepts (N,4)."""
    years = np.array(CONSTANTS["HISTORICAL_YEARS_FOR_TREND"], dtype=np.float64)
    slopes = np.zeros((CONSTANTS["EXPECTED_NODES"], CONSTANTS["N_PILLARS"]), dtype=np.float64)
    intercepts = np.zeros_like(slopes)
    for pi in range(CONSTANTS["N_PILLARS"]):
        col = f"P{pi + 1}"
        for i, county in enumerate(counties):
            series = []
            for y in CONSTANTS["HISTORICAL_YEARS_FOR_TREND"]:
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


def lag_support_bounds(scores_real: pd.DataFrame, counties: list[str], y_bar: float, sigma_y: float) -> tuple[float, float]:
    """Compute lag z-score support bounds from real historical lag values."""
    z_values: list[float] = []
    for county in counties:
        for year in [2022, 2023, 2024, 2025]:
            prev_score = float(
                scores_real[(scores_real["county"] == county) & (scores_real["year"] == year - 1)]["score"].iloc[0]
            )
            z_values.append((prev_score - y_bar) / max(sigma_y, CONSTANTS["EPSILON"]))
    z_array = np.array(z_values, dtype=np.float64)
    lower = float(np.percentile(z_array, CONSTANTS["LAG_LOWER_PERCENTILE"]))
    upper = float(np.percentile(z_array, CONSTANTS["LAG_UPPER_PERCENTILE"]))
    if lower >= upper:
        lower, upper = -2.0, 2.0
    return lower, upper


def score_temporal_limits(scores_real: pd.DataFrame, counties: list[str]) -> tuple[float, float]:
    """Compute robust velocity and acceleration limits from real historical scores."""
    velocities: list[float] = []
    accelerations: list[float] = []
    for county in counties:
        sub = scores_real[scores_real["county"] == county].sort_values("year")
        vec = sub["score"].to_numpy(dtype=np.float64)
        if len(vec) >= 2:
            d1 = vec[1:] - vec[:-1]
            velocities.extend(np.abs(d1).tolist())
            if len(d1) >= 2:
                d2 = d1[1:] - d1[:-1]
                accelerations.extend(np.abs(d2).tolist())
    vel_lim = float(np.percentile(np.array(velocities, dtype=np.float64), CONSTANTS["SCORE_VELOCITY_PERCENTILE"]))
    acc_source = np.array(accelerations, dtype=np.float64) if accelerations else np.array([vel_lim], dtype=np.float64)
    acc_lim = float(np.percentile(acc_source, CONSTANTS["SCORE_ACCEL_PERCENTILE"]))
    vel_lim = max(vel_lim, 1.0)
    acc_lim = max(acc_lim, 0.5)
    return vel_lim, acc_lim


def _score_trend_fallback(scores_real: pd.DataFrame, counties: list[str], year: int) -> np.ndarray:
    """Compute bounded county-level linear score fallback for invalid STGNN outputs."""
    years = np.array(CONSTANTS["HISTORICAL_YEARS_FOR_TREND"], dtype=np.float64)
    fallback = np.zeros(CONSTANTS["EXPECTED_NODES"], dtype=np.float64)
    for idx, county in enumerate(counties):
        series = np.array(
            [
                float(scores_real[(scores_real["county"] == county) & (scores_real["year"] == y)]["score"].iloc[0])
                for y in CONSTANTS["HISTORICAL_YEARS_FOR_TREND"]
            ],
            dtype=np.float64,
        )
        slope, intercept = np.polyfit(years, series, deg=1)
        fallback[idx] = (slope * float(year)) + intercept
    return np.clip(fallback, CONSTANTS["SCORE_MIN"], CONSTANTS["SCORE_MAX"])


def bounded_score_predictions(
    raw_scores: np.ndarray,
    fallback_scores: np.ndarray,
) -> tuple[np.ndarray, int]:
    """Replace out-of-domain predictions with fallback, then enforce score bounds."""
    invalid_mask = (
        ~np.isfinite(raw_scores)
        | (raw_scores < CONSTANTS["SCORE_MIN"])
        | (raw_scores > CONSTANTS["SCORE_MAX"])
    )
    bounded = raw_scores.copy()
    bounded[invalid_mask] = fallback_scores[invalid_mask]
    bounded = np.clip(bounded, CONSTANTS["SCORE_MIN"], CONSTANTS["SCORE_MAX"])
    return bounded, int(np.count_nonzero(invalid_mask))


def compute_ood_score(
    pillars: np.ndarray,
    lag_z: np.ndarray,
    raw_scores: np.ndarray,
    pillar_lower: np.ndarray,
    pillar_upper: np.ndarray,
    target_mean: float,
    target_std: float,
) -> np.ndarray:
    """Compute OOD score from pillar, lag, and raw score distances."""
    center = (pillar_lower + pillar_upper) / 2.0
    radius = np.maximum((pillar_upper - pillar_lower) / 2.0, CONSTANTS["EPSILON"])
    pillar_dist = np.mean(np.abs((pillars - center.reshape(1, -1)) / radius.reshape(1, -1)), axis=1)
    lag_scale = max(abs(float(np.percentile(lag_z, 90))), 1.0)
    lag_dist = np.abs(lag_z) / lag_scale
    score_dist = np.abs((raw_scores - target_mean) / max(target_std, CONSTANTS["EPSILON"]))
    return (
        CONSTANTS["OOD_PILLAR_WEIGHT"] * pillar_dist
        + CONSTANTS["OOD_LAG_WEIGHT"] * lag_dist
        + CONSTANTS["OOD_SCORE_WEIGHT"] * score_dist
    )


def adaptive_blend_with_fallback(
    raw_scores: np.ndarray,
    fallback_scores: np.ndarray,
    ood_scores: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Blend model outputs with fallback based on OOD risk."""
    weights = np.full_like(raw_scores, CONSTANTS["BLEND_WEIGHT_LOW"], dtype=np.float64)
    medium_mask = ood_scores >= CONSTANTS["OOD_MEDIUM_THRESHOLD"]
    high_mask = ood_scores >= CONSTANTS["OOD_HIGH_THRESHOLD"]
    weights[medium_mask] = CONSTANTS["BLEND_WEIGHT_MEDIUM"]
    weights[high_mask] = CONSTANTS["BLEND_WEIGHT_HIGH"]
    blended = (weights * raw_scores) + ((1.0 - weights) * fallback_scores)
    return blended, weights


def apply_temporal_rate_limits(
    scores: np.ndarray,
    last_scores: np.ndarray,
    last_deltas: np.ndarray,
    velocity_limit: float,
    accel_limit: float,
) -> np.ndarray:
    """Apply bounded velocity and acceleration constraints county-wise."""
    delta = scores - last_scores
    delta = np.clip(delta, -velocity_limit, velocity_limit)
    delta_lower = last_deltas - accel_limit
    delta_upper = last_deltas + accel_limit
    delta = np.clip(delta, delta_lower, delta_upper)
    return last_scores + delta


def apply_fail_safe_policy(
    scores: np.ndarray,
    fallback_scores: np.ndarray,
    _ood_scores: np.ndarray,
    invalid_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, str]:
    """Replace only invalid (non-finite / out-of-domain) nodes with fallback.

    High OOD risk is already absorbed by ``adaptive_blend_with_fallback``; we do not
    hard-replace finite predictions again based on OOD, so trajectories do not collapse
    onto the linear trend baseline after blending.
    """
    invalid_ratio = float(np.mean(invalid_mask))
    mode = "normal"
    if invalid_ratio >= CONSTANTS["FAILSAFE_INVALID_RATIO"]:
        mode = "safe"
        affected = np.ones_like(invalid_mask, dtype=bool)
    elif np.any(invalid_mask):
        mode = "degraded"
        affected = invalid_mask.copy()
    else:
        affected = np.zeros_like(invalid_mask, dtype=bool)
    out = scores.copy()
    out[affected] = fallback_scores[affected]
    return out, affected, mode


def build_node_features(
    pillar_s: np.ndarray,
    prev_year_scores: np.ndarray,
    calendar_year: int,
    y_bar: float,
    sigma_y: float,
    lag_bounds: tuple[float, float] | None = None,
) -> Tensor:
    """Stack pillars and lag into (N, 5) node features."""
    if calendar_year <= CONSTANTS["FIRST_YEAR_LAG_ZERO"]:
        lag = np.zeros(CONSTANTS["EXPECTED_NODES"], dtype=np.float64)
    else:
        lag = (prev_year_scores - y_bar) / max(sigma_y, CONSTANTS["EPSILON"])
    if lag_bounds is not None:
        lag = np.clip(lag, lag_bounds[0], lag_bounds[1])
    features = np.concatenate([pillar_s, lag.reshape(-1, 1)], axis=1)
    return torch.tensor(features, dtype=torch.float32)


def run_forecast() -> None:
    """Run Phase A8: extrapolate pillars, autoregressive STGNN, save forecast CSVs."""
    _print_header()
    device = torch.device("cpu")
    y_bar, sigma_y = load_lag_norm()
    target_mean, target_std = load_target_scaler()
    edge_index, counties = load_edge_index_and_counties()
    model = load_forecast_model(device)
    edge_index = edge_index.to(device)

    pillar_path = CONSTANTS["DATA_DIR"] / CONSTANTS["PILLAR_SCORES_FILENAME"]
    pillars_df = pd.read_csv(pillar_path)
    scores_real = _load_real_scores_wide()
    scores_real = scores_real.sort_values(["county", "year"])

    slopes, intercepts = extrapolate_pillar_slopes(pillars_df, counties)
    pillar_lower, pillar_upper = pillar_support_bounds(pillars_df)
    pillar_delta_limit = pillar_delta_limits(pillars_df, counties)
    lag_bounds = lag_support_bounds(scores_real, counties, y_bar, sigma_y)
    velocity_limit, accel_limit = score_temporal_limits(scores_real, counties)
    pillar_prev = _pillar_matrix_for_year(pillars_df, counties, 2025, CONSTANTS["REAL_VARIANT_ID"])
    fallback_replacements = 0

    window_tensors: list[Tensor] = []
    prev_scores_by_year: dict[int, np.ndarray] = {}
    for y in range(2021, 2026):
        prev_scores_by_year[y] = np.array(
            [
                float(
                    scores_real[(scores_real["county"] == c) & (scores_real["year"] == y)]["score"].iloc[0]
                )
                for c in counties
            ],
            dtype=np.float64,
        )

    for wy in CONSTANTS["WINDOW_INPUT_YEARS"]:
        p_mat = _pillar_matrix_for_year(pillars_df, counties, wy, CONSTANTS["REAL_VARIANT_ID"])
        prev_y = wy - 1
        prev_vec = prev_scores_by_year[prev_y]
        window_tensors.append(build_node_features(p_mat, prev_vec, wy, y_bar, sigma_y, lag_bounds).to(device))

    predicted_rows: list[dict[str, Any]] = []
    pillar_forecast_rows: list[dict[str, Any]] = []
    last_scores = prev_scores_by_year[2025].copy()
    last_deltas = np.zeros_like(last_scores)

    for fy in CONSTANTS["FORECAST_YEARS"]:
        p_hat = clamp_pillars_to_support(
            extrapolated_pillars_at_year(slopes, intercepts, fy),
            pillar_lower,
            pillar_upper,
        )
        p_hat = clamp_pillar_deltas(p_hat, pillar_prev, pillar_delta_limit)
        p_hat = clamp_pillars_to_support(p_hat, pillar_lower, pillar_upper)
        prev_for_lag = last_scores if fy > CONSTANTS["FORECAST_YEARS"][0] else prev_scores_by_year[2025]
        lag_z = (prev_for_lag - y_bar) / max(sigma_y, CONSTANTS["EPSILON"])
        lag_z = np.clip(lag_z, lag_bounds[0], lag_bounds[1])
        x_fy = build_node_features(p_hat, prev_for_lag, fy, y_bar, sigma_y, lag_bounds).to(device)
        seq = torch.stack(window_tensors, dim=0)
        with torch.no_grad():
            y_hat_scaled = model(seq, edge_index).cpu().numpy()
        y_hat_raw = (y_hat_scaled * max(target_std, CONSTANTS["EPSILON"])) + target_mean
        fallback_scores = _score_trend_fallback(scores_real, counties, fy)
        ood_scores = compute_ood_score(
            pillars=p_hat,
            lag_z=lag_z,
            raw_scores=y_hat_raw,
            pillar_lower=pillar_lower,
            pillar_upper=pillar_upper,
            target_mean=target_mean,
            target_std=target_std,
        )
        y_blend, blend_w = adaptive_blend_with_fallback(y_hat_raw, fallback_scores, ood_scores)
        y_limited = apply_temporal_rate_limits(y_blend, last_scores, last_deltas, velocity_limit, accel_limit)
        invalid_mask = (
            ~np.isfinite(y_limited)
            | (y_limited < CONSTANTS["SCORE_MIN"])
            | (y_limited > CONSTANTS["SCORE_MAX"])
        )
        y_safe, affected_mask, mode = apply_fail_safe_policy(y_limited, fallback_scores, ood_scores, invalid_mask)
        y_hat, replaced_count = bounded_score_predictions(y_safe, fallback_scores)
        fallback_replacements += replaced_count + int(np.count_nonzero(affected_mask))
        high_ratio = float(np.mean(ood_scores >= CONSTANTS["OOD_HIGH_THRESHOLD"]))
        print(
            f"[A8][{fy}] high_risk_ratio={high_ratio:.2f} avg_blend_weight={float(np.mean(blend_w)):.2f} "
            f"max_delta={float(np.max(np.abs(y_hat - last_scores))):.2f} fail_safe_mode={mode}"
        )
        for i, county in enumerate(counties):
            predicted_rows.append(
                {
                    "county": county,
                    "year": fy,
                    "predicted_score": float(round(y_hat[i], 1)),
                    "blend_weight": float(round(blend_w[i], 4)),
                    "ood_score": float(round(ood_scores[i], 4)),
                    "fallback_score": float(round(fallback_scores[i], 1)),
                    "forecast_policy": mode,
                    "raw_stgnn_score": float(round(y_hat_raw[i], 1)),
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
        last_deltas = y_hat - last_scores
        last_scores = y_hat.copy()
        pillar_prev = p_hat.copy()
        window_tensors = [window_tensors[1], window_tensors[2], window_tensors[3], x_fy]

    out_scores = pd.DataFrame(predicted_rows)
    out_pillars = pd.DataFrame(pillar_forecast_rows)
    score_path = CONSTANTS["DATA_DIR"] / CONSTANTS["FORECAST_SCORES_FILENAME"]
    pillar_path_out = CONSTANTS["DATA_DIR"] / CONSTANTS["FORECAST_PILLARS_FILENAME"]
    out_scores.to_csv(score_path, index=False)
    out_pillars.to_csv(pillar_path_out, index=False)

    mean_2025 = float(scores_real[scores_real["year"] == 2025]["score"].mean())
    mean_2026 = float(out_scores[out_scores["year"] == 2026]["predicted_score"].mean())
    print(f"[A8] Forecast saved: rows={len(out_scores)}, year_range=2026-2036")
    print(f"[A8] Files: {score_path}, {pillar_path_out}")
    print(
        f"[A8] Score range: min={out_scores['predicted_score'].min():.1f}, "
        f"max={out_scores['predicted_score'].max():.1f}, mean_2036="
        f"{out_scores[out_scores['year'] == 2036]['predicted_score'].mean():.1f}, "
        f"fallback_replacements={fallback_replacements}"
    )
    print(f"[A8] Sanity: mean_2025(real)={mean_2025:.2f}, mean_2026(pred)={mean_2026:.2f}, delta={mean_2026 - mean_2025:.2f}")
