from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GENERATED_800 = ROOT / "data" / "generated_800"


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.skipif(
    not (GENERATED_800 / "source" / "runs.jsonl").exists(),
    reason="generated_800 dataset has not been generated",
)
def test_generated_800_user_and_ai_time_invariants() -> None:
    users = _read_jsonl(GENERATED_800 / "source" / "users.jsonl")
    conversations = _read_jsonl(GENERATED_800 / "source" / "conversations.jsonl")
    runs = _read_jsonl(GENERATED_800 / "source" / "runs.jsonl")
    messages = _read_jsonl(GENERATED_800 / "source" / "messages.jsonl")
    truth = _read_jsonl(GENERATED_800 / "ground_truth.jsonl")
    report = json.loads(
        (GENERATED_800 / "generation_report.json").read_text(encoding="utf-8")
    )

    assert len(users) == 20
    assert len(runs) == 800
    assert len(truth) == 800
    user_by_id = {user["user_id"]: user for user in users}
    assert all(user.get("display_name") for user in users)

    conversation_by_id = {item["conversation_id"]: item for item in conversations}
    runs_by_user = Counter(run["user_id"] for run in runs)
    assert set(runs_by_user) == set(user_by_id)
    assert sum(runs_by_user.values()) == 800
    assert min(runs_by_user.values()) >= 2
    assert len(set(runs_by_user.values())) >= 10

    for run in runs:
        conversation = conversation_by_id[run["conversation_id"]]
        assert conversation["user_id"] == run["user_id"]
        metadata = run["metadata"]
        assert metadata["ai_processing_minutes_source"] == (
            "synthetic_complexity_estimate"
        )
        assert metadata["ai_processing_minutes_evidence_level"] == "E0"
        minutes = float(metadata["ai_processing_minutes"])
        started_at = datetime.fromisoformat(run["started_at"].replace("Z", "+00:00"))
        finished_at = datetime.fromisoformat(
            run["finished_at"].replace("Z", "+00:00")
        )
        actual = (finished_at - started_at).total_seconds() / 60
        assert abs(actual - minutes) <= (1 / 60)

    for message in messages:
        if message["role"] == "user":
            conversation = conversation_by_id[message["conversation_id"]]
            assert message["sender_user_id"] == conversation["user_id"]

    mephi = [row for row in truth if row["generator_group"] == "mephi"]
    assert len(mephi) == 20
    assert {row["expected_user_id"] for row in mephi} == {"tatiana_belyakova"}
    assert report["unique_named_users"] == 20
    assert report["runs_by_user"]["Татьяна Белякова"] == 20
    assert report["mephi_runs_owned_by_tatiana_belyakova"] == 20
    assert report["ai_processing_interval_mismatch_count"] == 0
