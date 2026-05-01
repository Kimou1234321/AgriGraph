"""Phases A7-A7b STGNN eval training and full-data forecast retraining."""

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

CONSTANTS: dict[str, Any] = {
    "PHASE": "A7_A7B",
    "DATA_DIR": Path(__file__).resolve().parents[1] / "data",
    "ARTIFACTS_DIR": Path(__file__).resolve().parents[1] / "artifacts",
    "MODELS_DIR": Path(__file__).resolve().parents[1] / "models",
    "PILLAR_SCORES_FILENAME": "pillar_scores_augmented.csv",
    "SCORES_AUGMENTED_FILENAME": "sustainability_scores_augmented.csv",
    "SCORES_REAL_FILENAME": "sustainability_scores.csv",
    "EDGE_INDEX_FILENAME": "edge_index.pt",
    "COUNTIES_FILENAME": "graph_counties.pkl",
    "LAG_NORM_FILENAME": "lag_norm.pkl",
    "EVAL_WEIGHTS_FILENAME": "stgnn_eval_weights.pt",
    "FORECAST_WEIGHTS_FILENAME": "stgnn_forecast_weights.pt",
    "METRICS_FILENAME": "stgnn_metrics.json",
    "TARGET_SCALER_FILENAME": "stgnn_target_scaler.pkl",
    "EVAL_PREDICTIONS_FILENAME": "stgnn_eval_predictions.csv",
    "F_PILLARS": 4,
    "F_TOTAL": 5,
    "GCN_HIDDEN": 64,
    "ATTN_DIM": 32,
    "HEAD_HIDDEN": 16,
    "DROPOUT": 0.2,
    "EPOCHS": 500,
    "LEARNING_RATE": 1e-3,
    "WEIGHT_DECAY": 1e-4,
    "INPUT_YEARS": [2021, 2022, 2023, 2024],
    "TARGET_YEAR": 2025,
    "REAL_VARIANT_ID": 0,
    "SYNTHETIC_VARIANTS": [1, 2, 3, 4],
    "ALL_VARIANTS": [0, 1, 2, 3, 4],
    "SEED": 42,
    "EPSILON": 1e-8,
    "LOG_EPOCHS": (1, 100, 250, 500),
    "EXPECTED_NODES": 26,
    "EXPECTED_T": 4,
}


class STGNN(nn.Module):
    """Spatio-temporal GNN: 2 GCN layers, causal temporal attention, regression head."""

    def __init__(self) -> None:
        """Initialize GCN, attention projections, and regression layers."""
        super().__init__()
        self.conv1 = GCNConv(CONSTANTS["F_TOTAL"], CONSTANTS["GCN_HIDDEN"])
        self.conv2 = GCNConv(CONSTANTS["GCN_HIDDEN"], CONSTANTS["GCN_HIDDEN"])
        self.dropout = nn.Dropout(CONSTANTS["DROPOUT"])
        self.w_q = nn.Linear(CONSTANTS["GCN_HIDDEN"], CONSTANTS["ATTN_DIM"])
        self.w_k = nn.Linear(CONSTANTS["GCN_HIDDEN"], CONSTANTS["ATTN_DIM"])
        self.w_v = nn.Linear(CONSTANTS["GCN_HIDDEN"], CONSTANTS["ATTN_DIM"])
        self.w_out = nn.Linear(CONSTANTS["ATTN_DIM"], CONSTANTS["ATTN_DIM"])
        self.head1 = nn.Linear(CONSTANTS["ATTN_DIM"], CONSTANTS["HEAD_HIDDEN"])
        self.head2 = nn.Linear(CONSTANTS["HEAD_HIDDEN"], 1)

    def forward(self, x_seq: Tensor, edge_index: Tensor) -> Tensor:
        """Predict county scores for TARGET_YEAR from input years [2021..2024]."""
        time_steps, _, _ = x_seq.shape
        spatial_embeddings: list[Tensor] = []
        for t in range(time_steps):
            node_features = x_seq[t]
            hidden = self.conv1(node_features, edge_index)
            hidden = F.relu(hidden)
            hidden = self.dropout(hidden)
            hidden = self.conv2(hidden, edge_index)
            hidden = F.relu(hidden)
            hidden = self.dropout(hidden)
            spatial_embeddings.append(hidden)
        h_stack = torch.stack(spatial_embeddings, dim=0)
        queries = self.w_q(h_stack)
        keys = self.w_k(h_stack)
        values = self.w_v(h_stack)
        last_idx = time_steps - 1
        query_last = queries[last_idx]
        scale = float(CONSTANTS["ATTN_DIM"]) ** 0.5
        scores = torch.einsum("nd,tnd->nt", query_last, keys) / scale
        future_mask = torch.triu(
            torch.ones(time_steps, time_steps, device=x_seq.device, dtype=torch.bool),
            diagonal=1,
        )
        mask_row = future_mask[last_idx].unsqueeze(0).expand_as(scores)
        scores = scores.masked_fill(mask_row, float("-inf"))
        attention_weights = F.softmax(scores, dim=1)
        context = torch.einsum("nt,tnd->nd", attention_weights, values)
        context = self.w_out(context)
        head_hidden = F.relu(self.head1(context))
        predictions = self.head2(head_hidden).squeeze(-1)
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


