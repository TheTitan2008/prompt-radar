"""Strict offline checks for the generated 200-run dataset."""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "generated_200"
ZIP_PATH = OUT_DIR / "dataset.zip"
GROUND_TRUTH_PATH = OUT_DIR / "ground_truth.jsonl"
REPORT_PATH = OUT_DIR / "generation_report.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail(message: str) -> None:
    raise SystemExit(f"validation failed: {message}")


def main() -> None:
    temp = Path(tempfile.mkdtemp(prefix="dataset-200-"))
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
        if len(runs) != 200 or len(truth) != 200:
            fail("expected exactly 200 runs and 200 ground-truth rows")
        groups = Counter(row["generator_group"] for row in truth)
        expected_groups = {"known": 150, "mephi": 5, "emerging": 20, "noise": 25}
        if dict(groups) != expected_groups:
            fail(f"group distribution mismatch: {dict(groups)}")
        buckets = Counter(row["length_bucket"] for row in truth)
        expected_buckets = {"1_20": 40, "21_100": 80, "101_500": 50, "501_3000": 20, "3001_10000": 8, "exact_100000": 2}
        if dict(buckets) != expected_buckets:
            fail(f"length distribution mismatch: {dict(buckets)}")
        known_counts = Counter(row["expected_use_case_ids"][0] for row in truth if row["generator_group"] == "known")
        if len(known_counts) != 31 or sorted(known_counts.values()).count(4) != 5 or sorted(known_counts.values()).count(5) != 26:
            fail("known use-case distribution mismatch")
        if sum(1 for row in truth if row["expected_has_attachments"]) != 15:
            fail("expected 15 runs with attachments")
        tatiana_conv_ids = {c["conversation_id"] for c in conversations if c["user_id"] == "tatiana_belyakova"}
        mephi_runs = {row["run_id"] for row in truth if row["generator_group"] == "mephi"}
        run_by_id = {r["run_id"]: r for r in runs}
        if len(tatiana_conv_ids) < 2:
            fail("Tatiana must have at least two conversations")
        if any(run_by_id[run_id]["conversation_id"] not in tatiana_conv_ids for run_id in mephi_runs):
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
        for attachment in attachments:
            rel = attachment["path"]
            path = temp / rel
            if not path.is_file() or ".." in Path(rel).parts or Path(rel).is_absolute():
                fail(f"bad attachment path: {rel}")
            if path.stat().st_size != attachment["size_bytes"]:
                fail(f"attachment size mismatch: {rel}")
            if attachment["attachment_id"] not in msg_by_id[attachment["message_id"]].get("attachment_ids", []):
                fail("attachment/message backlink mismatch")
        for run in runs:
            if run.get("finished_at") and datetime.fromisoformat(run["finished_at"].replace("Z", "+00:00")) < datetime.fromisoformat(run["started_at"].replace("Z", "+00:00")):
                fail(f"finished_at before started_at: {run['run_id']}")
        report["validation_passed"] = True
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"valid": True, "runs": len(runs), "users": len(users), "conversations": len(conversations), "messages": len(messages), "attachments": len(attachments)}, ensure_ascii=False, indent=2))
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    main()
