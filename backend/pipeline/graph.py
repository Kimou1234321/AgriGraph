"""Phase A6 spatial graph construction and normalization."""

from __future__ import annotations

import math
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import torch

CONSTANTS: dict[str, Any] = {
    "PHASE": "A6",
    "ARTIFACTS_DIR": Path(__file__).resolve().parents[1] / "artifacts",
    "K_NEIGHBORS": 3,
    "EARTH_RADIUS_KM": 6371.0,
    "EPSILON": 1e-8,
    "ADJACENCY_FILENAME": "adjacency_matrix.npy",
    "NORMALIZED_ADJACENCY_FILENAME": "normalized_adjacency.npy",
    "EDGE_INDEX_FILENAME": "edge_index.pt",
    "COUNTIES_FILENAME": "graph_counties.pkl",
    "COUNTY_CENTROIDS": {
        "Carlow": (52.836, -6.926),
        "Cavan": (53.990, -7.360),
        "Clare": (52.893, -8.981),
        "Cork": (51.897, -8.475),
        "Donegal": (54.654, -8.110),
        "Dublin": (53.350, -6.266),
        "Galway": (53.274, -8.988),
        "Kerry": (52.156, -9.566),
        "Kildare": (53.157, -6.909),
        "Kilkenny": (52.649, -7.252),
        "Laois": (52.994, -7.332),
        "Leitrim": (54.124, -8.001),
        "Limerick": (52.502, -8.623),
        "Longford": (53.727, -7.795),
        "Louth": (53.924, -6.486),
        "Mayo": (53.845, -9.299),
        "Meath": (53.605, -6.656),
        "Monaghan": (54.249, -6.968),
        "Offaly": (53.235, -7.712),
        "Roscommon": (53.627, -8.182),
        "Sligo": (54.277, -8.476),
        "Tipperary": (52.474, -7.952),
        "Waterford": (52.259, -7.110),
        "Westmeath": (53.534, -7.462),
        "Wexford": (52.336, -6.463),
        "Wicklow": (52.981, -6.364),
    },
}


def _print_phase_header() -> None:
    """Print a readable phase header."""
    print("\n" + "=" * 72)
    print(f"[{CONSTANTS['PHASE']}] SPATIAL GRAPH CONSTRUCTION")
    print("=" * 72)


def _ordered_counties() -> list[str]:
    """Return deterministic county order for node indexing."""
    return sorted(CONSTANTS["COUNTY_CENTROIDS"].keys())


def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in kilometers using haversine."""
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad
    a_value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * CONSTANTS["EARTH_RADIUS_KM"] * math.asin(math.sqrt(a_value))


def _distance_matrix(counties: list[str]) -> np.ndarray:
    """Build pairwise county geodesic distance matrix."""
    node_count = len(counties)
    distances = np.zeros((node_count, node_count), dtype=np.float64)
    for i, county_i in enumerate(counties):
        lat_i, lon_i = CONSTANTS["COUNTY_CENTROIDS"][county_i]
        for j, county_j in enumerate(counties):
            if i == j:
                continue
            lat_j, lon_j = CONSTANTS["COUNTY_CENTROIDS"][county_j]
            distances[i, j] = _haversine_distance_km(lat_i, lon_i, lat_j, lon_j)
    return distances


def _knn_adjacency(distances: np.ndarray, k_neighbors: int) -> np.ndarray:
    """Build symmetric k-NN adjacency without self-loops."""
    node_count = distances.shape[0]
    adjacency = np.zeros((node_count, node_count), dtype=np.float64)
    for i in range(node_count):
        neighbor_indices = np.argsort(distances[i])[1 : k_neighbors + 1]
        adjacency[i, neighbor_indices] = 1.0
    adjacency = np.where((adjacency + adjacency.T) > 0, 1.0, 0.0)
    np.fill_diagonal(adjacency, 0.0)
    return adjacency


def _normalize_adjacency(adjacency: np.ndarray) -> np.ndarray:
    """Compute A_tilde = D_hat^-0.5 @ (A + I) @ D_hat^-0.5."""
    node_count = adjacency.shape[0]
    adjacency_hat = adjacency + np.eye(node_count, dtype=np.float64)
    degree_hat = np.sum(adjacency_hat, axis=1)
    degree_inv_sqrt = np.diag(1.0 / np.sqrt(np.maximum(degree_hat, CONSTANTS["EPSILON"])))
    return degree_inv_sqrt @ adjacency_hat @ degree_inv_sqrt


def _edge_index_from_adjacency(adjacency: np.ndarray) -> torch.Tensor:
    """Build PyG-compatible edge_index with directed pairs."""
    src_nodes, dst_nodes = np.where(adjacency > 0.0)
    edge_index = np.vstack([src_nodes, dst_nodes]).astype(np.int64)
    return torch.tensor(edge_index, dtype=torch.long)


def _save_artifacts(
    counties: list[str],
    adjacency: np.ndarray,
    normalized_adjacency: np.ndarray,
    edge_index: torch.Tensor,
) -> None:
    """Persist adjacency, normalized adjacency, edge index, and county order."""
    CONSTANTS["ARTIFACTS_DIR"].mkdir(parents=True, exist_ok=True)
    adjacency_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["ADJACENCY_FILENAME"]
    normalized_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["NORMALIZED_ADJACENCY_FILENAME"]
    edge_index_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["EDGE_INDEX_FILENAME"]
    counties_path = CONSTANTS["ARTIFACTS_DIR"] / CONSTANTS["COUNTIES_FILENAME"]

    np.save(adjacency_path, adjacency)
    np.save(normalized_path, normalized_adjacency)
    torch.save(edge_index, edge_index_path)
    with counties_path.open("wb") as file:
        pickle.dump(counties, file)

    print(f"[A6] Saved artifact: {adjacency_path}")
    print(f"[A6] Saved artifact: {normalized_path}")
    print(f"[A6] Saved artifact: {edge_index_path}")
    print(f"[A6] Saved artifact: {counties_path}")


def run_graph_construction() -> None:
    """Run Phase A6 graph construction and persist graph artifacts."""
    _print_phase_header()
    counties = _ordered_counties()
    distances = _distance_matrix(counties)
    adjacency = _knn_adjacency(distances=distances, k_neighbors=CONSTANTS["K_NEIGHBORS"])
    normalized_adjacency = _normalize_adjacency(adjacency)
    edge_index = _edge_index_from_adjacency(adjacency)

    undirected_edges = int(np.sum(adjacency) / 2)
    print(f"[A6] Node count: {len(counties)}")
    print(f"[A6] Undirected edge count: {undirected_edges}")
    print(f"[A6] Directed edge_index shape: {tuple(edge_index.shape)}")
    print(f"[A6] Normalized adjacency shape: {normalized_adjacency.shape}")
    print(f"[A6] Normalized adjacency symmetric: {np.allclose(normalized_adjacency, normalized_adjacency.T)}")

    _save_artifacts(
        counties=counties,
        adjacency=adjacency,
        normalized_adjacency=normalized_adjacency,
        edge_index=edge_index,
    )
    print("[A6] Completed successfully.")

