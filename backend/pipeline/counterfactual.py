"""Phase A10 counterfactual: raw delta -> pillar recompute -> STGNN autoregressive path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import Tensor

from backend.pipeline import forecast as forecast_mod
from backend.pipeline.forecast import (
    adaptive_blend_with_fallback,
    apply_fail_safe_policy,
    apply_temporal_rate_limits,
    bounded_score_predictions,
    build_node_features,
    clamp_pillars_to_support,
    clamp_pillar_deltas,
    compute_ood_score,
    extrapolate_pillar_slopes,
    extrapolated_pillars_at_year,
    lag_support_bounds,
    load_edge_index_and_counties,
    load_forecast_model,
    load_lag_norm,
    pillar_delta_limits,
    pillar_support_bounds,
    score_temporal_limits,
)
from backend.pipeline.pillar_transform import (
    CONSTANTS as PT_CONST,
    load_frozen_transforms,
    raw_to_pillars,
)
from backend.pipeline.preprocessing import CONSTANTS as PRE_CONST

CONSTANTS: dict[str, Any] = {
    "PHASE": "A10",
    "DATA_DIR": Path(__file__).resolve().parents[1] / "data",
    "NORMALIZED_PANEL_FILENAME": "x_normalized.csv",
    "PILLAR_SCORES_FILENAME": "pillar_scores_augmented.csv",
    "FORECAST_SCORES_FILENAME": "forecast_2026_2036.csv",
    "SCENARIO_OUTPUT_FILENAME": "counterfactual_scenarios.csv",
    "REAL_VARIANT_ID": 0,
    "YEAR_2025": 2025,
    "CLIP_MIN": 0.0,
    "CLIP_MAX": 1.0,
    "PRESET_SCENARIOS": {
        "Monaghan_LowPerformer": {
            "county": "Monaghan",
            "interventions": {
                "recycled_cows_pct": 0.15,
                "calving_interval": -0.05,
                "cows_culled_pct": -0.05,
            },
        },
        "Kerry_LowPerformer": {
            "county": "Kerry",
            "interventions": {
                "recycled_cows_pct": 0.08,
                "calving_interval": -0.05,
                "cows_culled_pct": -0.02,
            },
        },
    },
}


def _print_header() -> None:
    """Print phase banner."""
    print("\n" + "=" * 72)
    print(f"[{CONSTANTS['PHASE']}] COUNTERFACTUAL SIMULATION")
    print("=" * 72)


def _county_normalized_row_2025(county: str) -> np.ndarray:
    """Load MinMax-normalized 2025 feature vector for one county."""
    path = CONSTANTS["DATA_DIR"] / CONSTANTS["NORMALIZED_PANEL_FILENAME"]
    df = pd.read_csv(path)
    row = df[(df["county"] == county) & (df["year"] == CONSTANTS["YEAR_2025"])]
    if len(row) != 1:
        raise ValueError(f"[A10] Expected one 2025 row for {county}, found {len(row)}")
    return row[PRE_CONST["FEATURE_COLS"]].to_numpy(dtype=np.float64).flatten()


def _apply_interventions(
    x_norm: np.ndarray,
    interventions: dict[str, float],
) -> np.ndarray:
    """Apply multiplicative deltas and clip to MinMax domain."""
    out = x_norm.copy()
    for feat, delta in interventions.items():
        if feat not in PRE_CONST["FEATURE_COLS"]:
            raise KeyError(f"[A10] Unknown feature: {feat}")
        idx = PRE_CONST["FEATURE_COLS"].index(feat)
        out[idx] = out[idx] * (1.0 + float(delta))
    return np.clip(out, CONSTANTS["CLIP_MIN"], CONSTANTS["CLIP_MAX"])


def _baseline_pillars_2025(county: str, pillars_df: pd.DataFrame) -> np.ndarray:
    """Read standardized pillars for real 2025."""
    row = pillars_df[
        (pillars_df["county"] == county)
        & (pillars_df["year"] == CONSTANTS["YEAR_2025"])
        & (pillars_df["variant_id"] == CONSTANTS["REAL_VARIANT_ID"])
    ]
    if len(row) != 1:
        raise ValueError(f"[A10] Missing baseline pillars for {county}")
    r = row.iloc[0]
    return np.array([float(r["P1"]), float(r["P2"]), float(r["P3"]), float(r["P4"])], dtype=np.float64)


def _load_baseline_forecast_scores() -> dict[tuple[str, int], float]:
    """Load deterministic A8 scores for baseline trajectory."""
    path = CONSTANTS["DATA_DIR"] / CONSTANTS["FORECAST_SCORES_FILENAME"]
    if not path.exists():
        raise FileNotFoundError(f"[A10] Run A8 first; missing {path}")
    df = pd.read_csv(path)
    out: dict[tuple[str, int], float] = {}
    for _, row in df.iterrows():
        out[(str(row["county"]), int(row["year"]))] = float(row["predicted_score"])
    return out


def _score_trend_fallback(scores_real: pd.DataFrame, counties: list[str], year: int) -> np.ndarray:
    """Compute bounded county score trend fallback for invalid scenario outputs."""
    years = np.array(forecast_mod.CONSTANTS["HISTORICAL_YEARS_FOR_TREND"], dtype=np.float64)
    fallback = np.zeros(forecast_mod.CONSTANTS["EXPECTED_NODES"], dtype=np.float64)
    for idx, county in enumerate(counties):
        series = np.array(
            [
                float(scores_real[(scores_real["county"] == county) & (scores_real["year"] == y)]["score"].iloc[0])
                for y in forecast_mod.CONSTANTS["HISTORICAL_YEARS_FOR_TREND"]
            ],
            dtype=np.float64,
        )
        slope, intercept = np.polyfit(years, series, deg=1)
        fallback[idx] = (slope * float(year)) + intercept
    return np.clip(
        fallback,
        forecast_mod.CONSTANTS["SCORE_MIN"],
        forecast_mod.CONSTANTS["SCORE_MAX"],
    )


def simulate_counterfactual(
    county: str,
    interventions: dict[str, float],
    horizon: int = 11,
) -> dict[str, Any]:
    """Run raw delta -> frozen pillar recompute -> persistent pillar shift -> STGNN AR forecast."""
    forecast_years = forecast_mod.CONSTANTS["FORECAST_YEARS"]
    if horizon != len(forecast_years):
        horizon = len(forecast_years)
    device = torch.device("cpu")
    frozen = load_frozen_transforms()
    y_bar, sigma_y = load_lag_norm()
    target_mean, target_std = forecast_mod.load_target_scaler()
    edge_index, counties = load_edge_index_and_counties()
    edge_index = edge_index.to(device)
    model = load_forecast_model(device)

    if county not in counties:
        raise ValueError(f"[A10] Unknown county: {county}")
    county_idx = counties.index(county)

    x_base = _county_normalized_row_2025(county)
    x_tilde = _apply_interventions(x_base, interventions)
    s_tilde = raw_to_pillars(x_tilde, frozen)
    pillars_df = pd.read_csv(CONSTANTS["DATA_DIR"] / CONSTANTS["PILLAR_SCORES_FILENAME"])
    s_base = _baseline_pillars_2025(county, pillars_df)
    pillar_shift = s_tilde - s_base
    pillar_shifts = {f"P{k + 1}_delta": float(pillar_shift[k]) for k in range(PT_CONST["N_PILLARS"])}

    scores_real = pd.read_csv(CONSTANTS["DATA_DIR"] / "sustainability_scores.csv")
    exp_n = forecast_mod.CONSTANTS["EXPECTED_NODES"]
    n_pil = forecast_mod.CONSTANTS["N_PILLARS"]
    slopes, intercepts = extrapolate_pillar_slopes(pillars_df, counties)
    pillar_lower, pillar_upper = pillar_support_bounds(pillars_df)
    pillar_delta_limit = pillar_delta_limits(pillars_df, counties)
    lag_bounds = lag_support_bounds(scores_real, counties, y_bar, sigma_y)
    velocity_limit, accel_limit = score_temporal_limits(scores_real, counties)
    pillar_prev = np.zeros((exp_n, n_pil), dtype=np.float64)
    sub_2025 = pillars_df[
        (pillars_df["variant_id"] == CONSTANTS["REAL_VARIANT_ID"])
        & (pillars_df["year"] == CONSTANTS["YEAR_2025"])
    ].set_index("county")
    for i, cty in enumerate(counties):
        r = sub_2025.loc[cty]
        pillar_prev[i, :] = [float(r["P1"]), float(r["P2"]), float(r["P3"]), float(r["P4"])]
    baseline_scores = _load_baseline_forecast_scores()

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

    window_tensors: list[Tensor] = []
    for wy in forecast_mod.CONSTANTS["WINDOW_INPUT_YEARS"]:
        p_mat = np.zeros((exp_n, n_pil), dtype=np.float64)
        sub = pillars_df[
            (pillars_df["variant_id"] == CONSTANTS["REAL_VARIANT_ID"]) & (pillars_df["year"] == wy)
        ].set_index("county")
        for i, cty in enumerate(counties):
            r = sub.loc[cty]
            p_mat[i, :] = [float(r["P1"]), float(r["P2"]), float(r["P3"]), float(r["P4"])]
        prev_vec = prev_scores_by_year[wy - 1]
        window_tensors.append(build_node_features(p_mat, prev_vec, wy, y_bar, sigma_y, lag_bounds).to(device))

    scenario_last = prev_scores_by_year[2025].copy()
    scenario_last_delta = np.zeros_like(scenario_last)
    baseline_trajectory: list[dict[str, Any]] = []
    scenario_trajectory: list[dict[str, Any]] = []
    uplift_trajectory: list[dict[str, Any]] = []

    forecast_years_slice = forecast_years[:horizon]
    for fy in forecast_years_slice:
        p_baseline = clamp_pillars_to_support(
            extrapolated_pillars_at_year(slopes, intercepts, fy),
            pillar_lower,
            pillar_upper,
        )
        p_baseline = clamp_pillar_deltas(p_baseline, pillar_prev, pillar_delta_limit)
        p_baseline = clamp_pillars_to_support(p_baseline, pillar_lower, pillar_upper)
        p_use = p_baseline.copy()
        p_use[county_idx, :] = p_baseline[county_idx, :] + pillar_shift
        p_use = clamp_pillars_to_support(p_use, pillar_lower, pillar_upper)

        prev_vec = np.zeros(exp_n, dtype=np.float64)
        for i, cty in enumerate(counties):
            if fy == forecast_years[0]:
                prev_vec[i] = prev_scores_by_year[2025][i]
            else:
                if i == county_idx:
                    prev_vec[i] = scenario_last[i]
                else:
                    prev_vec[i] = baseline_scores[(cty, fy - 1)]

        lag_z = (prev_vec - y_bar) / max(sigma_y, forecast_mod.CONSTANTS["EPSILON"])
        lag_z = np.clip(lag_z, lag_bounds[0], lag_bounds[1])
        x_fy = build_node_features(p_use, prev_vec, fy, y_bar, sigma_y, lag_bounds).to(device)
        seq = torch.stack(window_tensors, dim=0)
        with torch.no_grad():
            y_hat_scaled = model(seq, edge_index).cpu().numpy()
        y_hat_raw = (y_hat_scaled * max(target_std, forecast_mod.CONSTANTS["EPSILON"])) + target_mean
        fallback_scores = _score_trend_fallback(scores_real, counties, fy)
        ood_scores = compute_ood_score(
            pillars=p_use,
            lag_z=lag_z,
            raw_scores=y_hat_raw,
            pillar_lower=pillar_lower,
            pillar_upper=pillar_upper,
            target_mean=target_mean,
            target_std=target_std,
        )
        y_blend, _ = adaptive_blend_with_fallback(y_hat_raw, fallback_scores, ood_scores)
        y_limited = apply_temporal_rate_limits(
            y_blend,
            scenario_last,
            scenario_last_delta,
            velocity_limit,
            accel_limit,
        )
        invalid_mask = (
            ~np.isfinite(y_limited)
            | (y_limited < forecast_mod.CONSTANTS["SCORE_MIN"])
            | (y_limited > forecast_mod.CONSTANTS["SCORE_MAX"])
        )
        y_safe, _, _ = apply_fail_safe_policy(y_limited, fallback_scores, ood_scores, invalid_mask)
        y_hat, _ = bounded_score_predictions(y_safe, fallback_scores)

        base_y = baseline_scores[(county, fy)]
        scen_y = float(y_hat[county_idx])
        baseline_trajectory.append({"year": fy, "score": base_y})
        scenario_trajectory.append({"year": fy, "score": round(scen_y, 1)})
        uplift_trajectory.append({"year": fy, "delta": round(scen_y - base_y, 1)})
        scenario_last = scenario_last.copy()
        scenario_last_delta = y_hat - scenario_last
        scenario_last[county_idx] = scen_y
        pillar_prev = p_baseline.copy()
        window_tensors = [window_tensors[1], window_tensors[2], window_tensors[3], x_fy]

    uplift_final = uplift_trajectory[-1]["delta"]
    final_year = int(forecast_years_slice[-1])
    return {
        "county": county,
        "interventions": interventions,
        "pillar_shifts": pillar_shifts,
        "baseline": baseline_trajectory,
        "counterfactual": scenario_trajectory,
        "uplift": uplift_trajectory,
        "uplift_final_year": uplift_final,
        "final_year": final_year,
        "metadata": {"horizon": list(forecast_years_slice), "model": "stgnn_forecast_weights.pt"},
    }


def run_counterfactual() -> None:
    """Execute preset Monaghan and Kerry scenarios and save CSV summary."""
    _print_header()
    rows: list[dict[str, Any]] = []
    for scenario_name, spec in CONSTANTS["PRESET_SCENARIOS"].items():
        cty = spec["county"]
        result = simulate_counterfactual(cty, spec["interventions"])
        shift = result["pillar_shifts"]
        print(
            f"[A10] Scenario {scenario_name}: pillar_shift P1..P4="
            f"[{shift['P1_delta']:.4f}, {shift['P2_delta']:.4f}, {shift['P3_delta']:.4f}, {shift['P4_delta']:.4f}], "
            f"uplift_{result['final_year']}={result['uplift_final_year']:+.2f}"
        )
        for b, s, u in zip(result["baseline"], result["counterfactual"], result["uplift"], strict=True):
            rows.append(
                {
                    "scenario_name": scenario_name,
                    "county": cty,
                    "year": b["year"],
                    "baseline_score": b["score"],
                    "counterfactual_score": s["score"],
                    "uplift": u["delta"],
                    "P1_shift": shift["P1_delta"],
                    "P2_shift": shift["P2_delta"],
                    "P3_shift": shift["P3_delta"],
                    "P4_shift": shift["P4_delta"],
                }
            )

    out_path = CONSTANTS["DATA_DIR"] / CONSTANTS["SCENARIO_OUTPUT_FILENAME"]
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"[A10] Saved scenarios: {out_path}")
