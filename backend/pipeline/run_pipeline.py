"""Pipeline orchestrator scaffold for phases A1-A10."""

from backend.pipeline.counterfactual import run_counterfactual
from backend.pipeline.data_loader import run_data_loader
from backend.pipeline.forecast import run_forecast
from backend.pipeline.graph import run_graph_construction
from backend.pipeline.pca_pillars import run_pca_and_scoring
from backend.pipeline.preprocessing import run_preprocessing
from backend.pipeline.stgnn import run_stgnn_training
from backend.pipeline.uncertainty import run_uncertainty
from backend.pipeline.vae import run_cvae_augmentation

CONSTANTS: dict[str, tuple[str, ...]] = {
    "PIPELINE_ORDER": ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A7b", "A8", "A9", "A10")
}


def run_pipeline() -> None:
    """Run all pipeline phase scaffolds in order."""
    run_data_loader()
    run_preprocessing()
    run_cvae_augmentation()
    run_pca_and_scoring()
    run_graph_construction()
    run_stgnn_training()
    run_forecast()
    run_uncertainty()
    run_counterfactual()


if __name__ == "__main__":
    run_pipeline()

