"""Medoid-based representative and boundary example selection."""

from __future__ import annotations

import numpy as np


def representative_indexes(
    vectors: np.ndarray,
    *,
    representative_count: int,
    boundary_count: int,
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Return closest-to-medoid and farthest boundary indexes."""
    if len(vectors) == 0:
        return [], []
    normalized = vectors.astype(np.float32, copy=True)
    norms = np.linalg.norm(normalized, axis=1, keepdims=True)
    np.divide(normalized, norms, out=normalized, where=norms > 0)
    pairwise = 1.0 - normalized @ normalized.T
    medoid = int(np.argmin(pairwise.sum(axis=1)))
    distances = pairwise[medoid]
    order = np.argsort(distances)
    representatives = [
        (int(index), float(distances[index]))
        for index in order[:representative_count]
    ]
    representative_ids = {index for index, _ in representatives}
    boundaries = [
        (int(index), float(distances[index]))
        for index in reversed(order.tolist())
        if int(index) not in representative_ids
    ][:boundary_count]
    return representatives, boundaries

