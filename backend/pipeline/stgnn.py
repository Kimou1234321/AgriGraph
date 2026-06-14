"""Phases A7-A7b STGNN eval training and full-data forecast retraining (pillar output)."""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from torch import Tensor, nn
from torch_geometric.nn import GCNConv

from backend.pipeline.pillar_transform import load_frozen_transforms, pillar_matrix_to_scores

CONSTANTS: dict[str, Any] = {
    "PHASE": "A7_A7B",
    "DATA_DIR": Path(__file__).resolve().parents[1] / "data",
    "ARTIFACTS_DIR": Path(__file__).resolve().parents[1] / "artifacts",
    "MODELS_DIR": Path(__file__).resolve().parents[1] / "models",
    "PILLAR_SCORES_FILENAME": "pillar_scores_augmented.csv",
    "SCORES_REAL_FILENAME": "sustainability_scores.csv",
    "EDGE_INDEX_FILENAME": "edge_index.pt",
    "COUNTIES_FILENAME": "graph_counties.pkl",
    "EVAL_WEIGHTS_FILENAME": "stgnn_eval_weights.pt",
    "FORECAST_WEIGHTS_FILENAME": "stgnn_forecast_weights.pt",
    "METRICS_FILENAME": "stgnn_metrics.json",
    "PILLAR_TARGET_SCALER_FILENAME": "stgnn_pillar_target_scaler.pkl",
    "EVAL_PREDICTIONS_FILENAME": "stgnn_eval_predictions.csv",
    "F_PILLARS": 4,
    "F_TOTAL": 4,
    "OUTPUT_DIM": 4,
    "GCN_HIDDEN": 24,
    "HEAD_HIDDEN": 16,
    "DROPOUT": 0.1,
    "EPOCHS": 500,
    "LEARNING_RATE": 1e-3,
    "WEIGHT_DECAY": 1e-4,
    "WINDOW_LEN": 2,
    "INPUT_YEAR_PAIRS": [(2021, 2022, 2023), (2022, 2023, 2024), (2023, 2024, 2025)],
    "EVAL_INPUT_PAIR": (2023, 2024, 2025),
    "TARGET_YEAR": 2025,
    "REAL_VARIANT_ID": 0,
    "SYNTHETIC_VARIANTS": [1, 2, 3, 4],
    "ALL_VARIANTS": [0, 1, 2, 3, 4],
    "SEED": 42,
    "EPSILON": 1e-8,
    "LOG_EPOCHS": (1, 100, 250, 500),
    "EXPECTED_NODES": 26,
}


class STGNN(nn.Module):
    """Lightweight spatio-temporal GNN: 1 GCN per timestep, concat temporal state, 4-pillar head."""

    def __init__(self) -> None:
        """Initialize GCN layers and pillar regression head."""
        super().__init__()
        self.conv = GCNConv(CONSTANTS["F_TOTAL"], CONSTANTS["GCN_HIDDEN"])
        self.dropout = nn.Dropout(CONSTANTS["DROPOUT"])
        combined_dim = CONSTANTS["GCN_HIDDEN"] * CONSTANTS["WINDOW_LEN"]
        self.head1 = nn.Linear(combined_dim, CONSTANTS["HEAD_HIDDEN"])
        self.head2 = nn.Linear(CONSTANTS["HEAD_HIDDEN"], CONSTANTS["OUTPUT_DIM"])

    def forward(self, x_seq: Tensor, edge_index: Tensor) -> Tensor:
        """Predict next-year pillar vector (N, 4) from a 2-step pillar window."""
        time_steps, _, _ = x_seq.shape
        spatial_embeddings: list[Tensor] = []
        for t in range(time_steps):
            node_features = x_seq[t]
            hidden = self.conv(node_features, edge_index)
            hidden = F.relu(hidden)
            hidden = self.dropout(hidden)
            spatial_embeddings.append(hidden)
        combined = torch.cat(spatial_embeddings, dim=1)
        head_hidden = F.relu(self.head1(combined))
        predictions = self.head2(head_hidden)
        return predictions


def _set_seed(seed: int) -> None:
    """Set RNG seeds for reproducible training."""
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _print_header(title: str) -> None:
    """Print a section banner."""
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _load_edge_index() -> Tensor:
    """Load fixed graph edge_index from artifacts."""
    path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["EDGE_INDEX_FILENAME"]
    if not path.exists():
        raise FileNotFoundError(f"[A7] Missing edge_index: {path}")
    edge_index = torch.load(path, map_location="cpu")
    if not isinstance(edge_index, Tensor):
        edge_index = torch.as_tensor(edge_index)
    return edge_index.long()


