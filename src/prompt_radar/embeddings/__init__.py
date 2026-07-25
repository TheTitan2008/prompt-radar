"""Embedding-service implementations."""

from prompt_radar.embeddings.base import EmbeddingService
from prompt_radar.embeddings.fake import HashingEmbeddingService

__all__ = ["EmbeddingService", "HashingEmbeddingService"]

