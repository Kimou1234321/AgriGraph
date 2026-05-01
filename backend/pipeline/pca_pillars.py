"""Phases A4-A5 PCA pillar extraction and sustainability scoring."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

CONSTANTS: dict[str, Any] = {
    "PHASE": "A4_A5",
    "DATA_DIR": Path(__file__).resolve().parents[1] / "data",
    "ARTIFACTS_DIR": Path(__file__).resolve().parents[1] / "artifacts",
    "AUGMENTED_INPUT_FILENAME": "x_augmented.csv",
    "PILLAR_OUTPUT_FILENAME": "pillar_scores_augmented.csv",
    "REAL_SCORE_OUTPUT_FILENAME": "sustainability_scores.csv",
    "AUGMENTED_SCORE_OUTPUT_FILENAME": "sustainability_scores_augmented.csv",
    "STANDARD_SCALER_FILENAME": "standard_scaler.pkl",
    "PCA_LOADINGS_FILENAME": "pca_loadings.npy",
    "PILLAR_WEIGHTS_FILENAME": "pillar_weights.pkl",
    "SCORE_PARAMS_FILENAME": "score_params.pkl",
    "N_COMPONENTS_FULL": 17,
    "N_COMPONENTS_RETAINED": 4,
    "DOMINANT_PERCENTILE": 75,
    "REAL_VARIANT_ID": 0,
    "SCORE_MIN": 0.0,
    "SCORE_MAX": 100.0,
    "SCORE_ROUND_DECIMALS": 1,
    "EPSILON": 1e-8,
    "NEGATIVE_POLARITY_FEATURES": {
        "calving_interval",
        "females_not_calved_pct",
        "cows_culled_pct",
        "mortality_dead_at_birth",
        "mortality_dead_28days",
    },
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
    "PILLAR_REFERENCE_FEATURES": {
        "Reproductive Efficiency": {
            "recycled_cows_pct",
            "calving_interval",
            "calves_per_cow_per_year",
            "females_not_calved_pct",
            "heifers_calved_22_26mo",
        },
        "Genetic Management": {
            "births_calving_survey_pct",
            "replacements_dairy_ai_pct",
            "births_known_sire_pct",
            "current_replacement_rate",
            "potential_replacement_rate",
        },
        "Herd Health": {
            "cows_culled_pct",
            "mortality_dead_at_birth",
            "potential_replacement_rate",
            "births_known_sire_pct",
            "mortality_dead_28days",
        },
        "Herd Management": {
            "cows_culled_pct",
            "potential_replacement_rate",
            "current_replacement_rate",
            "replacements_dairy_ai_pct",
            "births_known_sire_pct",
        },
    },
}


def _print_phase_header() -> None:
    """Print a readable phase header."""
    print("\n" + "=" * 72)
    print("[A4-A5] PCA PILLARS + COMPOSITE SCORING")
    print("=" * 72)


def _load_augmented_input() -> pd.DataFrame:
    """Load the Phase A3 augmented feature matrix."""
    input_path = CONSTANTS["DATA_DIR"] / CONSTANTS["AUGMENTED_INPUT_FILENAME"]
    print(f"[A4-A5] Loading augmented input from: {input_path}")
    if not input_path.exists():
        raise FileNotFoundError(f"[A4-A5] Missing required A3 output: {input_path}")
    dataframe = pd.read_csv(input_path)
    required_columns = ["county", "year", "variant_id", *CONSTANTS["FEATURE_COLS"]]
    missing_columns = [col for col in required_columns if col not in dataframe.columns]
    if missing_columns:
        raise ValueError(f"[A4-A5] Missing augmented columns: {missing_columns}")
    if len(dataframe) != 650:
        raise ValueError(f"[A4-A5] Expected 650 augmented rows, found {len(dataframe)}.")
    return dataframe.sort_values(["county", "year", "variant_id"]).reset_index(drop=True)


def _fit_standard_scaler_and_transform(df: pd.DataFrame) -> tuple[StandardScaler, np.ndarray]:
    """Fit StandardScaler on all augmented rows and transform features."""
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(df[CONSTANTS["FEATURE_COLS"]].to_numpy())
    print(f"[A4-A5] Standardized augmented matrix shape: {x_scaled.shape}")
    return scaler, x_scaled


def _fit_pca(x_scaled: np.ndarray) -> tuple[PCA, np.ndarray, np.ndarray, np.ndarray]:
    """Fit full PCA and return loadings plus retained variance ratios."""
    pca = PCA(n_components=CONSTANTS["N_COMPONENTS_FULL"])
    pca.fit(x_scaled)
    eigenvalues = pca.explained_variance_
    variance_ratios = pca.explained_variance_ratio_[: CONSTANTS["N_COMPONENTS_RETAINED"]]
    loadings = pca.components_[: CONSTANTS["N_COMPONENTS_RETAINED"], :].T
    print("[A4-A5] Retained variance ratios (rho_k):", np.round(variance_ratios, 6).tolist())
    print("[A4-A5] Sum retained variance:", float(np.sum(variance_ratios)))
    return pca, loadings, eigenvalues, variance_ratios


def _dominant_feature_indices(loadings: np.ndarray) -> dict[int, list[int]]:
    """Select dominant features per component by 75th percentile of |loading|."""
    dominant_map: dict[int, list[int]] = {}
    for component_index in range(CONSTANTS["N_COMPONENTS_RETAINED"]):
        component_abs = np.abs(loadings[:, component_index])
        threshold = float(np.percentile(component_abs, CONSTANTS["DOMINANT_PERCENTILE"]))
        indices = [idx for idx, value in enumerate(component_abs) if value >= threshold]
        dominant_map[component_index] = indices
    return dominant_map


def _match_pillar_label(dominant_features: set[str]) -> str:
    """Assign the closest reference pillar label by overlap score."""
    best_label = "Unassigned Pillar"
    best_overlap = -1
    for label, reference_features in CONSTANTS["PILLAR_REFERENCE_FEATURES"].items():
        overlap = len(dominant_features.intersection(reference_features))
        if overlap > best_overlap:
            best_overlap = overlap
            best_label = label
    return best_label


def _compute_sign_calibration(loadings: np.ndarray, dominant_map: dict[int, list[int]]) -> np.ndarray:
    """Calibrate component sign so higher scores reflect better sustainability."""
    signs = np.ones(CONSTANTS["N_COMPONENTS_RETAINED"], dtype=np.float64)
    for component_index in range(CONSTANTS["N_COMPONENTS_RETAINED"]):
        weighted_polarity = 0.0
        for feature_index in dominant_map[component_index]:
            feature_name = CONSTANTS["FEATURE_COLS"][feature_index]
            loading_value = loadings[feature_index, component_index]
            polarity = -1.0 if feature_name in CONSTANTS["NEGATIVE_POLARITY_FEATURES"] else 1.0
            weighted_polarity += polarity * loading_value
        signs[component_index] = 1.0 if weighted_polarity >= 0.0 else -1.0
    return signs


def _compute_within_pillar_weights(
    calibrated_loadings: np.ndarray,
    dominant_map: dict[int, list[int]],
) -> tuple[dict[int, np.ndarray], dict[int, list[int]]]:
    """Compute non-negative within-pillar weights from calibrated loadings."""
    weights_map: dict[int, np.ndarray] = {}
    dominant_indices_map: dict[int, list[int]] = {}
    for component_index in range(CONSTANTS["N_COMPONENTS_RETAINED"]):
        dominant_indices = dominant_map[component_index]
        dominant_indices_map[component_index] = dominant_indices
        magnitudes = np.abs(calibrated_loadings[dominant_indices, component_index])
        denom = float(np.sum(magnitudes))
        if denom <= CONSTANTS["EPSILON"]:
            weights = np.ones_like(magnitudes) / len(magnitudes)
        else:
            weights = magnitudes / denom
        weights_map[component_index] = weights
    return weights_map, dominant_indices_map


def _compute_raw_and_standardized_pillars(
    x_scaled: np.ndarray,
    weights_map: dict[int, np.ndarray],
    dominant_indices_map: dict[int, list[int]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute raw pillar scores P and standardized pillar scores S."""
    raw_pillars = np.zeros((x_scaled.shape[0], CONSTANTS["N_COMPONENTS_RETAINED"]), dtype=np.float64)
    for component_index in range(CONSTANTS["N_COMPONENTS_RETAINED"]):
        feature_indices = dominant_indices_map[component_index]
        weights = weights_map[component_index]
        raw_pillars[:, component_index] = x_scaled[:, feature_indices] @ weights

    means = raw_pillars.mean(axis=0)
    stds = raw_pillars.std(axis=0)
    stds = np.where(stds <= CONSTANTS["EPSILON"], 1.0, stds)
    standardized_pillars = (raw_pillars - means) / stds
    return raw_pillars, standardized_pillars, means, stds


