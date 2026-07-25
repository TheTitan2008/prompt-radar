"""Bounded overlapping extractive chunking."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_radar.preprocessing.tokenizer import Tokenizer


@dataclass(frozen=True)
class TextChunk:
    """One token-bounded text chunk."""

    chunk_id: str
    text: str
    token_start: int
    token_end: int


def chunk_text(
    text: str,
    tokenizer: Tokenizer,
    *,
    chunk_size: int,
    overlap: int,
    prefix: str = "chunk",
) -> list[TextChunk]:
    """Split text with a fixed token overlap and stable chunk IDs."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")
    chunks: list[TextChunk] = []
    optimized = getattr(tokenizer, "chunk_token_spans", None)
    if callable(optimized):
        spans = optimized(text, chunk_size=chunk_size, overlap=overlap)
        for index, (chunk, start, end) in enumerate(spans):
            chunks.append(
                TextChunk(
                    chunk_id=f"{prefix}:{index}",
                    text=chunk,
                    token_start=start,
                    token_end=end,
                )
            )
        return chunks
    tokens = tokenizer.split_tokens(text)
    if not tokens:
        return []
    step = chunk_size - overlap
    for index, start in enumerate(range(0, len(tokens), step)):
        end = min(start + chunk_size, len(tokens))
        chunks.append(
            TextChunk(
                chunk_id=f"{prefix}:{index}",
                text=" ".join(tokens[start:end]),
                token_start=start,
                token_end=end,
            )
        )
        if end >= len(tokens):
            break
    return chunks
