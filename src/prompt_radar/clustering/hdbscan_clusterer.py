"""HDBSCAN clustering of normalized run-level embeddings."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from prompt_radar.config import ClusteringConfig


@dataclass
class ClusterAssignment:
    """One HDBSCAN assignment."""

    cluster_id: int
    membership_probability: float
    outlier_score: float


@dataclass
class ClusteringResult:
    """Residual clustering result with an explicit small-data status."""

    status: str
    assignments: list[ClusterAssignment]
    parameters: dict[str, object]


def cluster_residual(
    vectors: np.ndarray, config: ClusteringConfig
) -> ClusteringResult:
    """Run UMAP (when safe) and HDBSCAN, or return an explanatory status."""
    sample_count = len(vectors)
    params: dict[str, object] = config.model_dump()
    if sample_count < 4:
        return ClusteringResult(
            status="insufficient_data_for_clustering",
            assignments=[
                ClusterAssignment(-1, 0.0, 1.0) for _ in range(sample_count)
            ],
            parameters=params,
        )
    try:
        import hdbscan
    except ImportError:
        return ClusteringResult(
            status="hdbscan_dependency_unavailable",
            assignments=[
                ClusterAssignment(-1, 0.0, 1.0) for _ in range(sample_count)
            ],
            parameters=params,
        )
    data = vectors.astype(np.float32, copy=False)
    norms = np.linalg.norm(data, axis=1, keepdims=True)
    data = np.divide(data, norms, out=np.zeros_like(data), where=norms > 0)
    if config.use_umap and sample_count >= 8:
        try:
            import umap

            components = min(config.umap_components, sample_count - 2)
            neighbors = min(config.umap_neighbors, sample_count - 1)
            reducer = umap.UMAP(
                n_components=max(2, components),
                n_neighbors=max(2, neighbors),
                min_dist=config.umap_min_dist,
                metric="cosine",
                random_state=config.random_seed,
                transform_seed=config.random_seed,
            )
            data = reducer.fit_transform(data)
            params["effective_umap_components"] = max(2, components)
            params["effective_umap_neighbors"] = max(2, neighbors)
        except (ImportError, ValueError):
            params["umap_fallback"] = "normalized_embedding_space"
    min_cluster_size = min(max(2, config.min_cluster_size), sample_count)
    min_samples = (
        1
        if sample_count < 2 * min_cluster_size
        else min(max(1, config.min_samples), min_cluster_size)
    )
    params["effective_min_cluster_size"] = min_cluster_size
    params["effective_min_samples"] = min_samples
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="euclidean",
        cluster_selection_method=config.cluster_selection_method,
        allow_single_cluster=True,
        prediction_data=False,
    )
    labels = clusterer.fit_predict(data)
    probabilities = getattr(
        clusterer, "probabilities_", np.zeros(sample_count, dtype=float)
    )
    outliers = getattr(
        clusterer, "outlier_scores_", np.ones(sample_count, dtype=float)
    )
    assignments = [
        ClusterAssignment(int(label), float(probability), float(outlier))
        for label, probability, outlier in zip(
            labels, probabilities, outliers, strict=True
        )
    ]
    return ClusteringResult(
        status="clustered",
        assignments=assignments,
        parameters=params,
    )