def _load_counties() -> list[str]:
    """Load canonical county node order."""
    path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["COUNTIES_FILENAME"]
    if not path.exists():
        raise FileNotFoundError(f"[A7] Missing counties list: {path}")
    with path.open("rb") as file:
        counties = pickle.load(file)
    if len(counties) != CONSTANTS["EXPECTED_NODES"]:
        raise ValueError(f"[A7] Expected {CONSTANTS['EXPECTED_NODES']} counties, got {len(counties)}")
    return list(counties)


def _load_pillar_frame() -> pd.DataFrame:
    """Load pillar scores augmented dataframe."""
    pillar_path = CONSTANTS["DATA_DIR"] / CONSTANTS["PILLAR_SCORES_FILENAME"]
    if not pillar_path.exists():
        raise FileNotFoundError(f"[A7] Missing {pillar_path}")
    return pd.read_csv(pillar_path)


def _compute_pillar_target_scaler(pillars_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Compute per-pillar target mean and std from augmented training rows."""
    cols = [f"P{i + 1}" for i in range(CONSTANTS["F_PILLARS"])]
    target_mean = pillars_df[cols].mean(axis=0).to_numpy(dtype=np.float64)
    target_std = pillars_df[cols].std(axis=0).to_numpy(dtype=np.float64)
    target_std = np.where(target_std <= CONSTANTS["EPSILON"], 1.0, target_std)
    return target_mean, target_std


def _save_pillar_target_scaler(target_mean: np.ndarray, target_std: np.ndarray) -> None:
    """Persist pillar target scaling constants for A7/A7b/A8/A10 consistency."""
    CONSTANTS["ARTIFACTS_DIR"].mkdir(parents=True, exist_ok=True)
    path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["PILLAR_TARGET_SCALER_FILENAME"]
    payload = {"target_mean": target_mean.tolist(), "target_std": target_std.tolist()}
    with path.open("wb") as file:
        pickle.dump(payload, file)
    print(f"[A7] Saved pillar target scaler: {path}")


def _scale_pillar_matrix(values: np.ndarray, target_mean: np.ndarray, target_std: np.ndarray) -> Tensor:
    """Standardize pillar matrix (N, 4) for stable optimization."""
    scaled = (values - target_mean.reshape(1, -1)) / np.maximum(target_std.reshape(1, -1), CONSTANTS["EPSILON"])
    return torch.tensor(scaled, dtype=torch.float32)


def _inverse_scale_pillar_matrix(values: np.ndarray, target_mean: np.ndarray, target_std: np.ndarray) -> np.ndarray:
    """Map standardized pillar predictions back to pillar units."""
    return (values * np.maximum(target_std.reshape(1, -1), CONSTANTS["EPSILON"])) + target_mean.reshape(1, -1)


def _pillar_matrix_for_year(
    pillars_df: pd.DataFrame,
    counties: list[str],
    variant_id: int,
    year: int,
) -> np.ndarray:
    """Build node feature matrix (N, 4) for one graph snapshot."""
    county_to_idx = {c: i for i, c in enumerate(counties)}
    p_sub = pillars_df[
        (pillars_df["variant_id"] == variant_id) & (pillars_df["year"] == year)
    ].set_index("county")
    features = np.zeros((CONSTANTS["EXPECTED_NODES"], CONSTANTS["F_TOTAL"]), dtype=np.float64)
    for county in counties:
        idx = county_to_idx[county]
        row_p = p_sub.loc[county]
        features[idx, 0] = float(row_p["P1"])
        features[idx, 1] = float(row_p["P2"])
        features[idx, 2] = float(row_p["P3"])
        features[idx, 3] = float(row_p["P4"])
    return features


def _build_sequence_tensor(
    pillars_df: pd.DataFrame,
    counties: list[str],
    variant_id: int,
    year_pair: tuple[int, int, int],
) -> Tensor:
    """Stack T=2 pillar snapshots into (T, N, F)."""
    y1, y2, _ = year_pair
    snapshots = [
        _pillar_matrix_for_year(pillars_df, counties, variant_id, y1),
        _pillar_matrix_for_year(pillars_df, counties, variant_id, y2),
    ]
    return torch.tensor(np.stack(snapshots, axis=0), dtype=torch.float32)


def _target_pillar_matrix(
    pillars_df: pd.DataFrame,
    counties: list[str],
    variant_id: int,
    target_year: int,
) -> np.ndarray:
    """Return target pillar matrix (N, 4) for one variant and year."""
    return _pillar_matrix_for_year(pillars_df, counties, variant_id, target_year)


def _build_training_samples(
    pillars_df: pd.DataFrame,
    counties: list[str],
    variant_id: int,
    target_mean: np.ndarray,
    target_std: np.ndarray,
) -> list[tuple[Tensor, Tensor]]:
    """Build sliding 2-step training samples for one variant."""
    samples: list[tuple[Tensor, Tensor]] = []
    for y1, y2, target_year in CONSTANTS["INPUT_YEAR_PAIRS"]:
        seq = _build_sequence_tensor(pillars_df, counties, variant_id, (y1, y2, target_year))
        target_raw = _target_pillar_matrix(pillars_df, counties, variant_id, target_year)
        target_scaled = _scale_pillar_matrix(target_raw, target_mean, target_std)
        samples.append((seq, target_scaled))
    return samples


def _train_one_run(
    model: STGNN,
    edge_index: Tensor,
    train_variants: list[int],
    samples_by_variant: dict[int, list[tuple[Tensor, Tensor]]],
    epochs: int,
    phase_tag: str,
) -> None:
    """Train STGNN with Adam for a fixed number of epochs."""
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=CONSTANTS["LEARNING_RATE"],
        weight_decay=CONSTANTS["WEIGHT_DECAY"],
    )
    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        loss = torch.tensor(0.0, dtype=torch.float32, device=edge_index.device)
        sample_count = 0
        for vid in train_variants:
            for seq, target in samples_by_variant[vid]:
                pred = model(seq, edge_index)
                diff = pred - target
                loss = loss + (diff * diff).sum()
                sample_count += 1
        denom = sample_count * CONSTANTS["EXPECTED_NODES"] * CONSTANTS["OUTPUT_DIM"]
        loss = loss / denom
        loss.backward()
        optimizer.step()
        if epoch in CONSTANTS["LOG_EPOCHS"] or epoch == epochs:
            print(f"[{phase_tag}] Epoch {epoch:03d}/{epochs} train_mse={float(loss.detach()):.6f}")


def _predict_sample(
    model: STGNN,
    edge_index: Tensor,
    seq: Tensor,
) -> np.ndarray:
    """Run forward pass for one sequence and return numpy pillar predictions (N, 4)."""
    model.eval()
    with torch.no_grad():
        pred = model(seq, edge_index)
    return pred.cpu().numpy()


def _r2_over_variants_pillars(
    model: STGNN,
    edge_index: Tensor,
    variants: list[int],
    samples_by_variant: dict[int, list[tuple[Tensor, Tensor]]],
) -> float:
    """Compute R² pooled over listed variants on standardized pillar targets."""
    y_true_list: list[np.ndarray] = []
    y_pred_list: list[np.ndarray] = []
    for vid in variants:
        for seq, target in samples_by_variant[vid]:
            y_true_list.append(target.cpu().numpy().reshape(-1))
            y_pred_list.append(_predict_sample(model, edge_index, seq).reshape(-1))
    y_true = np.concatenate(y_true_list)
    y_pred = np.concatenate(y_pred_list)
    return float(r2_score(y_true, y_pred))


def _save_weights(path: Path, model: STGNN, extra: dict[str, Any]) -> None:
    """Save model state and small metadata dict."""
    CONSTANTS["MODELS_DIR"].mkdir(parents=True, exist_ok=True)
    payload = {"state_dict": model.state_dict(), **extra}
    torch.save(payload, path)
    print(f"[A7/A7b] Saved weights: {path}")


def run_stgnn_training() -> None:
    """Run A7 K-fold + eval model + metrics, then A7b forecast model (no metrics)."""
    _print_header("[A7] STGNN PILLAR EVAL TRAINING + METRICS")
    _set_seed(CONSTANTS["SEED"])
    device = torch.device("cpu")
    edge_index = _load_edge_index().to(device)
    counties = _load_counties()
    pillars_df = _load_pillar_frame()
    target_mean, target_std = _compute_pillar_target_scaler(pillars_df)
    _save_pillar_target_scaler(target_mean, target_std)
    frozen = load_frozen_transforms()

    samples_by_variant: dict[int, list[tuple[Tensor, Tensor]]] = {}
    for vid in CONSTANTS["ALL_VARIANTS"]:
        samples_by_variant[vid] = _build_training_samples(
            pillars_df, counties, vid, target_mean, target_std
        )
        for seq, _ in samples_by_variant[vid]:
            seq.to(device)

    print(
        f"[A7] Built pillar sequences: T={CONSTANTS['WINDOW_LEN']}, N={CONSTANTS['EXPECTED_NODES']}, "
        f"F={CONSTANTS['F_TOTAL']}, output={CONSTANTS['OUTPUT_DIM']}, variants={CONSTANTS['ALL_VARIANTS']}"
    )

    synth = CONSTANTS["SYNTHETIC_VARIANTS"]
    eval_train_variants = list(synth)
    training_r2_per_fold: list[float] = []
    validation_r2_per_fold: list[float] = []

    for fold_idx, val_variant in enumerate(synth):
        train_variants = [v for v in synth if v != val_variant]
        print(f"[A7] K-fold {fold_idx + 1}/4 train={train_variants} val={val_variant}")
        model = STGNN().to(device)
        _train_one_run(
            model,
            edge_index,
            train_variants,
            samples_by_variant,
            CONSTANTS["EPOCHS"],
            f"A7-fold{fold_idx + 1}",
        )
        train_r2 = _r2_over_variants_pillars(model, edge_index, train_variants, samples_by_variant)
        val_r2 = _r2_over_variants_pillars(model, edge_index, [val_variant], samples_by_variant)
        training_r2_per_fold.append(train_r2)
        validation_r2_per_fold.append(val_r2)
        print(f"[A7] Fold {fold_idx + 1} train_R2={train_r2:.6f} val_R2={val_r2:.6f}")

    training_r2_mean = float(np.mean(training_r2_per_fold))
    validation_r2_mean = float(np.mean(validation_r2_per_fold))
    print(f"[A7] K-fold mean train_R2={training_r2_mean:.6f} mean val_R2={validation_r2_mean:.6f}")

    _print_header("[A7] FINAL EVAL MODEL (train all synthetic variants)")
    eval_model = STGNN().to(device)
    _train_one_run(
        eval_model,
        edge_index,
        eval_train_variants,
        samples_by_variant,
        CONSTANTS["EPOCHS"],
        "A7-final",
    )
    eval_path = CONSTANTS["MODELS_DIR"] / CONSTANTS["EVAL_WEIGHTS_FILENAME"]
    _save_weights(
        eval_path,
        eval_model,
        {
            "phase": "A7",
            "pillar_target_scaler": {"target_mean": target_mean.tolist(), "target_std": target_std.tolist()},
            "counties": counties,
            "window_len": CONSTANTS["WINDOW_LEN"],
            "output_dim": CONSTANTS["OUTPUT_DIM"],
        },
    )

    real_target_path = CONSTANTS["DATA_DIR"] / CONSTANTS["SCORES_REAL_FILENAME"]
    if not real_target_path.exists():
        raise FileNotFoundError(f"[A7] Missing real scores for test: {real_target_path}")
    real_scores = pd.read_csv(real_target_path)
    county_to_idx = {c: i for i, c in enumerate(counties)}
    y_test_score = np.zeros(CONSTANTS["EXPECTED_NODES"], dtype=np.float64)
    real_scores_target_year = real_scores[real_scores["year"] == CONSTANTS["TARGET_YEAR"]]
    if len(real_scores_target_year) != CONSTANTS["EXPECTED_NODES"]:
        raise ValueError(
            f"[A7] Expected {CONSTANTS['EXPECTED_NODES']} real target rows for "
            f"{CONSTANTS['TARGET_YEAR']}, found {len(real_scores_target_year)}"
        )
    for _, row in real_scores_target_year.iterrows():
        y_test_score[county_to_idx[str(row["county"])]] = float(row["score"])

    eval_seq = _build_sequence_tensor(
        pillars_df,
        counties,
        CONSTANTS["REAL_VARIANT_ID"],
        CONSTANTS["EVAL_INPUT_PAIR"],
    ).to(device)
    y_pred_scaled = _predict_sample(eval_model, edge_index, eval_seq)
    y_pred_pillars = _inverse_scale_pillar_matrix(y_pred_scaled, target_mean, target_std)
    y_true_pillars = _target_pillar_matrix(
        pillars_df, counties, CONSTANTS["REAL_VARIANT_ID"], CONSTANTS["TARGET_YEAR"]
    )
    y_pred_score = pillar_matrix_to_scores(y_pred_pillars, frozen)
    test_r2 = float(r2_score(y_test_score, y_pred_score))
    test_mae = float(mean_absolute_error(y_test_score, y_pred_score))
    test_mse = float(mean_squared_error(y_test_score, y_pred_score))
    y_test_norm = (y_test_score - float(np.mean(y_test_score))) / max(float(np.std(y_test_score)), CONSTANTS["EPSILON"])
    y_pred_norm = (y_pred_score - float(np.mean(y_test_score))) / max(float(np.std(y_test_score)), CONSTANTS["EPSILON"])
    test_mae_norm = float(mean_absolute_error(y_test_norm, y_pred_norm))
    test_mse_norm = float(mean_squared_error(y_test_norm, y_pred_norm))
    print(f"[A7] Test (variant_id=0, 2025) score R2={test_r2:.6f} MAE={test_mae:.6f} MSE={test_mse:.6f}")

    eval_predictions_df = pd.DataFrame(
        {
            "county": counties,
            "year": [CONSTANTS["TARGET_YEAR"]] * len(counties),
            "y_true_score": y_test_score,
            "y_pred_score": y_pred_score,
            "y_true_P1": y_true_pillars[:, 0],
            "y_true_P2": y_true_pillars[:, 1],
            "y_true_P3": y_true_pillars[:, 2],
            "y_true_P4": y_true_pillars[:, 3],
            "y_pred_P1": y_pred_pillars[:, 0],
            "y_pred_P2": y_pred_pillars[:, 1],
            "y_pred_P3": y_pred_pillars[:, 2],
            "y_pred_P4": y_pred_pillars[:, 3],
            "residual_score": y_pred_score - y_test_score,
        }
    )
    eval_predictions_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["EVAL_PREDICTIONS_FILENAME"]
    eval_predictions_df.to_csv(eval_predictions_path, index=False)
    print(f"[A7] Saved eval predictions: {eval_predictions_path}")

    metrics_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["METRICS_FILENAME"]
    CONSTANTS["ARTIFACTS_DIR"].mkdir(parents=True, exist_ok=True)
    metrics_payload = {
        "phase": "A7",
        "training_r2_mean": training_r2_mean,
        "training_r2_per_fold": training_r2_per_fold,
        "validation_r2_mean": validation_r2_mean,
        "validation_r2_per_fold": validation_r2_per_fold,
        "test_r2": test_r2,
        "test_mae": test_mae,
        "test_mse": test_mse,
        "test_mae_norm": test_mae_norm,
        "test_mse_norm": test_mse_norm,
        "target_scale": "pillar_standardized",
        "pillar_target_scaler": {"target_mean": target_mean.tolist(), "target_std": target_std.tolist()},
        "eval_train_variants": eval_train_variants,
        "eval_test_variant": CONSTANTS["REAL_VARIANT_ID"],
        "test_set": "variant_id=0, year=2025, derived_score_from_pillars",
        "epochs": CONSTANTS["EPOCHS"],
    }
    metrics_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")
    print(f"[A7] Saved metrics (A7 only): {metrics_path}")

    _print_header("[A7b] STGNN FULL-DATA RETRAIN (FORECAST WEIGHTS, NO METRICS)")
    forecast_model = STGNN().to(device)
    _train_one_run(
        forecast_model,
        edge_index,
        CONSTANTS["ALL_VARIANTS"],
        samples_by_variant,
        CONSTANTS["EPOCHS"],
        "A7b",
    )
    forecast_path = CONSTANTS["MODELS_DIR"] / CONSTANTS["FORECAST_WEIGHTS_FILENAME"]
    _save_weights(
        forecast_path,
        forecast_model,
        {
            "phase": "A7b",
            "pillar_target_scaler": {"target_mean": target_mean.tolist(), "target_std": target_std.tolist()},
            "counties": counties,
            "window_len": CONSTANTS["WINDOW_LEN"],
            "output_dim": CONSTANTS["OUTPUT_DIM"],
        },
    )
    print("[A7b] Completed; metrics unchanged (A7 only).")
