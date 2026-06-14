"""Phase A9 Monte Carlo uncertainty bands on derived forecast scores."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.pipeline.pillar_transform import load_frozen_transforms, pillar_matrix_to_scores

CONSTANTS: dict[str, Any] = {
    "PHASE": "A9",
    "DATA_DIR": Path(__file__).resolve().parents[1] / "data",
    "ARTIFACTS_DIR": Path(__file__).resolve().parents[1] / "artifacts",
    "FORECAST_SCORES_FILENAME": "forecast_2026_2036.csv",
    "FORECAST_PILLARS_FILENAME": "forecast_pillars_2026_2036.csv",
    "PILLAR_TARGET_SCALER_FILENAME": "stgnn_pillar_target_scaler.pkl",
    "UNCERTAINTY_OUTPUT_FILENAME": "uncertainty_bands.csv",
    "MONTE_CARLO_TRIALS": 100,
    "SIGMA_PILLAR_MC": 0.05,
    "LOWER_PCT": 5.0,
    "UPPER_PCT": 95.0,
    "SCORE_MIN": 0.0,
    "SCORE_MAX": 100.0,
    "N_PILLARS": 4,
    "SEED": 42,
}


def _print_header() -> None:
    """Print phase banner."""
    print("\n" + "=" * 72)
    print(f"[{CONSTANTS['PHASE']}] MONTE CARLO UNCERTAINTY")
    print("=" * 72)


def _load_pillar_sigma() -> np.ndarray:
    """Load per-pillar target std as MC noise scale."""
    path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["PILLAR_TARGET_SCALER_FILENAME"]
    with path.open("rb") as file:
        payload = pickle.load(file)
    target_std = np.asarray(payload["target_std"], dtype=np.float64)
    return np.maximum(target_std * CONSTANTS["SIGMA_PILLAR_MC"], 0.01)


def run_uncertainty() -> None:
    """Run Phase A9: perturb pillars, derive score bands, save percentile bands."""
    _print_header()
    forecast_path = CONSTANTS["DATA_DIR"] / CONSTANTS["FORECAST_SCORES_FILENAME"]
    pillar_path = CONSTANTS["DATA_DIR"] / CONSTANTS["FORECAST_PILLARS_FILENAME"]
    if not forecast_path.exists():
        raise FileNotFoundError(f"[A9] Run A8 first; missing {forecast_path}")
    if not pillar_path.exists():
        raise FileNotFoundError(f"[A9] Run A8 first; missing {pillar_path}")
    baseline_df = pd.read_csv(forecast_path)
    pillars_df = pd.read_csv(pillar_path)
    merged = baseline_df.merge(pillars_df, on=["county", "year"], how="inner")
    frozen = load_frozen_transforms()
    pillar_sigma = _load_pillar_sigma()
    rng = np.random.default_rng(CONSTANTS["SEED"])

    rows_out: list[dict[str, Any]] = []
    half_widths: list[float] = []

    for _, row in merged.iterrows():
        base_pillars = np.array(
            [float(row["P1"]), float(row["P2"]), float(row["P3"]), float(row["P4"])],
            dtype=np.float64,
        )
        score_samples = np.zeros(CONSTANTS["MONTE_CARLO_TRIALS"], dtype=np.float64)
        for trial in range(CONSTANTS["MONTE_CARLO_TRIALS"]):
            noise = rng.normal(0.0, pillar_sigma, size=CONSTANTS["N_PILLARS"])
            perturbed = base_pillars + noise
            score_samples[trial] = pillar_matrix_to_scores(perturbed.reshape(1, -1), frozen)[0]
        score_samples = np.clip(score_samples, CONSTANTS["SCORE_MIN"], CONSTANTS["SCORE_MAX"])
        mean_val = float(np.mean(score_samples))
        lower = float(np.percentile(score_samples, CONSTANTS["LOWER_PCT"]))
        upper = float(np.percentile(score_samples, CONSTANTS["UPPER_PCT"]))
        half_widths.append((upper - lower) / 2.0)
        rows_out.append(
            {
                "county": row["county"],
                "year": int(row["year"]),
                "mean": round(mean_val, 1),
                "lower_5pct": round(lower, 1),
                "upper_95pct": round(upper, 1),
            }
        )

    out_df = pd.DataFrame(rows_out)
    out_path = CONSTANTS["DATA_DIR"] / CONSTANTS["UNCERTAINTY_OUTPUT_FILENAME"]
    out_df.to_csv(out_path, index=False)

    print(
        f"[A9] Uncertainty saved: trials={CONSTANTS['MONTE_CARLO_TRIALS']}, "
        f"sigma_pillar_mc={CONSTANTS['SIGMA_PILLAR_MC']}"
    )
    print(f"[A9] Output: {out_path}, rows={len(out_df)}")
    print(f"[A9] Mean half-width (95-5)/2 over all cells: {float(np.mean(half_widths)):.4f}")