def _load_pillar_and_score_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load pillar scores and augmented sustainability scores."""
    pillar_path = CONSTANTS["DATA_DIR"] / CONSTANTS["PILLAR_SCORES_FILENAME"]
    score_path = CONSTANTS["DATA_DIR"] / CONSTANTS["SCORES_AUGMENTED_FILENAME"]
    if not pillar_path.exists():
        raise FileNotFoundError(f"[A7] Missing {pillar_path}")
    if not score_path.exists():
        raise FileNotFoundError(f"[A7] Missing {score_path}")
    pillars_df = pd.read_csv(pillar_path)
    scores_df = pd.read_csv(score_path)
    return pillars_df, scores_df


def _compute_lag_norm(scores_df: pd.DataFrame) -> tuple[float, float]:
    """Compute global mean and std of scores over all augmented rows for lag scaling."""
    y_bar = float(scores_df["score"].mean())
    sigma_y = float(scores_df["score"].std())
    if sigma_y <= CONSTANTS["EPSILON"]:
        sigma_y = 1.0
    return y_bar, sigma_y


def _compute_target_scaler(scores_df: pd.DataFrame) -> tuple[float, float]:
    """Compute score target scaling parameters from augmented training rows."""
    target_mean = float(scores_df["score"].mean())
    target_std = float(scores_df["score"].std())
    if target_std <= CONSTANTS["EPSILON"]:
        target_std = 1.0
    return target_mean, target_std


def _save_lag_norm(y_bar: float, sigma_y: float) -> None:
    """Persist lag normalization constants for A8+."""
    CONSTANTS["ARTIFACTS_DIR"].mkdir(parents=True, exist_ok=True)
    path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["LAG_NORM_FILENAME"]
    payload = {"y_bar": y_bar, "sigma_y": sigma_y}
    with path.open("wb") as file:
        pickle.dump(payload, file)
    print(f"[A7] Saved lag norm: {path} y_bar={y_bar:.6f}, sigma_y={sigma_y:.6f}")


def _save_target_scaler(target_mean: float, target_std: float) -> None:
    """Persist target scaling constants for A7/A7b/A8/A10 consistency."""
    CONSTANTS["ARTIFACTS_DIR"].mkdir(parents=True, exist_ok=True)
    path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["TARGET_SCALER_FILENAME"]
    payload = {"target_mean": target_mean, "target_std": target_std}
    with path.open("wb") as file:
        pickle.dump(payload, file)
    print(f"[A7] Saved target scaler: {path} mean={target_mean:.6f}, std={target_std:.6f}")


def _scale_values(values: Tensor, target_mean: float, target_std: float) -> Tensor:
    """Standardize score values for stable optimization."""
    return (values - target_mean) / max(target_std, CONSTANTS["EPSILON"])


def _inverse_scale_numpy(values: np.ndarray, target_mean: float, target_std: float) -> np.ndarray:
    """Map standardized predictions back to score units."""
    return (values * max(target_std, CONSTANTS["EPSILON"])) + target_mean


def _build_snapshot_tensor(
    pillars_df: pd.DataFrame,
    scores_df: pd.DataFrame,
    counties: list[str],
    variant_id: int,
    year: int,
    y_bar: float,
    sigma_y: float,
) -> Tensor:
    """Build node feature matrix (N, 5) for one graph snapshot."""
    county_to_idx = {c: i for i, c in enumerate(counties)}
    p_sub = pillars_df[
        (pillars_df["variant_id"] == variant_id) & (pillars_df["year"] == year)
    ].set_index("county")
    s_sub = scores_df.set_index(["county", "year", "variant_id"])
    features = np.zeros((CONSTANTS["EXPECTED_NODES"], CONSTANTS["F_TOTAL"]), dtype=np.float64)
    for county in counties:
        idx = county_to_idx[county]
        row_p = p_sub.loc[county]
        p1, p2, p3, p4 = float(row_p["P1"]), float(row_p["P2"]), float(row_p["P3"]), float(row_p["P4"])
        if year == CONSTANTS["INPUT_YEARS"][0]:
            lag_val = 0.0
        else:
            prev_year = year - 1
            y_prev = float(s_sub.loc[(county, prev_year, variant_id), "score"])
            lag_val = (y_prev - y_bar) / sigma_y
        features[idx, 0] = p1
        features[idx, 1] = p2
        features[idx, 2] = p3
        features[idx, 3] = p4
        features[idx, 4] = lag_val
    return torch.tensor(features, dtype=torch.float32)


def _build_sequence_tensor(
    pillars_df: pd.DataFrame,
    scores_df: pd.DataFrame,
    counties: list[str],
    variant_id: int,
    y_bar: float,
    sigma_y: float,
) -> Tensor:
    """Stack T=4 snapshots into (T, N, F)."""
    snapshots = [
        _build_snapshot_tensor(pillars_df, scores_df, counties, variant_id, y, y_bar, sigma_y)
        for y in CONSTANTS["INPUT_YEARS"]
    ]
    return torch.stack(snapshots, dim=0)


def _target_vector(
    scores_df: pd.DataFrame,
    counties: list[str],
    variant_id: int,
) -> Tensor:
    """Return 2025 target scores (N,) for one variant."""
    county_to_idx = {c: i for i, c in enumerate(counties)}
    sub = scores_df[
        (scores_df["variant_id"] == variant_id) & (scores_df["year"] == CONSTANTS["TARGET_YEAR"])
    ].set_index("county")
    target = np.zeros(CONSTANTS["EXPECTED_NODES"], dtype=np.float64)
    for county in counties:
        target[county_to_idx[county]] = float(sub.loc[county, "score"])
    return torch.tensor(target, dtype=torch.float32)


def _train_one_run(
    model: STGNN,
    edge_index: Tensor,
    train_variants: list[int],
    seq_by_variant: dict[int, Tensor],
    target_by_variant: dict[int, Tensor],
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
        for vid in train_variants:
            pred = model(seq_by_variant[vid], edge_index)
            diff = pred - target_by_variant[vid]
            loss = loss + (diff * diff).sum()
        denom = len(train_variants) * CONSTANTS["EXPECTED_NODES"]
        loss = loss / denom
        loss.backward()
        optimizer.step()
        if epoch in CONSTANTS["LOG_EPOCHS"] or epoch == epochs:
            print(f"[{phase_tag}] Epoch {epoch:03d}/{epochs} train_mse={float(loss.detach()):.6f}")


def _predict_variant(
    model: STGNN,
    edge_index: Tensor,
    seq_by_variant: dict[int, Tensor],
    variant_id: int,
) -> np.ndarray:
    """Run forward pass for one variant and return numpy predictions."""
    model.eval()
    with torch.no_grad():
        pred = model(seq_by_variant[variant_id], edge_index)
    return pred.cpu().numpy()


def _r2_over_variants(
    model: STGNN,
    edge_index: Tensor,
    variants: list[int],
    seq_by_variant: dict[int, Tensor],
    target_by_variant_scaled: dict[int, Tensor],
) -> float:
    """Compute R² pooled over listed variants (each N nodes)."""
    y_true_list: list[np.ndarray] = []
    y_pred_list: list[np.ndarray] = []
    for vid in variants:
        y_true_list.append(target_by_variant_scaled[vid].cpu().numpy())
        y_pred_list.append(_predict_variant(model, edge_index, seq_by_variant, vid))
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
    _print_header("[A7] STGNN EVAL TRAINING + METRICS")
    _set_seed(CONSTANTS["SEED"])
    device = torch.device("cpu")
    edge_index = _load_edge_index().to(device)
    counties = _load_counties()
    pillars_df, scores_df = _load_pillar_and_score_frames()
    y_bar, sigma_y = _compute_lag_norm(scores_df)
    _save_lag_norm(y_bar, sigma_y)
    target_mean, target_std = _compute_target_scaler(scores_df)
    _save_target_scaler(target_mean, target_std)

    seq_by_variant: dict[int, Tensor] = {}
    target_by_variant_raw: dict[int, Tensor] = {}
    target_by_variant_scaled: dict[int, Tensor] = {}
    for vid in CONSTANTS["ALL_VARIANTS"]:
        seq_by_variant[vid] = _build_sequence_tensor(
            pillars_df, scores_df, counties, vid, y_bar, sigma_y
        ).to(device)
        target_raw = _target_vector(scores_df, counties, vid).to(device)
        target_by_variant_raw[vid] = target_raw
        target_by_variant_scaled[vid] = _scale_values(target_raw, target_mean, target_std)

    print(
        f"[A7] Built sequences: T={CONSTANTS['EXPECTED_T']}, N={CONSTANTS['EXPECTED_NODES']}, "
        f"F={CONSTANTS['F_TOTAL']}, variants={CONSTANTS['ALL_VARIANTS']}"
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
            seq_by_variant,
            target_by_variant_scaled,
            CONSTANTS["EPOCHS"],
            f"A7-fold{fold_idx + 1}",
        )
        train_r2 = _r2_over_variants(
            model,
            edge_index,
            train_variants,
            seq_by_variant,
            target_by_variant_scaled,
        )
        val_r2 = _r2_over_variants(
            model,
            edge_index,
            [val_variant],
            seq_by_variant,
            target_by_variant_scaled,
        )
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
        seq_by_variant,
        target_by_variant_scaled,
        CONSTANTS["EPOCHS"],
        "A7-final",
    )
    eval_path = CONSTANTS["MODELS_DIR"] / CONSTANTS["EVAL_WEIGHTS_FILENAME"]
    _save_weights(
        eval_path,
        eval_model,
        {
            "phase": "A7",
            "lag_norm": {"y_bar": y_bar, "sigma_y": sigma_y},
            "target_scaler": {"target_mean": target_mean, "target_std": target_std},
            "counties": counties,
        },
    )

    real_target_path = CONSTANTS["DATA_DIR"] / CONSTANTS["SCORES_REAL_FILENAME"]
    if not real_target_path.exists():
        raise FileNotFoundError(f"[A7] Missing real scores for test: {real_target_path}")
    real_scores = pd.read_csv(real_target_path)
    county_to_idx = {c: i for i, c in enumerate(counties)}
    y_test = np.zeros(CONSTANTS["EXPECTED_NODES"], dtype=np.float64)
    real_scores_target_year = real_scores[real_scores["year"] == CONSTANTS["TARGET_YEAR"]]
    if len(real_scores_target_year) != CONSTANTS["EXPECTED_NODES"]:
        raise ValueError(
            f"[A7] Expected {CONSTANTS['EXPECTED_NODES']} real target rows for "
            f"{CONSTANTS['TARGET_YEAR']}, found {len(real_scores_target_year)}"
        )
    for _, row in real_scores_target_year.iterrows():
        y_test[county_to_idx[str(row["county"])]] = float(row["score"])

    y_pred_scaled = _predict_variant(eval_model, edge_index, seq_by_variant, CONSTANTS["REAL_VARIANT_ID"])
    y_pred_score = _inverse_scale_numpy(y_pred_scaled, target_mean, target_std)
    test_r2 = float(r2_score(y_test, y_pred_score))
    test_mae = float(mean_absolute_error(y_test, y_pred_score))
    test_mse = float(mean_squared_error(y_test, y_pred_score))
    y_test_norm = (y_test - target_mean) / max(target_std, CONSTANTS["EPSILON"])
    y_pred_norm = (y_pred_score - target_mean) / max(target_std, CONSTANTS["EPSILON"])
    test_mae_norm = float(mean_absolute_error(y_test_norm, y_pred_norm))
    test_mse_norm = float(mean_squared_error(y_test_norm, y_pred_norm))
    print(f"[A7] Test (variant_id=0, 2025) R2={test_r2:.6f} MAE={test_mae:.6f} MSE={test_mse:.6f}")

    eval_predictions_df = pd.DataFrame(
        {
            "county": counties,
            "year": [CONSTANTS["TARGET_YEAR"]] * len(counties),
            "y_true_score": y_test,
            "y_pred_score": y_pred_score,
            "y_true_norm": y_test_norm,
            "y_pred_norm": y_pred_norm,
            "residual_score": y_pred_score - y_test,
            "residual_norm": y_pred_norm - y_test_norm,
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
        "target_scale": "standardized",
        "target_scaler": {"target_mean": target_mean, "target_std": target_std},
        "eval_train_variants": eval_train_variants,
        "eval_test_variant": CONSTANTS["REAL_VARIANT_ID"],
        "test_set": "variant_id=0, year=2025",
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
        seq_by_variant,
        target_by_variant_scaled,
        CONSTANTS["EPOCHS"],
        "A7b",
    )
    forecast_path = CONSTANTS["MODELS_DIR"] / CONSTANTS["FORECAST_WEIGHTS_FILENAME"]
    _save_weights(
        forecast_path,
        forecast_model,
        {
            "phase": "A7b",
            "lag_norm": {"y_bar": y_bar, "sigma_y": sigma_y},
            "target_scaler": {"target_mean": target_mean, "target_std": target_std},
            "counties": counties,
        },
    )
    print("[A7b] Completed; metrics unchanged (A7 only).")
