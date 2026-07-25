"""Revision-aware filesystem embedding cache."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from prompt_radar.io_utils import atomic_write_bytes


def embedding_cache_key(
    *,
    model_id: str,
    model_revision: str,
    tokenizer_version: str,
    preprocessing_version: str,
    encoding_mode: str,
    text: str,
) -> str:
    """Build the required revision- and preprocessing-aware SHA-256 key."""
    payload = "\0".join(
        (
            model_id,
            model_revision,
            tokenizer_version,
            preprocessing_version,
            encoding_mode,
            text,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class EmbeddingCache:
    """Small per-vector `.npy` cache with atomic writes."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def get(self, key: str) -> np.ndarray | None:
        """Load one cached vector or return `None`."""
        path = self.root / key[:2] / f"{key}.npy"
        if not path.is_file():
            return None
        try:
            return np.load(path, allow_pickle=False).astype(np.float32, copy=False)
        except (OSError, ValueError):
            return None

    def put(self, key: str, vector: np.ndarray) -> None:
        """Atomically store one vector."""
        import io

        buffer = io.BytesIO()
        np.save(buffer, vector.astype(np.float32, copy=False), allow_pickle=False)
        atomic_write_bytes(self.root / key[:2] / f"{key}.npy", buffer.getvalue())

