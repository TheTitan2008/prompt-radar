from __future__ import annotations

import json
from pathlib import Path

from prompt_radar.ingestion.validator import validate_extracted

from conftest import write_minimal_extracted


def test_missing_required_jsonl_has_clear_error(tmp_path: Path) -> None:
    root = write_minimal_extracted(tmp_path / "data")
    (root / "messages.jsonl").unlink()
    bundle, report = validate_extracted(root)
    assert bundle is None
    assert any(
        issue.code == "missing_required_file" and issue.file == "messages.jsonl"
        for issue in report.issues
    )


def test_unknown_schema_major_is_rejected(tmp_path: Path) -> None:
    root = write_minimal_extracted(tmp_path / "data", schema_version="2.0")
    bundle, report = validate_extracted(root)
    assert bundle is None
    assert any(issue.code == "unsupported_schema_major" for issue in report.issues)


def test_duplicate_ids_are_detected(tmp_path: Path) -> None:
    root = write_minimal_extracted(
        tmp_path / "data", users=[{"user_id": "u1"}, {"user_id": "u1"}]
    )
    _, report = validate_extracted(root)
    assert any(issue.code == "duplicate_id" for issue in report.issues)


def test_missing_attachment_id_is_detected(tmp_path: Path) -> None:
    messages = [
        {
            "message_id": "m1",
            "conversation_id": "c1",
            "run_id": "r1",
            "role": "user",
            "content": "x",
            "sequence_number": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "attachment_ids": ["missing"],
        }
    ]
    root = write_minimal_extracted(tmp_path / "data", messages=messages)
    _, report = validate_extracted(root)
    assert any(issue.code == "orphan_attachment" for issue in report.issues)


def test_missing_relationship_ids_are_detected(tmp_path: Path) -> None:
    conversations = [
        {
            "conversation_id": "c1",
            "user_id": "missing",
            "created_at": "2026-01-01T00:00:00Z",
        }
    ]
    runs = [
        {
            "run_id": "r1",
            "conversation_id": "missing",
            "status": "completed",
            "started_at": "2026-01-01T00:00:00Z",
        }
    ]
    root = write_minimal_extracted(
        tmp_path / "data", conversations=conversations, runs=runs
    )
    _, report = validate_extracted(root)
    codes = {issue.code for issue in report.issues}
    assert "orphan_user" in codes
    assert "orphan_conversation" in codes


def test_role_specific_cost_is_rejected(tmp_path: Path) -> None:
    root = write_minimal_extracted(tmp_path / "data")
    (root / "cost_config.json").write_text(
        json.dumps(
            {
                "currency": "RUB",
                "worker_role": "lawyer",
                "employee_cost_per_hour": 3000,
            }
        ),
        encoding="utf-8",
    )
    bundle, report = validate_extracted(root)
    assert bundle is None
    assert any(issue.code == "invalid_cost_config" for issue in report.issues)


def test_cost_config_is_normalized_to_fixed_1500(tmp_path: Path) -> None:
    root = write_minimal_extracted(tmp_path / "data")
    (root / "cost_config.json").write_text(
        '{"currency":"RUB"}', encoding="utf-8"
    )
    bundle, report = validate_extracted(root)
    assert report.valid is True
    assert bundle is not None
    assert bundle.cost_config["employee_cost_per_hour"] == 1500


def test_ai_processing_minutes_and_user_ownership_are_validated(tmp_path: Path) -> None:
    users = [{"user_id": "u1", "display_name": "Иван Петров"}]
    conversations = [
        {
            "conversation_id": "c1",
            "user_id": "u1",
            "owner_user_id": "u1",
            "created_at": "2026-01-01T00:00:00Z",
        }
    ]
    runs = [
        {
            "run_id": "r1",
            "conversation_id": "c1",
            "user_id": "u1",
            "status": "completed",
            "started_at": "2026-01-01T00:00:00Z",
            "finished_at": "2026-01-01T00:03:30Z",
            "metadata": {
                "ai_processing_minutes": 3.5,
                "ai_processing_minutes_source": "synthetic_complexity_estimate",
                "ai_processing_minutes_evidence_level": "E0",
            },
        }
    ]
    messages = [
        {
            "message_id": "m1",
            "conversation_id": "c1",
            "run_id": "r1",
            "sender_user_id": "u1",
            "role": "user",
            "content": "Покажи задачи",
            "sequence_number": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "attachment_ids": [],
        }
    ]
    root = write_minimal_extracted(
        tmp_path / "data",
        users=users,
        conversations=conversations,
        runs=runs,
        messages=messages,
    )
    bundle, report = validate_extracted(root)
    assert report.valid is True
    assert bundle is not None


def test_ai_processing_minutes_must_match_run_interval(tmp_path: Path) -> None:
    runs = [
        {
            "run_id": "r1",
            "conversation_id": "c1",
            "status": "completed",
            "started_at": "2026-01-01T00:00:00Z",
            "finished_at": "2026-01-01T00:04:00Z",
            "metadata": {
                "ai_processing_minutes": 3.0,
                "ai_processing_minutes_source": "synthetic_complexity_estimate",
                "ai_processing_minutes_evidence_level": "E0",
            },
        }
    ]
    root = write_minimal_extracted(tmp_path / "data", runs=runs)
    _, report = validate_extracted(root)
    assert any(issue.code == "ai_processing_minutes_mismatch" for issue in report.issues)


def test_run_and_message_user_mismatch_is_rejected(tmp_path: Path) -> None:
    users = [{"user_id": "u1"}, {"user_id": "u2"}]
    runs = [
        {
            "run_id": "r1",
            "conversation_id": "c1",
            "user_id": "u2",
            "status": "completed",
            "started_at": "2026-01-01T00:00:00Z",
        }
    ]
    messages = [
        {
            "message_id": "m1",
            "conversation_id": "c1",
            "run_id": "r1",
            "sender_user_id": "u2",
            "role": "user",
            "content": "Покажи задачи",
            "sequence_number": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "attachment_ids": [],
        }
    ]
    root = write_minimal_extracted(tmp_path / "data", users=users, runs=runs, messages=messages)
    _, report = validate_extracted(root)
    codes = {issue.code for issue in report.issues}
    assert "run_user_mismatch" in codes
    assert "message_sender_mismatch" in codes


def test_event_timestamp_must_be_inside_run_interval(tmp_path: Path) -> None:
    runs = [
        {
            "run_id": "r1",
            "conversation_id": "c1",
            "status": "completed",
            "started_at": "2026-01-01T00:00:00Z",
            "finished_at": "2026-01-01T00:03:00Z",
        }
    ]
    events = [
        {
            "event_id": "e1",
            "conversation_id": "c1",
            "run_id": "r1",
            "event_type": "tool_call",
            "status": "success",
            "sequence_number": 1,
            "created_at": "2026-01-01T00:04:00Z",
        }
    ]
    root = write_minimal_extracted(tmp_path / "data", runs=runs, events=events)
    _, report = validate_extracted(root)
    assert any(issue.code == "event_outside_run_interval" for issue in report.issues)
