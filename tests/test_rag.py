from __future__ import annotations

from prompt_radar.attachments.base import AttachmentExtraction, ExtractedSection
from prompt_radar.retrieval.rag import retrieve_top_k

from conftest import TinyEmbeddingService


def test_rag_returns_top_five_or_less() -> None:
    extraction = AttachmentExtraction(
        attachment_id="a1",
        filename="x.txt",
        extraction_status="success",
        sections=[
            ExtractedSection("a1", "x.txt", "file", " ".join(["почта"] * 50))
        ],
    )
    result = retrieve_top_k(
        "письма почты",
        [extraction],
        TinyEmbeddingService(),
        chunk_size=5,
        overlap=1,
        top_k=5,
    )
    assert len(result) == 5


def test_rag_ranks_relevant_chunk_first() -> None:
    extraction = AttachmentExtraction(
        attachment_id="a1",
        filename="x.txt",
        extraction_status="success",
        sections=[
            ExtractedSection("a1", "x.txt", "irrelevant", "стеклянный кит"),
            ExtractedSection("a1", "x.txt", "relevant", "важные письма почты"),
        ],
    )
    result = retrieve_top_k(
        "найди письма",
        [extraction],
        TinyEmbeddingService(),
        chunk_size=20,
        overlap=0,
        top_k=2,
    )
    assert result[0].locator == "relevant"

