"""Segmentation of messages that have no explicit run_id."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import timedelta

import numpy as np

from prompt_radar.config import FallbackConfig
from prompt_radar.embeddings.base import EmbeddingService
from prompt_radar.models import Message


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denominator) if denominator else 0.0


def segment_missing_runs(
    messages: list[Message],
    config: FallbackConfig,
    embeddings: EmbeddingService,
) -> dict[str, list[Message]]:
    """Create deterministic fallback segments within each conversation."""
    by_conversation: dict[str, list[Message]] = defaultdict(list)
    for message in messages:
        if message.run_id is None:
            by_conversation[message.conversation_id].append(message)
    result: dict[str, list[Message]] = {}
    for conversation_id, items in by_conversation.items():
        items.sort(
            key=lambda item: (
                item.sequence_number,
                item.created_at,
                item.message_id,
            )
        )
        segments: list[list[Message]] = []
        current: list[Message] = []
        last_user: Message | None = None
        for message in items:
            if message.role != "user":
                if current:
                    current.append(message)
                continue
            start_new = not current
            lowered = message.content.casefold()
            dependent = any(phrase in lowered for phrase in config.dependent_phrases)
            topic_change = any(
                phrase in lowered for phrase in config.topic_change_phrases
            )
            if last_user and not start_new:
                gap = message.created_at - last_user.created_at
                if topic_change or gap > timedelta(minutes=config.max_gap_minutes):
                    start_new = True
                elif not dependent:
                    matrix = embeddings.encode(
                        [last_user.content, message.content], mode="query"
                    )
                    start_new = (
                        _cosine(matrix[0], matrix[1])
                        < config.adjacent_similarity_threshold
                    )
            if start_new and current:
                segments.append(current)
                current = []
            current.append(message)
            last_user = message
        if current:
            segments.append(current)
        for index, segment in enumerate(segments):
            digest = hashlib.sha256(
                f"{conversation_id}:{index}:{segment[0].message_id}".encode("utf-8")
            ).hexdigest()[:12]
            result[f"fallback:{conversation_id}:{digest}"] = segment
    return result

