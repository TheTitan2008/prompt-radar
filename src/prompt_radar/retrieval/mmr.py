"""Minimal Maximal Marginal Relevance selection."""

from __future__ import annotations

import numpy as np

from prompt_radar.retrieval.cosine import cosine_matrix


def maximal_marginal_relevance(
    query: np.ndarray,
    candidates: np.ndarray,
    *,
    limit: int,
    diversity: float = 0.3,
) -> list[int]:
    """Choose relevant, non-duplicate candidate indexes."""
    if len(candidates) == 0 or limit <= 0:
        return []
    relevance = cosine_matrix(query.reshape(1, -1), candidates)[0]
    pairwise = cosine_matrix(candidates, candidates)
    selected: list[int] = []
    remaining = set(range(len(candidates)))
    while remaining and len(selected) < limit:
        best = max(
            remaining,
            key=lambda index: (
                (1.0 - diversity) * relevance[index]
                - diversity
                * max((pairwise[index, chosen] for chosen in selected), default=0.0),
                -index,
            ),
        )
        selected.append(best)
        remaining.remove(best)
    return selected

