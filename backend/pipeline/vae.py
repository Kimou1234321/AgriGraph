"""Phase A3 year-conditioned CVAE training and augmentation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import Tensor, nn
from torch.utils.data import DataLoader, TensorDataset

CONSTANTS: dict[str, Any] = {
    "PHASE": "A3",
    "DATA_DIR": Path(__file__).resolve().parents[1] / "data",
    "ARTIFACTS_DIR": Path(__file__).resolve().parents[1] / "artifacts",
    "MODELS_DIR": Path(__file__).resolve().parents[1] / "models",
    "NORMALIZED_PANEL_FILENAME": "x_normalized.csv",
    "AUGMENTED_FILENAME": "x_augmented.csv",
    "MODEL_FILENAME": "cvae_weights.pt",
    "HISTORY_FILENAME": "cvae_training_history.json",
    "VALIDATION_FILENAME": "cvae_validation_summary.json",
    "EXPECTED_ROWS": 130,
    "EXPECTED_AUGMENTED_ROWS": 650,
    "EXPECTED_COUNTIES": 26,
    "EXPECTED_YEARS": [2021, 2022, 2023, 2024, 2025],
    "EXPECTED_VARIANTS": [0, 1, 2, 3, 4],
    "REAL_VARIANT_ID": 0,
    "FIRST_SYNTHETIC_VARIANT_ID": 1,
    "INPUT_DIM": 17,
    "CONDITION_DIM": 5,
    "ENCODER_INPUT_DIM": 22,
    "LATENT_DIM": 80,
    "DECODER_INPUT_DIM": 85,
    "HIDDEN_DIM": 128,
    "ENCODER_OUTPUT_DIM": 160,
    "BETA": 1.0,
    "LEARNING_RATE": 1e-3,
    "EPOCHS": 200,
    "BATCH_SIZE": 32,
    "SYNTHETIC_PER_REAL": 4,
    "SEED": 42,
    "CORRELATION_NORM_THRESHOLD": 1.0,
    "MEAN_ABS_DIFF_THRESHOLD": 0.05,
    "LOG_INTERVAL": 25,
    "NORMALIZED_MIN": 0.0,
    "NORMALIZED_MAX": 1.0,
    "NORMALIZED_TOLERANCE": 1e-8,
    "KL_OFFSET": 1.0,
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


class YearConditionedCVAE(nn.Module):
    """Year-conditioned CVAE with the exact A3 architecture."""

    def __init__(self) -> None:
        """Initialize encoder and decoder layers."""
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(CONSTANTS["ENCODER_INPUT_DIM"], CONSTANTS["HIDDEN_DIM"]),
            nn.ReLU(),
            nn.Linear(CONSTANTS["HIDDEN_DIM"], CONSTANTS["ENCODER_OUTPUT_DIM"]),
        )
        self.decoder = nn.Sequential(
            nn.Linear(CONSTANTS["DECODER_INPUT_DIM"], CONSTANTS["HIDDEN_DIM"]),
            nn.ReLU(),
            nn.Linear(CONSTANTS["HIDDEN_DIM"], CONSTANTS["INPUT_DIM"]),
            nn.Sigmoid(),
        )

    def encode(self, x_values: Tensor, conditions: Tensor) -> tuple[Tensor, Tensor]:
        """Encode normalized features and year condition into mu and log variance."""
        encoded = self.encoder(torch.cat([x_values, conditions], dim=1))
        mu, log_sigma_squared = torch.chunk(encoded, chunks=2, dim=1)
        return mu, log_sigma_squared

    def reparameterize(self, mu: Tensor, log_sigma_squared: Tensor) -> Tensor:
        """Sample z using z = mu + sigma * eps, eps sampled from N(0,I)."""
        sigma = torch.sqrt(torch.exp(log_sigma_squared))
        epsilon = torch.randn_like(sigma)
        return mu + sigma * epsilon

    def decode(self, z_values: Tensor, conditions: Tensor) -> Tensor:
        """Decode latent samples and year condition into normalized features."""
        return self.decoder(torch.cat([z_values, conditions], dim=1))

    def forward(self, x_values: Tensor, conditions: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        """Run full CVAE forward pass."""
        mu, log_sigma_squared = self.encode(x_values, conditions)
        z_values = self.reparameterize(mu, log_sigma_squared)
        reconstruction = self.decode(z_values, conditions)
        return reconstruction, mu, log_sigma_squared


def _print_phase_header() -> None:
    """Print a readable phase header."""
    print("\n" + "=" * 72)
    print(f"[{CONSTANTS['PHASE']}] CONDITIONAL VAE DATA AUGMENTATION")
    print("=" * 72)


def _set_random_seeds() -> None:
    """Set random seeds for repeatable prototype augmentation."""
    np.random.seed(CONSTANTS["SEED"])
    torch.manual_seed(CONSTANTS["SEED"])
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(CONSTANTS["SEED"])
    print(f"[A3] Random seed set to {CONSTANTS['SEED']}.")


def _load_normalized_panel() -> pd.DataFrame:
    """Load normalized A2 panel from disk."""
    input_path = CONSTANTS["DATA_DIR"] / CONSTANTS["NORMALIZED_PANEL_FILENAME"]
    print(f"[A3] Loading normalized panel from: {input_path}")
    if not input_path.exists():
        raise FileNotFoundError(f"[A3] Missing A2 output: {input_path}")
    dataframe = pd.read_csv(input_path)
    _validate_normalized_panel(dataframe)
    return dataframe.sort_values(["county", "year"]).reset_index(drop=True)


def _validate_normalized_panel(df: pd.DataFrame) -> None:
    """Validate A2 normalized panel schema and bounds."""
    expected_columns = ["county", "year", *CONSTANTS["FEATURE_COLS"]]
    missing_columns = [col for col in expected_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"[A3] Missing normalized panel columns: {missing_columns}")
    if len(df) != CONSTANTS["EXPECTED_ROWS"]:
        raise ValueError(f"[A3] Expected {CONSTANTS['EXPECTED_ROWS']} rows, found {len(df)}.")

    years = sorted(df["year"].astype(int).unique().tolist())
    counties = sorted(df["county"].astype(str).unique().tolist())
    if years != CONSTANTS["EXPECTED_YEARS"]:
        raise ValueError(f"[A3] Expected years {CONSTANTS['EXPECTED_YEARS']}, found {years}.")
    if len(counties) != CONSTANTS["EXPECTED_COUNTIES"]:
        raise ValueError(f"[A3] Expected {CONSTANTS['EXPECTED_COUNTIES']} counties, found {len(counties)}.")

    feature_values = df[CONSTANTS["FEATURE_COLS"]]
    min_value = float(feature_values.min().min())
    max_value = float(feature_values.max().max())
    min_bound = CONSTANTS["NORMALIZED_MIN"] - CONSTANTS["NORMALIZED_TOLERANCE"]
    max_bound = CONSTANTS["NORMALIZED_MAX"] + CONSTANTS["NORMALIZED_TOLERANCE"]
    if min_value < min_bound or max_value > max_bound:
        raise ValueError(f"[A3] Normalized features must be in [0,1], found [{min_value}, {max_value}].")
    print(f"[A3] Normalized panel validated: shape={df.shape}, range=[{min_value:.4f}, {max_value:.4f}].")


def _build_year_condition(years: pd.Series) -> Tensor:
    """Convert years into one-hot condition tensor."""
    year_to_index = {year: idx for idx, year in enumerate(CONSTANTS["EXPECTED_YEARS"])}
    indices = [year_to_index[int(year)] for year in years.tolist()]
    return torch.nn.functional.one_hot(
        torch.tensor(indices, dtype=torch.long),
        num_classes=CONSTANTS["CONDITION_DIM"],
    ).float()


def _build_training_tensors(df: pd.DataFrame) -> tuple[Tensor, Tensor]:
    """Build CVAE feature and condition tensors."""
    x_tensor = torch.tensor(df[CONSTANTS["FEATURE_COLS"]].to_numpy(dtype=np.float32), dtype=torch.float32)
    condition_tensor = _build_year_condition(df["year"])
    return x_tensor, condition_tensor


def _cvae_loss(reconstruction: Tensor, x_values: Tensor, mu: Tensor, log_sigma_squared: Tensor) -> Tensor:
    """Compute L = mean(||x-xhat||^2 + beta * KL) with closed-form KL."""
    reconstruction_term = torch.sum((x_values - reconstruction) ** 2, dim=1)
    sigma_squared = torch.exp(log_sigma_squared)
    kl_term = CONSTANTS["BETA"] * 0.5 * torch.sum(
        (mu**2) + sigma_squared - log_sigma_squared - CONSTANTS["KL_OFFSET"],
        dim=1,
    )
    return torch.mean(reconstruction_term + kl_term)


def _train_cvae(x_tensor: Tensor, condition_tensor: Tensor) -> tuple[YearConditionedCVAE, list[dict[str, float]]]:
    """Train the year-conditioned CVAE with Adam."""
    model = YearConditionedCVAE()
    optimizer = torch.optim.Adam(model.parameters(), lr=CONSTANTS["LEARNING_RATE"])
    dataset = TensorDataset(x_tensor, condition_tensor)
    data_loader = DataLoader(dataset, batch_size=CONSTANTS["BATCH_SIZE"], shuffle=True)
    history: list[dict[str, float]] = []

    print(
        "[A3] Training CVAE "
        f"epochs={CONSTANTS['EPOCHS']}, batch_size={CONSTANTS['BATCH_SIZE']}, "
        f"lr={CONSTANTS['LEARNING_RATE']}, beta={CONSTANTS['BETA']}."
    )
    for epoch in range(1, CONSTANTS["EPOCHS"] + 1):
        model.train()
        total_loss = 0.0
        batch_count = 0
        for batch_x, batch_condition in data_loader:
            optimizer.zero_grad()
            reconstruction, mu, log_sigma_squared = model(batch_x, batch_condition)
            loss = _cvae_loss(reconstruction, batch_x, mu, log_sigma_squared)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach().item())
            batch_count += 1

        mean_loss = total_loss / batch_count
        history.append({"epoch": float(epoch), "loss": mean_loss})
        should_log = epoch == 1 or epoch == CONSTANTS["EPOCHS"] or epoch % CONSTANTS["LOG_INTERVAL"] == 0
        if should_log:
            print(f"[A3] Epoch {epoch:03d}/{CONSTANTS['EPOCHS']} - loss={mean_loss:.6f}")

    return model, history


def _create_real_variant_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Create variant 0 rows from observed normalized data."""
    rows: list[dict[str, Any]] = []
    for _, source_row in df.iterrows():
        row = {
            "county": source_row["county"],
            "year": int(source_row["year"]),
            "variant_id": CONSTANTS["REAL_VARIANT_ID"],
        }
        for feature in CONSTANTS["FEATURE_COLS"]:
            row[feature] = float(source_row[feature])
        rows.append(row)
    return rows


