"""Phase A9 Monte Carlo uncertainty bands on forecast scores."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

CONSTANTS: dict[str, Any] = {
    "PHASE": "A9",
    "DATA_DIR": Path(__file__).resolve().parents[1] / "data",
    "FORECAST_SCORES_FILENAME": "forecast_2026_2036.csv",
    "UNCERTAINTY_OUTPUT_FILENAME": "uncertainty_bands.csv",
    "MONTE_CARLO_TRIALS": 100,
    "SIGMA_MC": 0.1,
    "LOWER_PCT": 5.0,
    "UPPER_PCT": 95.0,
    "SEED": 42,
}


def _print_header() -> None:
    """Print phase banner."""
    print("\n" + "=" * 72)
    print(f"[{CONSTANTS['PHASE']}] MONTE CARLO UNCERTAINTY")
    print("=" * 72)


def run_uncertainty() -> None:
    """Run Phase A9: add Gaussian noise in score space and save percentile bands."""
    _print_header()
    forecast_path = CONSTANTS["DATA_DIR"] / CONSTANTS["FORECAST_SCORES_FILENAME"]
    if not forecast_path.exists():
        raise FileNotFoundError(f"[A9] Run A8 first; missing {forecast_path}")
    baseline_df = pd.read_csv(forecast_path)
    rng = np.random.default_rng(CONSTANTS["SEED"])

    rows_out: list[dict[str, Any]] = []
    half_widths: list[float] = []

    for _, row in baseline_df.iterrows():
        base = float(row["predicted_score"])
        samples = base + rng.normal(0.0, CONSTANTS["SIGMA_MC"], size=CONSTANTS["MONTE_CARLO_TRIALS"])
        mean_val = float(np.mean(samples))
        lower = float(np.percentile(samples, CONSTANTS["LOWER_PCT"]))
        upper = float(np.percentile(samples, CONSTANTS["UPPER_PCT"]))
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

    print(f"[A9] Uncertainty saved: trials={CONSTANTS['MONTE_CARLO_TRIALS']}, sigma_MC={CONSTANTS['SIGMA_MC']}")
    print(f"[A9] Output: {out_path}, rows={len(out_df)}")
    print(f"[A9] Mean half-width (95-5)/2 over all cells: {float(np.mean(half_widths)):.4f}")
    for y in sorted(out_df["year"].unique()):
        sub = out_df[out_df["year"] == y]
        hw = float(((sub["upper_95pct"] - sub["lower_5pct"]) / 2.0).mean())
        print(f"[A9] Year {y}: avg_half_width={hw:.4f}, n={len(sub)}")
