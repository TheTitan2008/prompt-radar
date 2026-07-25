"""Attachment-wide Top-K retrieval."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from prompt_radar.attachments.base import AttachmentExtraction
from prompt_radar.embeddings.base import EmbeddingService
from prompt_radar.preprocessing.chunker import chunk_text
from prompt_radar.retrieval.cosine import cosine_matrix


@dataclass
class RetrievedChunk:
    """One scored attachment chunk with source provenance."""

    chunk_id: str
    attachment_id: str
    filename: str
    locator: str
    token_start: int
    token_end: int
    similarity_score: float
    text: str

    def to_dict(self) -> dict[str, object]:
        """Serialize this retrieval record."""
        return asdict(self)


def retrieve_top_k(
    query: str,
    extractions: list[AttachmentExtraction],
    embeddings: EmbeddingService,
    *,
    chunk_size: int,
    overlap: int,
    top_k: int,
) -> list[RetrievedChunk]:
    """Rank chunks from all attachments against the user goal."""
    candidates: list[RetrievedChunk] = []
    for extraction in extractions:
        for section in extraction.sections:
            chunks = chunk_text(
                section.text,
                embeddings.tokenizer,
                chunk_size=chunk_size,
                overlap=overlap,
                prefix=f"{section.attachment_id}:{section.locator}",
            )
            candidates.extend(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    attachment_id=section.attachment_id,
                    filename=section.filename,
                    locator=section.locator,
                    token_start=chunk.token_start,
                    token_end=chunk.token_end,
                    similarity_score=0.0,
                    text=chunk.text,
                )
                for chunk in chunks
            )
    if not candidates or top_k <= 0:
        return []
    query_vector = embeddings.encode([query], mode="query")
    document_vectors = embeddings.encode(
        [candidate.text for candidate in candidates], mode="document"
    )
    scores = cosine_matrix(query_vector, document_vectors)[0]
    for candidate, score in zip(candidates, scores, strict=True):
        candidate.similarity_score = float(score)
    candidates.sort(
        key=lambda item: (-item.similarity_score, item.chunk_id)
    )
    return candidates[:top_k]