def _generate_synthetic_rows(model: YearConditionedCVAE, df: pd.DataFrame) -> list[dict[str, Any]]:
    """Generate four same-year synthetic rows for each real row."""
    model.eval()
    synthetic_rows: list[dict[str, Any]] = []
    x_tensor, condition_tensor = _build_training_tensors(df)

    with torch.no_grad():
        mu, log_sigma_squared = model.encode(x_tensor, condition_tensor)
        for row_idx, source_row in df.iterrows():
            source_condition = condition_tensor[row_idx].unsqueeze(0)
            source_mu = mu[row_idx].unsqueeze(0)
            source_log_sigma_squared = log_sigma_squared[row_idx].unsqueeze(0)

            for variant_id in range(
                CONSTANTS["FIRST_SYNTHETIC_VARIANT_ID"],
                CONSTANTS["SYNTHETIC_PER_REAL"] + CONSTANTS["FIRST_SYNTHETIC_VARIANT_ID"],
            ):
                z_value = model.reparameterize(source_mu, source_log_sigma_squared)
                decoded = model.decode(z_value, source_condition).squeeze(0)
                clipped = torch.clamp(
                    decoded,
                    min=CONSTANTS["NORMALIZED_MIN"],
                    max=CONSTANTS["NORMALIZED_MAX"],
                ).cpu().numpy()
                synthetic_row = {
                    "county": source_row["county"],
                    "year": int(source_row["year"]),
                    "variant_id": variant_id,
                }
                for feature_idx, feature in enumerate(CONSTANTS["FEATURE_COLS"]):
                    synthetic_row[feature] = float(clipped[feature_idx])
                synthetic_rows.append(synthetic_row)

    print(f"[A3] Generated synthetic rows: {len(synthetic_rows)}.")
    return synthetic_rows


