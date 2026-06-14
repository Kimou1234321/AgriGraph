"""Frozen pillar transform chain for API and counterfactual recomputation."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.preprocessing import StandardScaler

CONSTANTS: dict[str, Any] = {
    "MODULE": "pillar_transform",
    "ARTIFACTS_DIR": Path(__file__).resolve().parents[1] / "artifacts",
    "STANDARD_SCALER_FILENAME": "standard_scaler.pkl",
    "PCA_LOADINGS_FILENAME": "pca_loadings.npy",
    "PILLAR_WEIGHTS_FILENAME": "pillar_weights.pkl",
    "SCORE_PARAMS_FILENAME": "score_params.pkl",
    "EDGE_INDEX_FILENAME": "edge_index.pt",
    "COUNTIES_FILENAME": "graph_counties.pkl",
    "N_PILLARS": 4,
    "EPSILON": 1e-8,
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


def load_frozen_transforms() -> dict[str, Any]:
    """Load all frozen artifacts needed for on-the-fly pillar and score computation."""
    base = CONSTANTS["ARTIFACTS_DIR"]
    with (base / CONSTANTS["STANDARD_SCALER_FILENAME"]).open("rb") as file:
        standard_scaler = pickle.load(file)
    pca_loadings = np.load(base / CONSTANTS["PCA_LOADINGS_FILENAME"])
    with (base / CONSTANTS["PILLAR_WEIGHTS_FILENAME"]).open("rb") as file:
        pillar_weights = pickle.load(file)
    with (base / CONSTANTS["SCORE_PARAMS_FILENAME"]).open("rb") as file:
        score_params = pickle.load(file)
    edge_index = torch.load(base / CONSTANTS["EDGE_INDEX_FILENAME"], map_location="cpu")
    if not isinstance(edge_index, torch.Tensor):
        edge_index = torch.as_tensor(edge_index)
    with (base / CONSTANTS["COUNTIES_FILENAME"]).open("rb") as file:
        counties = pickle.load(file)
    return {
        "standard_scaler": standard_scaler,
        "pca_loadings": pca_loadings,
        "pillar_weights": pillar_weights,
        "score_params": score_params,
        "edge_index": edge_index.long(),
        "counties": list(counties),
    }


def raw_to_pillars(x_norm_row: np.ndarray, frozen: dict[str, Any]) -> np.ndarray:
    """Map MinMax-normalized raw features to four standardized pillar scores S_k."""
    if x_norm_row.shape != (len(CONSTANTS["FEATURE_COLS"]),):
        raise ValueError(
            f"Expected x_norm_row shape ({len(CONSTANTS['FEATURE_COLS'])},), got {x_norm_row.shape}"
        )
    scaler = frozen["standard_scaler"]
    pillar_weights = frozen["pillar_weights"]
    score_params = frozen["score_params"]
    x_row = x_norm_row.reshape(1, -1)
    x_sc = scaler.transform(x_row).astype(np.float64).flatten()
    raw_p = np.zeros(CONSTANTS["N_PILLARS"], dtype=np.float64)
    for k in range(CONSTANTS["N_PILLARS"]):
        key = k + 1
        indices = pillar_weights["J_k_indices"][key]
        weights = np.asarray(pillar_weights["w_jk"][key], dtype=np.float64)
        raw_p[k] = float(x_sc[indices] @ weights)
    p_bar = np.asarray(score_params["P_bar_k"], dtype=np.float64)
    sigma_p = np.asarray(score_params["sigma_P_k"], dtype=np.float64)
    sigma_p = np.where(sigma_p <= CONSTANTS["EPSILON"], 1.0, sigma_p)
    standardized = (raw_p - p_bar) / sigma_p
    return standardized


def _score_params_from_frozen(frozen: dict[str, Any]) -> tuple[float, float, float, float, float, int]:
    """Extract min-max score calibration constants from frozen artifacts."""
    params = frozen["score_params"]
    i_min = float(params["I_min"])
    i_max = float(params["I_max"])
    score_min = float(params.get("SCORE_MIN", 0.0))
    score_max = float(params.get("SCORE_MAX", 100.0))
    fallback = float(params.get("SCORE_FALLBACK", 50.0))
    round_decimals = int(params.get("SCORE_ROUND_DECIMALS", 1))
    return i_min, i_max, score_min, score_max, fallback, round_decimals


def pillars_to_score(
    s_row: np.ndarray,
    frozen: dict[str, Any],
) -> float:
    """Map standardized pillar vector to rescaled sustainability score I* in [0, 100]."""
    scores = pillar_matrix_to_scores(s_row.reshape(1, -1), frozen)
    return float(scores[0])


def pillar_matrix_to_scores(
    pillar_matrix: np.ndarray,
    frozen: dict[str, Any],
) -> np.ndarray:
    """Derive sustainability scores from pillar matrix using simple average and min-max scaling."""
    pillars = np.asarray(pillar_matrix, dtype=np.float64)
    if pillars.ndim == 1:
        pillars = pillars.reshape(1, -1)
    if pillars.shape[1] != CONSTANTS["N_PILLARS"]:
        raise ValueError(f"Expected {CONSTANTS['N_PILLARS']} pillars, got {pillars.shape[1]}")
    i_min, i_max, score_min, score_max, fallback, round_decimals = _score_params_from_frozen(frozen)
    index_values = pillars.mean(axis=1)
    if abs(i_max - i_min) <= CONSTANTS["EPSILON"]:
        scores = np.full(pillars.shape[0], fallback, dtype=np.float64)
    else:
        scores = score_max * (index_values - i_min) / (i_max - i_min)
        scores = np.clip(scores, score_min, score_max)
    return np.round(scores, round_decimals)
