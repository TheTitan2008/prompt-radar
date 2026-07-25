"""Pinned offline-capable Qwen3 embedding service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from prompt_radar.config import PipelineConfig
from prompt_radar.embeddings.base import EncodingMode
from prompt_radar.embeddings.cache import EmbeddingCache, embedding_cache_key
from prompt_radar.errors import ModelUnavailableError


class _QwenTokenizerAdapter:
    def __init__(self, tokenizer: Any, version: str) -> None:
        self._tokenizer = tokenizer
        self.version = version

    def count_tokens(self, text: str) -> int:
        # Tokenizers warn when an input exceeds the model's forward-pass
        # context even though routing only needs a count and never embeds the
        # raw long payload. Count bounded character windows with the same
        # tokenizer to avoid implying that the full payload will be forwarded.
        window_chars = 20_000
        if len(text) <= window_chars:
            return len(self._tokenizer.encode(text, add_special_tokens=False))
        return sum(
            len(
                self._tokenizer.encode(
                    text[start : start + window_chars],
                    add_special_tokens=False,
                )
            )
            for start in range(0, len(text), window_chars)
        )

    def split_tokens(self, text: str) -> list[str]:
        token_ids = self._tokenizer.encode(
            text, add_special_tokens=False, verbose=False
        )
        return [
            self._tokenizer.decode([token_id], skip_special_tokens=False)
            for token_id in token_ids
        ]

    def chunk_token_spans(
        self, text: str, *, chunk_size: int, overlap: int
    ) -> list[tuple[str, int, int]]:
        """Decode token spans in bulk instead of decoding every token."""
        token_ids = self._tokenizer.encode(
            text, add_special_tokens=False, verbose=False
        )
        if not token_ids:
            return []
        step = chunk_size - overlap
        spans: list[tuple[str, int, int]] = []
        for start in range(0, len(token_ids), step):
            end = min(start + chunk_size, len(token_ids))
            spans.append(
                (
                    self._tokenizer.decode(
                        token_ids[start:end],
                        skip_special_tokens=False,
                    ),
                    start,
                    end,
                )
            )
            if end >= len(token_ids):
                break
        return spans


class QwenEmbeddingService:
    """Load pinned Qwen3 embeddings locally and never expose torch tensors."""

    def __init__(self, config: PipelineConfig, *, offline: bool = True) -> None:
        self.model_id = config.model.id
        self.model_revision = config.model.revision
        self.preprocessing_version = config.preprocessing_version
        self._query_instruction = config.model.query_instruction
        self._cache_dir = Path(config.model.cache_dir)
        self._vector_cache = EmbeddingCache(Path(".cache/embeddings"))
        if offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ModelUnavailableError(
                "ML dependencies are not installed. Run "
                'python -m pip install -e ".[ml,attachments]".'
            ) from exc
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        batch = (
            config.resources.embedding_batch_size_cuda
            if self.device == "cuda"
            else config.resources.embedding_batch_size_cpu
        )
        self._batch_size = batch
        try:
            self._model = SentenceTransformer(
                self.model_id,
                revision=self.model_revision,
                cache_folder=str(self._cache_dir),
                device=self.device,
                local_files_only=offline,
                trust_remote_code=True,
            )
        except Exception as exc:
            raise ModelUnavailableError(
                "Pinned Qwen model is not available in the local cache. Run "
                "`python -m prompt_radar.cli download-model` while online, "
                "then repeat with `--offline`."
            ) from exc
        tokenizer_version = (
            f"{self.model_id}@{self.model_revision}:"
            f"{self._model.tokenizer.__class__.__name__}"
        )
        self.tokenizer = _QwenTokenizerAdapter(
            self._model.tokenizer, tokenizer_version
        )

    def encode(
        self, texts: list[str], *, mode: EncodingMode = "document"
    ) -> np.ndarray:
        """Encode in batches with an on-disk revision-aware cache."""
        if not texts:
            dimension = self._model.get_sentence_embedding_dimension()
            return np.empty((0, dimension), dtype=np.float32)
        vectors: list[np.ndarray | None] = [None] * len(texts)
        missing_texts: list[str] = []
        missing_indices: list[int] = []
        keys: list[str] = []
        for index, text in enumerate(texts):
            encoded_text = (
                self._query_instruction + text if mode == "query" else text
            )
            key = embedding_cache_key(
                model_id=self.model_id,
                model_revision=self.model_revision,
                tokenizer_version=self.tokenizer.version,
                preprocessing_version=self.preprocessing_version,
                encoding_mode=mode,
                text=encoded_text,
            )
            keys.append(key)
            cached = self._vector_cache.get(key)
            if cached is None:
                missing_indices.append(index)
                missing_texts.append(encoded_text)
            else:
                vectors[index] = cached
        if missing_texts:
            encoded = self._model.encode(
                missing_texts,
                batch_size=self._batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            ).astype(np.float32, copy=False)
            for source_index, vector in zip(missing_indices, encoded, strict=True):
                vectors[source_index] = vector
                self._vector_cache.put(keys[source_index], vector)
        return np.stack([vector for vector in vectors if vector is not None]).astype(
            np.float32, copy=False
        )


def download_model(config: PipelineConfig) -> Path:
    """Explicitly download the pinned snapshot and return its local path."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise ModelUnavailableError(
            "ML dependencies are not installed. Run "
            'python -m pip install -e ".[ml]".'
        ) from exc
    local = snapshot_download(
        repo_id=config.model.id,
        revision=config.model.revision,
        cache_dir=config.model.cache_dir,
        local_files_only=False,
    )
    return Path(local)
