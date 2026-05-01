"""Application startup state loading and in-memory cache."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from backend.pipeline.pillar_transform import load_frozen_transforms

CONSTANTS: dict[str, Any] = {
    "BACKEND_DIR": Path(__file__).resolve().parents[1],
    "DATA_DIR": Path(__file__).resolve().parents[1] / "data",
    "ARTIFACTS_DIR": Path(__file__).resolve().parents[1] / "artifacts",
    "HISTORICAL_FILENAME": "sustainability_scores.csv",
    "FORECAST_FILENAME": "forecast_2026_2036.csv",
    "UNCERTAINTY_FILENAME": "uncertainty_bands.csv",
    "PILLARS_AUGMENTED_FILENAME": "pillar_scores_augmented.csv",
    "PILLARS_FORECAST_FILENAME": "forecast_pillars_2026_2036.csv",
    "X_NORMALIZED_FILENAME": "x_normalized.csv",
    "METRICS_FILENAME": "stgnn_metrics.json",
    "PILLAR_KEYS_DEFAULT": [
        "reproductive_efficiency",
        "genetic_management",
        "herd_health",
        "herd_management",
    ],
}


@dataclass(slots=True)
class AppState:
    """Container for startup-loaded API artifacts and tables."""

    frozen: dict[str, Any]
    counties: list[str]
    historical_scores: pd.DataFrame
    forecast_scores: pd.DataFrame
    uncertainty: pd.DataFrame
    pillars_augmented: pd.DataFrame
    pillars_forecast: pd.DataFrame
    x_normalized: pd.DataFrame
    metrics: dict[str, Any]
    pillar_label_keys: dict[str, str]


def _slugify(value: str) -> str:
    """Convert a human-readable label to a stable API key slug."""
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return slug.strip("_")


def _pillar_label_keys_from_frozen(frozen: dict[str, Any]) -> dict[str, str]:
    """Build P1..P4 API key mapping from artifact labels with safe fallback."""
    fallback = {f"P{index + 1}": key for index, key in enumerate(CONSTANTS["PILLAR_KEYS_DEFAULT"])}
    labels = frozen.get("pillar_weights", {}).get("pillar_labels", {})
    candidate: dict[str, str] = {}
    used: set[str] = set()
    for index in range(4):
        raw_label = labels.get(index + 1)
        if not isinstance(raw_label, str):
            return fallback
        slug = _slugify(raw_label)
        if not slug or slug in used:
            return fallback
        used.add(slug)
        candidate[f"P{index + 1}"] = slug
    return candidate


def load_state() -> AppState:
    """Load frozen artifacts and cached CSVs once at API startup."""
    frozen = load_frozen_transforms()
    data_dir = CONSTANTS["DATA_DIR"]
    artifacts_dir = CONSTANTS["ARTIFACTS_DIR"]

    historical_scores = pd.read_csv(data_dir / CONSTANTS["HISTORICAL_FILENAME"])
    forecast_scores = pd.read_csv(data_dir / CONSTANTS["FORECAST_FILENAME"])
    uncertainty = pd.read_csv(data_dir / CONSTANTS["UNCERTAINTY_FILENAME"])
    pillars_augmented = pd.read_csv(data_dir / CONSTANTS["PILLARS_AUGMENTED_FILENAME"])
    pillars_forecast = pd.read_csv(data_dir / CONSTANTS["PILLARS_FORECAST_FILENAME"])
    x_normalized = pd.read_csv(data_dir / CONSTANTS["X_NORMALIZED_FILENAME"])

    pillars_augmented = pillars_augmented[pillars_augmented["variant_id"] == 0].copy()
    counties = list(frozen["counties"])
    with (artifacts_dir / CONSTANTS["METRICS_FILENAME"]).open("r", encoding="utf-8") as file:
        metrics = json.load(file)

    state = AppState(
        frozen=frozen,
        counties=counties,
        historical_scores=historical_scores,
        forecast_scores=forecast_scores,
        uncertainty=uncertainty,
        pillars_augmented=pillars_augmented,
        pillars_forecast=pillars_forecast,
        x_normalized=x_normalized,
        metrics=metrics,
        pillar_label_keys=_pillar_label_keys_from_frozen(frozen),
    )
    print(f"[API] Loaded counties={len(state.counties)}")
    print(
        f"[API] Historical rows={len(state.historical_scores)}, "
        f"Forecast rows={len(state.forecast_scores)}"
    )
    print(
        f"[API] Metrics found: train={state.metrics.get('training_r2_mean')}, "
        f"val={state.metrics.get('validation_r2_mean')}, test_r2={state.metrics.get('test_r2')}"
    )
    return state

