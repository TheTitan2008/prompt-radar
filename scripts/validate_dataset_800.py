"""Strict offline checks for the generated 800-run dataset."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from collections import Counter
from datetime import datetime
from statistics import mean, median
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "generated_800"
ZIP_PATH = OUT_DIR / "dataset.zip"
GROUND_TRUTH_PATH = OUT_DIR / "ground_truth.jsonl"
REPORT_PATH = OUT_DIR / "generation_report.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"validation failed: {message}")


def main() -> None:
    temp = Path(tempfile.mkdtemp(prefix="dataset-800-"))
    try:
        with zipfile.ZipFile(ZIP_PATH) as archive:
            names = set(archive.namelist())
            if "ground_truth.jsonl" in names:
                fail("ground_truth.jsonl is inside dataset.zip")
            archive.extractall(temp)
        users = read_jsonl(temp / "users.jsonl")
        conversations = read_jsonl(temp / "conversations.jsonl")
        runs = read_jsonl(temp / "runs.jsonl")
        messages = read_jsonl(temp / "messages.jsonl")
        events = read_jsonl(temp / "events.jsonl")
        attachments = read_jsonl(temp / "attachments.jsonl")
        truth = read_jsonl(GROUND_TRUTH_PATH)
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        if len(runs) != 800 or len(truth) != 800:
            fail("expected exactly 800 runs and 800 ground-truth rows")
        if len(users) != 20:
            fail(f"expected exactly 20 users, got {len(users)}")
        user_by_id = {user["user_id"]: user for user in users}
        if len(user_by_id) != 20:
            fail("user_id values must be unique")
        if any(not user.get("display_name") or " " not in user["display_name"] for user in users):
            fail("each user must have a Russian-looking display_name")
        groups = Counter(row["generator_group"] for row in truth)
        expected_groups = {"known": 600, "mephi": 20, "emerging": 80, "minor_emerging": 60, "noise": 40}
        if dict(groups) != expected_groups:
            fail(f"group distribution mismatch: {dict(groups)}")
        buckets = Counter(row["length_bucket"] for row in truth)
        expected_buckets = {"1_20": 160, "21_100": 320, "101_500": 200, "501_3000": 80, "3001_10000": 32, "exact_100000": 8}
        if dict(buckets) != expected_buckets:
            fail(f"length distribution mismatch: {dict(buckets)}")
        known_counts = Counter(row["expected_use_case_ids"][0] for row in truth if row["generator_group"] == "known")
        if len(known_counts) != 31 or sorted(known_counts.values()).count(16) != 5 or sorted(known_counts.values()).count(20) != 26:
            fail("known use-case distribution mismatch")
        if sum(1 for row in truth if row["expected_has_attachments"]) != 60:
            fail("expected 60 runs with attachments")
        if sum(1 for row in truth if row["generator_group"] in {"noise", "minor_emerging"}) != 100:
            fail("expected 100 runs in the clarified noise block")
        minor_counts = Counter(row["expected_cluster_id"] for row in truth if row["generator_group"] == "minor_emerging")
        if sorted(minor_counts.values()) != [12, 12, 12, 12, 12]:
            fail(f"minor emerging group sizes mismatch: {dict(minor_counts)}")
        conversation_by_id = {c["conversation_id"]: c for c in conversations}
        for conversation in conversations:
            if conversation["user_id"] not in user_by_id:
                fail(f"unknown conversation user_id: {conversation['user_id']}")
            if conversation.get("owner_user_id") != conversation["user_id"]:
                fail(f"conversation owner mismatch: {conversation['conversation_id']}")
        tatiana_conv_ids = {c["conversation_id"] for c in conversations if c["user_id"] == "tatiana_belyakova"}
        mephi_runs = {row["run_id"] for row in truth if row["generator_group"] == "mephi"}
        run_by_id = {r["run_id"]: r for r in runs}
        runs_by_user = Counter(run.get("user_id") for run in runs)
        if sum(runs_by_user.values()) != 800:
            fail("runs_by_user must sum to 800")
        if set(runs_by_user) != set(user_by_id):
            fail("runs must reference exactly the 20 known users")
        if min(runs_by_user.values()) < 2:
            fail("each user must have at least 2 runs")
        if len(set(runs_by_user.values())) < 10:
            fail("run distribution is too uniform")
        if len(tatiana_conv_ids) < 4:
            fail("Tatiana must have at least four conversations")
        if any(run_by_id[run_id]["conversation_id"] not in tatiana_conv_ids or run_by_id[run_id].get("user_id") != "tatiana_belyakova" for run_id in mephi_runs):
            fail("all MEPhI runs must belong to Tatiana")
        for entity_name, rows, key in [
            ("users", users, "user_id"),
            ("conversations", conversations, "conversation_id"),
            ("runs", runs, "run_id"),
            ("messages", messages, "message_id"),
            ("events", events, "event_id"),
            ("attachments", attachments, "attachment_id"),
        ]:
            ids = [row[key] for row in rows]
            if len(ids) != len(set(ids)):
                fail(f"duplicate IDs in {entity_name}")
        msg_by_id = {m["message_id"]: m for m in messages}
        for message in messages:
            conversation = conversation_by_id[message["conversation_id"]]
            if message["role"] == "user" and message.get("sender_user_id") != conversation["user_id"]:
                fail(f"user message sender mismatch: {message['message_id']}")
            if message.get("run_id"):
                run = run_by_id[message["run_id"]]
                if run["conversation_id"] != message["conversation_id"]:
                    fail(f"message/run conversation mismatch: {message['message_id']}")
                if message["role"] == "user" and message.get("sender_user_id") != run["user_id"]:
                    fail(f"message/run user mismatch: {message['message_id']}")
        for attachment in attachments:
            rel = attachment["path"]
            path = temp / rel
            if not path.is_file() or ".." in Path(rel).parts or Path(rel).is_absolute():
                fail(f"bad attachment path: {rel}")
            if path.stat().st_size != attachment["size_bytes"]:
                fail(f"attachment size mismatch: {rel}")
            if attachment.get("sha256") != sha256_file(path):
                fail(f"attachment sha256 mismatch: {rel}")
            if attachment["attachment_id"] not in msg_by_id[attachment["message_id"]].get("attachment_ids", []):
                fail("attachment/message backlink mismatch")
        ai_values = []
        interval_mismatches = 0
        for run in runs:
            if run["user_id"] != conversation_by_id[run["conversation_id"]]["user_id"]:
                fail(f"run user mismatch: {run['run_id']}")
            metadata = run.get("metadata") or {}
            if metadata.get("ai_processing_minutes_source") != "synthetic_complexity_estimate":
                fail(f"missing/invalid ai_processing_minutes_source: {run['run_id']}")
            if metadata.get("ai_processing_minutes_evidence_level") != "E0":
                fail(f"missing/invalid ai_processing_minutes_evidence_level: {run['run_id']}")
            minutes = metadata.get("ai_processing_minutes")
            if not isinstance(minutes, (int, float)) or isinstance(minutes, bool) or minutes < 0:
                fail(f"missing/invalid ai_processing_minutes: {run['run_id']}")
            ai_values.append(float(minutes))
            started_at = datetime.fromisoformat(run["started_at"].replace("Z", "+00:00"))
            finished_at = datetime.fromisoformat(run["finished_at"].replace("Z", "+00:00"))
            if run.get("finished_at") and finished_at < started_at:
                fail(f"finished_at before started_at: {run['run_id']}")
            actual = (finished_at - started_at).total_seconds() / 60
            if abs(actual - float(minutes)) > (1 / 60):
                interval_mismatches += 1
        if interval_mismatches:
            fail(f"ai_processing interval mismatches: {interval_mismatches}")
        for event in events:
            if event.get("run_id"):
                run = run_by_id[event["run_id"]]
                created_at = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
                started_at = datetime.fromisoformat(run["started_at"].replace("Z", "+00:00"))
                finished_at = datetime.fromisoformat(run["finished_at"].replace("Z", "+00:00"))
                if not started_at <= created_at <= finished_at:
                    fail(f"event outside run interval: {event['event_id']}")
        truth_by_run = {row["run_id"]: row for row in truth}
        for run in runs:
            truth_row = truth_by_run[run["run_id"]]
            user = user_by_id[run["user_id"]]
            minutes = float(run["metadata"]["ai_processing_minutes"])
            if truth_row.get("expected_user_id") != run["user_id"]:
                fail(f"ground truth user_id mismatch: {run['run_id']}")
            if truth_row.get("expected_user_name") != user["display_name"]:
                fail(f"ground truth user name mismatch: {run['run_id']}")
            if abs(float(truth_row.get("expected_ai_processing_minutes")) - minutes) > 1e-9:
                fail(f"ground truth ai minutes mismatch: {run['run_id']}")
            if truth_row.get("expected_ai_processing_minutes_source") != "synthetic_complexity_estimate":
                fail(f"ground truth ai source mismatch: {run['run_id']}")
        runs_by_name = {
            user["display_name"]: runs_by_user[user["user_id"]]
            for user in users
        }
        report["unique_named_users"] = len(users)
        report["runs_by_user"] = runs_by_name
        report["min_runs_per_user"] = min(runs_by_user.values())
        report["max_runs_per_user"] = max(runs_by_user.values())
        report["mean_runs_per_user"] = round(mean(runs_by_user.values()), 2)
        report["median_runs_per_user"] = median(runs_by_user.values())
        report["ai_processing_minutes_min"] = min(ai_values)
        report["ai_processing_minutes_max"] = max(ai_values)
        report["ai_processing_minutes_mean"] = round(mean(ai_values), 2)
        report["ai_processing_minutes_median"] = median(ai_values)
        report["ai_processing_interval_mismatch_count"] = 0
        report["mephi_runs_owned_by_tatiana_belyakova"] = len(mephi_runs)
        for file_name in ["generation_report.json", "ground_truth.jsonl", "source/messages.jsonl"]:
            path = OUT_DIR / file_name
            text = path.read_text(encoding="utf-8")
            if "\ufffd" in text or "Рџ" in text or "Рµ" in text:
                fail(f"possible mojibake in {file_name}")
        report["validation_passed"] = True
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"valid": True, "runs": len(runs), "users": len(users), "conversations": len(conversations), "messages": len(messages), "attachments": len(attachments), "ai_processing_minutes_min": min(ai_values), "ai_processing_minutes_max": max(ai_values)}, ensure_ascii=False, indent=2))
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    main()
