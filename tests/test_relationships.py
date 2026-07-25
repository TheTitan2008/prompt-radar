from __future__ import annotations

from pathlib import Path

from prompt_radar.config import load_config
from prompt_radar.ingestion.relationship_builder import messages_by_run
from prompt_radar.ingestion.validator import validate_extracted
from prompt_radar.preprocessing.run_builder import build_run_tasks

from conftest import TinyEmbeddingService, write_minimal_extracted


def test_messages_are_sorted_within_run(tmp_path: Path) -> None:
    messages = [
        {
            "message_id": "m2",
            "conversation_id": "c1",
            "run_id": "r1",
            "role": "user",
            "content": "second",
            "sequence_number": 2,
            "created_at": "2026-01-01T00:02:00Z",
        },
        {
            "message_id": "m1",
            "conversation_id": "c1",
            "run_id": "r1",
            "role": "user",
            "content": "first",
            "sequence_number": 1,
            "created_at": "2026-01-01T00:01:00Z",
        },
    ]
    root = write_minimal_extracted(tmp_path / "data", messages=messages)
    bundle, report = validate_extracted(root)
    assert report.valid and bundle
    assert [item.message_id for item in messages_by_run(bundle)["r1"]] == ["m1", "m2"]


def test_one_user_can_have_multiple_conversations(tmp_path: Path) -> None:
    conversations = [
        {"conversation_id": "c1", "user_id": "u1", "created_at": "2026-01-01T00:00:00Z"},
        {"conversation_id": "c2", "user_id": "u1", "created_at": "2026-01-02T00:00:00Z"},
    ]
    root = write_minimal_extracted(tmp_path / "data", conversations=conversations)
    bundle, report = validate_extracted(root)
    assert report.valid and bundle
    assert {item.conversation_id for item in bundle.conversations} == {"c1", "c2"}


def test_one_conversation_can_have_multiple_runs(tmp_path: Path) -> None:
    runs = [
        {"run_id": "r1", "conversation_id": "c1", "status": "completed", "started_at": "2026-01-01T00:00:00Z"},
        {"run_id": "r2", "conversation_id": "c1", "status": "completed", "started_at": "2026-01-01T01:00:00Z"},
    ]
    messages = [
        {"message_id": "m1", "conversation_id": "c1", "run_id": "r1", "role": "user", "content": "mail", "sequence_number": 1, "created_at": "2026-01-01T00:00:00Z"},
        {"message_id": "m2", "conversation_id": "c1", "run_id": "r2", "role": "user", "content": "jira", "sequence_number": 2, "created_at": "2026-01-01T01:00:00Z"},
    ]
    root = write_minimal_extracted(tmp_path / "data", runs=runs, messages=messages)
    bundle, report = validate_extracted(root)
    assert report.valid and bundle
    config = load_config(Path("configs/pipeline.yaml"))
    tasks = build_run_tasks(bundle, config, TinyEmbeddingService())
    assert {task.run_id for task in tasks} == {"r1", "r2"}

