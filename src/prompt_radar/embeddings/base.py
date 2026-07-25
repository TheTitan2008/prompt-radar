"""Embedding service protocol."""

from __future__ import annotations

from typing import Literal, Protocol

import numpy as np

from prompt_radar.preprocessing.tokenizer import Tokenizer

EncodingMode = Literal["query", "document"]


class EmbeddingService(Protocol):
    """Model-agnostic normalized embedding interface."""

    model_id: str
    model_revision: str
    preprocessing_version: str
    tokenizer: Tokenizer
    device: str

    def encode(
        self, texts: list[str], *, mode: EncodingMode = "document"
    ) -> np.ndarray:
        """Return a two-dimensional float32 array of L2-normalized vectors."""