def _compute_alpha_weights(variance_ratios: np.ndarray) -> np.ndarray:
    """Compute variance-weighted pillar aggregation coefficients alpha_k."""
    retained_sum = float(np.sum(variance_ratios))
    if retained_sum <= CONSTANTS["EPSILON"]:
        raise ValueError("[A4-A5] Invalid retained variance sum for alpha computation.")
    alpha = variance_ratios / retained_sum
    print("[A4-A5] Variance-weighted alpha_k:", np.round(alpha, 6).tolist())
    return alpha


def _compute_scaled_scores(standardized_pillars: np.ndarray, alpha: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Compute composite index and rescale to SCORE_MIN..SCORE_MAX."""
    index_values = standardized_pillars @ alpha
    index_min = float(np.min(index_values))
    index_max = float(np.max(index_values))
    denom = max(index_max - index_min, CONSTANTS["EPSILON"])
    score_values = CONSTANTS["SCORE_MIN"] + (
        (CONSTANTS["SCORE_MAX"] - CONSTANTS["SCORE_MIN"]) * (index_values - index_min) / denom
    )
    score_values = np.round(score_values, CONSTANTS["SCORE_ROUND_DECIMALS"])
    return score_values, index_min, index_max


def _save_artifacts(
    scaler: StandardScaler,
    calibrated_loadings: np.ndarray,
    signs: np.ndarray,
    weights_map: dict[int, np.ndarray],
    dominant_indices_map: dict[int, list[int]],
    pillar_labels: dict[int, str],
    means: np.ndarray,
    stds: np.ndarray,
    alpha: np.ndarray,
    index_min: float,
    index_max: float,
) -> None:
    """Persist A4-A5 frozen artifacts for downstream phases and API usage."""
    CONSTANTS["ARTIFACTS_DIR"].mkdir(parents=True, exist_ok=True)

    standard_scaler_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["STANDARD_SCALER_FILENAME"]
    pca_loadings_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["PCA_LOADINGS_FILENAME"]
    pillar_weights_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["PILLAR_WEIGHTS_FILENAME"]
    score_params_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["SCORE_PARAMS_FILENAME"]

    with standard_scaler_path.open("wb") as file:
        pickle.dump(scaler, file)
    np.save(pca_loadings_path, calibrated_loadings)

    pillar_weights_payload = {
        "w_jk": {k + 1: weights_map[k].tolist() for k in weights_map},
        "J_k": {k + 1: [CONSTANTS["FEATURE_COLS"][idx] for idx in dominant_indices_map[k]] for k in dominant_indices_map},
        "J_k_indices": {k + 1: dominant_indices_map[k] for k in dominant_indices_map},
        "s_k": {k + 1: float(signs[k]) for k in range(CONSTANTS["N_COMPONENTS_RETAINED"])},
        "pillar_labels": {k + 1: pillar_labels[k] for k in pillar_labels},
    }
    with pillar_weights_path.open("wb") as file:
        pickle.dump(pillar_weights_payload, file)

    score_params_payload = {
        "P_bar_k": means.tolist(),
        "sigma_P_k": stds.tolist(),
        "alpha_k": alpha.tolist(),
        "I_min": index_min,
        "I_max": index_max,
        "SCORE_MIN": CONSTANTS["SCORE_MIN"],
        "SCORE_MAX": CONSTANTS["SCORE_MAX"],
    }
    with score_params_path.open("wb") as file:
        pickle.dump(score_params_payload, file)

    print(f"[A4-A5] Saved artifact: {standard_scaler_path}")
    print(f"[A4-A5] Saved artifact: {pca_loadings_path}")
    print(f"[A4-A5] Saved artifact: {pillar_weights_path}")
    print(f"[A4-A5] Saved artifact: {score_params_path}")


def _save_outputs(
    augmented_df: pd.DataFrame,
    standardized_pillars: np.ndarray,
    score_values: np.ndarray,
) -> None:
    """Persist pillar and sustainability score outputs for real and augmented sets."""
    pillar_df = augmented_df[["county", "year", "variant_id"]].copy()
    for pillar_index in range(CONSTANTS["N_COMPONENTS_RETAINED"]):
        pillar_df[f"P{pillar_index + 1}"] = standardized_pillars[:, pillar_index]

    score_augmented_df = augmented_df[["county", "year", "variant_id"]].copy()
    score_augmented_df["score"] = score_values

    score_real_df = score_augmented_df[score_augmented_df["variant_id"] == CONSTANTS["REAL_VARIANT_ID"]][
        ["county", "year", "score"]
    ].copy()
    score_real_df = score_real_df.sort_values(["county", "year"]).reset_index(drop=True)

    pillar_path = CONSTANTS["DATA_DIR"] / CONSTANTS["PILLAR_OUTPUT_FILENAME"]
    score_real_path = CONSTANTS["DATA_DIR"] / CONSTANTS["REAL_SCORE_OUTPUT_FILENAME"]
    score_augmented_path = CONSTANTS["DATA_DIR"] / CONSTANTS["AUGMENTED_SCORE_OUTPUT_FILENAME"]

    pillar_df.to_csv(pillar_path, index=False)
    score_real_df.to_csv(score_real_path, index=False)
    score_augmented_df.to_csv(score_augmented_path, index=False)

    print(f"[A4-A5] Saved output: {pillar_path} shape={pillar_df.shape}")
    print(f"[A4-A5] Saved output: {score_real_path} shape={score_real_df.shape}")
    print(f"[A4-A5] Saved output: {score_augmented_path} shape={score_augmented_df.shape}")


def run_pca_and_scoring() -> None:
    """Run Phases A4-A5 using StandardScaler, PCA, and variance-weighted scoring."""
    _print_phase_header()
    augmented_df = _load_augmented_input()
    scaler, x_scaled = _fit_standard_scaler_and_transform(augmented_df)
    _, loadings, _, variance_ratios = _fit_pca(x_scaled)

    dominant_map = _dominant_feature_indices(loadings)
    signs = _compute_sign_calibration(loadings, dominant_map)
    calibrated_loadings = loadings * signs
    weights_map, dominant_indices_map = _compute_within_pillar_weights(calibrated_loadings, dominant_map)

    pillar_labels: dict[int, str] = {}
    for component_index in range(CONSTANTS["N_COMPONENTS_RETAINED"]):
        dominant_features = {CONSTANTS["FEATURE_COLS"][idx] for idx in dominant_indices_map[component_index]}
        label = _match_pillar_label(dominant_features)
        pillar_labels[component_index] = label
        print(
            f"[A4] Component {component_index + 1} labeled '{label}' with dominant features: "
            f"{sorted(dominant_features)}"
        )

    _, standardized_pillars, means, stds = _compute_raw_and_standardized_pillars(
        x_scaled=x_scaled,
        weights_map=weights_map,
        dominant_indices_map=dominant_indices_map,
    )
    alpha = _compute_alpha_weights(variance_ratios)
    score_values, index_min, index_max = _compute_scaled_scores(standardized_pillars, alpha)

    _save_artifacts(
        scaler=scaler,
        calibrated_loadings=calibrated_loadings,
        signs=signs,
        weights_map=weights_map,
        dominant_indices_map=dominant_indices_map,
        pillar_labels=pillar_labels,
        means=means,
        stds=stds,
        alpha=alpha,
        index_min=index_min,
        index_max=index_max,
    )
    _save_outputs(
        augmented_df=augmented_df,
        standardized_pillars=standardized_pillars,
        score_values=score_values,
    )
    print(
        f"[A5] Score range: min={float(np.min(score_values)):.1f}, "
        f"max={float(np.max(score_values)):.1f}, SCORE_MIN={CONSTANTS['SCORE_MIN']}, "
        f"SCORE_MAX={CONSTANTS['SCORE_MAX']}"
    )
    print("[A4-A5] Completed successfully.")

