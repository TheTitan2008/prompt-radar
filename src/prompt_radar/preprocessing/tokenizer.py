"""Tokenizer abstraction used by routing and chunking."""

from __future__ import annotations

import re
from typing import Protocol


class Tokenizer(Protocol):
    """Minimal tokenizer contract hidden behind the embedding service."""

    @property
    def version(self) -> str:
        """Return a stable tokenizer version identifier."""

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""

    def split_tokens(self, text: str) -> list[str]:
        """Split text into reversible-enough units for extractive chunks."""


class WhitespaceTokenizer:
    """Deterministic unit-test tokenizer that preserves punctuation tokens."""

    version = "whitespace-v1"
    _pattern = re.compile(r"\w+|[^\w\s]", re.UNICODE)

    def count_tokens(self, text: str) -> int:
        """Count regex tokens."""
        return len(self._pattern.findall(text))

    def split_tokens(self, text: str) -> list[str]:
        """Split to regex tokens."""
        return self._pattern.findall(text)