def _build_augmented_dataframe(model: YearConditionedCVAE, df: pd.DataFrame) -> pd.DataFrame:
    """Build augmented dataframe with real and synthetic variants."""
    rows = _create_real_variant_rows(df)
    rows.extend(_generate_synthetic_rows(model, df))
    augmented_df = pd.DataFrame(rows)
    sort_columns = ["county", "year", "variant_id"]
    augmented_df = augmented_df.sort_values(sort_columns).reset_index(drop=True)
    _validate_augmented_dataframe(augmented_df)
    return augmented_df


def _validate_augmented_dataframe(df: pd.DataFrame) -> None:
    """Validate augmented rows, variants, and temporal grouping."""
    if len(df) != CONSTANTS["EXPECTED_AUGMENTED_ROWS"]:
        raise ValueError(f"[A3] Expected {CONSTANTS['EXPECTED_AUGMENTED_ROWS']} augmented rows, found {len(df)}.")

    years = sorted(df["year"].astype(int).unique().tolist())
    variants = sorted(df["variant_id"].astype(int).unique().tolist())
    if years != CONSTANTS["EXPECTED_YEARS"]:
        raise ValueError(f"[A3] Synthetic row year mismatch: {years}")
    if variants != CONSTANTS["EXPECTED_VARIANTS"]:
        raise ValueError(f"[A3] Expected variant ids {CONSTANTS['EXPECTED_VARIANTS']}, found {variants}.")

    rows_per_county = df.groupby("county").size()
    expected_rows_per_county = len(CONSTANTS["EXPECTED_VARIANTS"]) * len(CONSTANTS["EXPECTED_YEARS"])
    invalid_counties = rows_per_county[rows_per_county != expected_rows_per_county]
    if not invalid_counties.empty:
        raise ValueError(f"[A3] Invalid per-county row counts: {invalid_counties.to_dict()}")

    rows_per_county_year = df.groupby(["county", "year"]).size()
    invalid_groups = rows_per_county_year[rows_per_county_year != len(CONSTANTS["EXPECTED_VARIANTS"])]
    if not invalid_groups.empty:
        raise ValueError(f"[A3] Invalid per-county-year variant counts: {invalid_groups.to_dict()}")

    feature_values = df[CONSTANTS["FEATURE_COLS"]]
    min_value = float(feature_values.min().min())
    max_value = float(feature_values.max().max())
    min_bound = CONSTANTS["NORMALIZED_MIN"] - CONSTANTS["NORMALIZED_TOLERANCE"]
    max_bound = CONSTANTS["NORMALIZED_MAX"] + CONSTANTS["NORMALIZED_TOLERANCE"]
    if min_value < min_bound or max_value > max_bound:
        raise ValueError(f"[A3] Augmented features must be clipped to [0,1], found [{min_value}, {max_value}].")

    print(f"[A3] Augmented data validated: shape={df.shape}, range=[{min_value:.4f}, {max_value:.4f}].")
    print(
        f"[A3] Confirmed each county has {expected_rows_per_county} rows "
        f"and each county-year has {len(CONSTANTS['EXPECTED_VARIANTS'])} variants."
    )


