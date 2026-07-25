from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from prompt_radar.preprocessing.tokenizer import WhitespaceTokenizer


class TinyEmbeddingService:
    model_id = "test/tiny"
    model_revision = "1"
    preprocessing_version = "test-1"
    device = "cpu"
    tokenizer = WhitespaceTokenizer()

    def encode(self, texts: list[str], *, mode: str = "document") -> np.ndarray:
        vectors = []
        for text in texts:
            lowered = text.casefold()
            vector = np.asarray(
                [
                    float(any(word in lowered for word in ("почт", "email", "письм"))),
                    float(any(word in lowered for word in ("jira", "тикет", "задач"))),
                    float(any(word in lowered for word in ("календар", "встреч", "слот"))),
                    float(any(word in lowered for word in ("кит", "зелён", "растен"))),
                ],
                dtype=np.float32,
            )
            if not vector.any():
                vector[-1] = 1.0
            vector /= np.linalg.norm(vector)
            vectors.append(vector)
        return np.stack(vectors)


@pytest.fixture
def tiny_embeddings() -> TinyEmbeddingService:
    return TinyEmbeddingService()


def write_minimal_extracted(
    root: Path,
    *,
    schema_version: str = "1.0",
    users: list[dict[str, Any]] | None = None,
    conversations: list[dict[str, Any]] | None = None,
    runs: list[dict[str, Any]] | None = None,
    messages: list[dict[str, Any]] | None = None,
    events: list[dict[str, Any]] | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    users = users if users is not None else [{"user_id": "u1"}]
    conversations = conversations if conversations is not None else [
        {
            "conversation_id": "c1",
            "user_id": "u1",
            "created_at": "2026-01-01T00:00:00Z",
        }
    ]
    runs = runs if runs is not None else [
        {
            "run_id": "r1",
            "conversation_id": "c1",
            "status": "completed",
            "started_at": "2026-01-01T00:00:00Z",
        }
    ]
    messages = messages if messages is not None else [
        {
            "message_id": "m1",
            "conversation_id": "c1",
            "run_id": "r1",
            "role": "user",
            "content": "Покажи задачи",
            "sequence_number": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "attachment_ids": [],
        }
    ]
    events = events if events is not None else []
    attachments = attachments if attachments is not None else []
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "dataset_id": "test",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    for name, rows in {
        "users.jsonl": users,
        "conversations.jsonl": conversations,
        "runs.jsonl": runs,
        "messages.jsonl": messages,
        "events.jsonl": events,
        "attachments.jsonl": attachments,
    }.items():
        (root / name).write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
    (root / "cost_config.json").write_text(
        '{"currency":"RUB","employee_cost_per_hour":1500}', encoding="utf-8"
    )
    return root


def zip_directory(root: Path, destination: Path) -> Path:
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in root.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(root).as_posix())
    return destination
