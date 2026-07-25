from __future__ import annotations

import numpy as np
import pytest

from prompt_radar.clustering.hdbscan_clusterer import cluster_residual
from prompt_radar.config import ClusteringConfig

hdbscan = pytest.importorskip("hdbscan")


def test_hdbscan_groups_obvious_clusters_and_marks_noise() -> None:
    vectors = np.asarray(
        [
            [1.0, 0.00],
            [0.99, 0.01],
            [0.98, -0.01],
            [0.0, 1.00],
            [0.01, 0.99],
            [-0.01, 0.98],
            [-1.0, -1.0],
        ],
        dtype=np.float32,
    )
    result = cluster_residual(
        vectors,
        ClusteringConfig(
            use_umap=False,
            min_cluster_size=2,
            min_samples=1,
        ),
    )
    labels = [item.cluster_id for item in result.assignments]
    assert labels[0] == labels[1] == labels[2] >= 0
    assert labels[3] == labels[4] == labels[5] >= 0
    assert labels[0] != labels[3]
    assert labels[-1] == -1


def test_small_dataset_has_clear_status() -> None:
    result = cluster_residual(
        np.eye(3, dtype=np.float32), ClusteringConfig(use_umap=False)
    )
    assert result.status == "insufficient_data_for_clustering"
    assert all(item.cluster_id == -1 for item in result.assignments)