def _safe_correlation_matrix(df: pd.DataFrame) -> np.ndarray:
    """Compute Pearson correlation matrix with finite-value cleanup."""
    matrix = df[CONSTANTS["FEATURE_COLS"]].corr().to_numpy()
    return np.nan_to_num(matrix, nan=0.0, posinf=0.0, neginf=0.0)


def _build_validation_summary(augmented_df: pd.DataFrame) -> dict[str, Any]:
    """Build per-year real-vs-synthetic validation diagnostics."""
    validation_summary: dict[str, Any] = {"per_year": {}}
    for year in CONSTANTS["EXPECTED_YEARS"]:
        real_df = augmented_df[
            (augmented_df["year"] == year) & (augmented_df["variant_id"] == CONSTANTS["REAL_VARIANT_ID"])
        ]
        synthetic_df = augmented_df[
            (augmented_df["year"] == year) & (augmented_df["variant_id"] != CONSTANTS["REAL_VARIANT_ID"])
        ]
        real_means = real_df[CONSTANTS["FEATURE_COLS"]].mean()
        synthetic_means = synthetic_df[CONSTANTS["FEATURE_COLS"]].mean()
        mean_abs_diff = float((real_means - synthetic_means).abs().mean())
        correlation_norm = float(
            np.linalg.norm(_safe_correlation_matrix(real_df) - _safe_correlation_matrix(synthetic_df), ord="fro")
        )
        validation_summary["per_year"][str(year)] = {
            "mean_abs_feature_diff": mean_abs_diff,
            "correlation_frobenius_norm": correlation_norm,
            "mean_diff_below_threshold": mean_abs_diff <= CONSTANTS["MEAN_ABS_DIFF_THRESHOLD"],
            "correlation_norm_below_threshold": correlation_norm < CONSTANTS["CORRELATION_NORM_THRESHOLD"],
        }
        status = "OK" if correlation_norm < CONSTANTS["CORRELATION_NORM_THRESHOLD"] else "WARN"
        print(
            f"[A3][{status}] Year {year}: "
            f"mean_abs_feature_diff={mean_abs_diff:.6f}, "
            f"corr_fro_norm={correlation_norm:.6f}"
        )

    monotonic_ok = all(
        county_df["year"].reset_index(drop=True).equals(
            county_df["year"].sort_values().reset_index(drop=True)
        )
        for _, county_df in augmented_df.groupby(["county", "variant_id"])
    )
    validation_summary["monotonic_county_variant_year_order"] = monotonic_ok
    validation_summary["year_values"] = sorted(augmented_df["year"].astype(int).unique().tolist())
    validation_summary["variant_values"] = sorted(augmented_df["variant_id"].astype(int).unique().tolist())
    print(f"[A3] Monotonic per-(county,variant) year ordering: {monotonic_ok}.")
    return validation_summary


