"""Deterministic offline embedding used by tests and mechanical demos."""

from __future__ import annotations

import hashlib
import re

import numpy as np

from prompt_radar.embeddings.base import EncodingMode
from prompt_radar.preprocessing.tokenizer import WhitespaceTokenizer

_WORDS = re.compile(r"\w+", re.UNICODE)


class HashingEmbeddingService:
    """Feature-hashing embedding with no model, network or learned weights."""

    model_id = "fake/hashing"
    model_revision = "1"
    preprocessing_version = "1.0.0"
    device = "cpu"
    tokenizer = WhitespaceTokenizer()

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def _features(self, text: str) -> list[str]:
        words = [word.casefold() for word in _WORDS.findall(text)]
        features = words[:]
        features.extend(
            f"{words[index]}::{words[index + 1]}"
            for index in range(len(words) - 1)
        )
        for word in words:
            padded = f"^{word}$"
            features.extend(
                padded[index : index + 3]
                for index in range(max(0, len(padded) - 2))
            )
        return features

    def encode(
        self, texts: list[str], *, mode: EncodingMode = "document"
    ) -> np.ndarray:
        """Hash lexical and character features into normalized float vectors."""
        matrix = np.zeros((len(texts), self.dimensions), dtype=np.float32)
        for row, text in enumerate(texts):
            for feature in self._features(text):
                digest = hashlib.blake2b(
                    feature.encode("utf-8"), digest_size=8
                ).digest()
                value = int.from_bytes(digest, "little")
                column = value % self.dimensions
                sign = 1.0 if value & (1 << 63) else -1.0
                matrix[row, column] += sign
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        np.divide(matrix, norms, out=matrix, where=norms > 0)
        return matrix

