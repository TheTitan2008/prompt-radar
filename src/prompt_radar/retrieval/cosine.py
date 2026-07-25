"""Cosine similarity helpers for normalized embeddings."""

from __future__ import annotations

import numpy as np


def cosine_matrix(queries: np.ndarray, documents: np.ndarray) -> np.ndarray:
    """Return cosine scores while safely normalizing arbitrary input arrays."""
    if queries.ndim != 2 or documents.ndim != 2:
        raise ValueError("cosine_matrix expects two 2D arrays")
    q_norm = np.linalg.norm(queries, axis=1, keepdims=True)
    d_norm = np.linalg.norm(documents, axis=1, keepdims=True)
    safe_q = np.divide(
        queries, q_norm, out=np.zeros_like(queries), where=q_norm > 0
    )
    safe_d = np.divide(
        documents, d_norm, out=np.zeros_like(documents), where=d_norm > 0
    )
    return safe_q @ safe_d.T