def _passes_quality_gate(validation_summary: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check whether CVAE synthetic diagnostics satisfy configured thresholds."""
    failures: list[str] = []
    for year in CONSTANTS["EXPECTED_YEARS"]:
        row = validation_summary["per_year"][str(year)]
        if not row["mean_diff_below_threshold"]:
            failures.append(
                f"year={year} mean_abs_feature_diff={row['mean_abs_feature_diff']:.6f} "
                f"> {CONSTANTS['MEAN_ABS_DIFF_THRESHOLD']:.6f}"
            )
        if not row["correlation_norm_below_threshold"]:
            failures.append(
                f"year={year} corr_fro_norm={row['correlation_frobenius_norm']:.6f} "
                f">= {CONSTANTS['CORRELATION_NORM_THRESHOLD']:.6f}"
            )
    if not validation_summary["monotonic_county_variant_year_order"]:
        failures.append("non-monotonic year ordering within at least one (county, variant_id) sequence")
    return len(failures) == 0, failures


def _build_real_only_fallback_augmented(df: pd.DataFrame) -> pd.DataFrame:
    """Build safe augmented table by replicating real rows across synthetic variant ids."""
    rows: list[dict[str, Any]] = []
    for _, source_row in df.iterrows():
        for variant_id in CONSTANTS["EXPECTED_VARIANTS"]:
            row = {
                "county": source_row["county"],
                "year": int(source_row["year"]),
                "variant_id": int(variant_id),
            }
            for feature in CONSTANTS["FEATURE_COLS"]:
                row[feature] = float(source_row[feature])
            rows.append(row)
    fallback_df = pd.DataFrame(rows).sort_values(["county", "year", "variant_id"]).reset_index(drop=True)
    _validate_augmented_dataframe(fallback_df)
    return fallback_df


def _save_outputs(
    model: YearConditionedCVAE,
    history: list[dict[str, float]],
    augmented_df: pd.DataFrame,
    validation_summary: dict[str, Any],
) -> None:
    """Save augmented data, model weights, and validation artifacts."""
    CONSTANTS["DATA_DIR"].mkdir(parents=True, exist_ok=True)
    CONSTANTS["ARTIFACTS_DIR"].mkdir(parents=True, exist_ok=True)
    CONSTANTS["MODELS_DIR"].mkdir(parents=True, exist_ok=True)

    augmented_path = CONSTANTS["DATA_DIR"] / CONSTANTS["AUGMENTED_FILENAME"]
    model_path = CONSTANTS["MODELS_DIR"] / CONSTANTS["MODEL_FILENAME"]
    history_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["HISTORY_FILENAME"]
    validation_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["VALIDATION_FILENAME"]

    augmented_df.to_csv(augmented_path, index=False)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "constants": {
                key: value
                for key, value in CONSTANTS.items()
                if isinstance(value, (str, int, float, list, tuple))
            },
        },
        model_path,
    )
    history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    validation_path.write_text(json.dumps(validation_summary, indent=2), encoding="utf-8")

    print(f"[A3] Saved augmented data: {augmented_path}")
    print(f"[A3] Saved CVAE model artifact: {model_path}")
    print(f"[A3] Saved training history: {history_path}")
    print(f"[A3] Saved validation summary: {validation_path}")


def run_cvae_augmentation() -> pd.DataFrame:
    """Run Phase A3 CVAE training, augmentation, validation, and persistence."""
    _print_phase_header()
    _set_random_seeds()
    normalized_df = _load_normalized_panel()
    x_tensor, condition_tensor = _build_training_tensors(normalized_df)
    model, history = _train_cvae(x_tensor, condition_tensor)
    generated_augmented_df = _build_augmented_dataframe(model, normalized_df)
    initial_validation = _build_validation_summary(generated_augmented_df)
    gate_passed, gate_failures = _passes_quality_gate(initial_validation)
    fallback_used = not gate_passed
    if fallback_used:
        print("[A3][GATE] CVAE synthetic quality gate failed; switching to safe real-only fallback variants.")
        for failure in gate_failures:
            print(f"[A3][GATE] {failure}")
        augmented_df = _build_real_only_fallback_augmented(normalized_df)
    else:
        print("[A3][GATE] CVAE synthetic quality gate passed.")
        augmented_df = generated_augmented_df
    final_validation = _build_validation_summary(augmented_df)
    validation_summary = {
        "quality_gate": {
            "passed": gate_passed,
            "fallback_used": fallback_used,
            "failures": gate_failures,
            "thresholds": {
                "mean_abs_feature_diff_max": CONSTANTS["MEAN_ABS_DIFF_THRESHOLD"],
                "correlation_frobenius_norm_max": CONSTANTS["CORRELATION_NORM_THRESHOLD"],
            },
        },
        "initial_validation": initial_validation,
        "final_validation": final_validation,
    }
    _save_outputs(model, history, augmented_df, validation_summary)
    print(f"[A3] Completed successfully. Final augmented shape: {augmented_df.shape}")
    return augmented_df

