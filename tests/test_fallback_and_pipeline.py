from __future__ import annotations

import json
import socket
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from prompt_radar.config import FallbackConfig
from prompt_radar.demo import generate_demo
from prompt_radar.models import Message
from prompt_radar.pipeline import analyze_dataset
from prompt_radar.preprocessing.fallback_run_segmenter import segment_missing_runs

from conftest import TinyEmbeddingService


def runless(
    message_id: str, content: str, minute: int, sequence: int
) -> Message:
    return Message(
        message_id=message_id,
        conversation_id="c1",
        run_id=None,
        role="user",
        content=content,
        sequence_number=sequence,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        + timedelta(minutes=minute),
    )


def test_fallback_segmenter_keeps_explicit_dependency() -> None:
    messages = [
        runless("m1", "Найди письма клиента", 0, 1),
        runless("m2", "Сделай это для последней недели", 1, 2),
    ]
    result = segment_missing_runs(
        messages,
        FallbackConfig(dependent_phrases=["сделай это"]),
        TinyEmbeddingService(),
    )
    assert len(result) == 1
    assert [item.message_id for item in next(iter(result.values()))] == ["m1", "m2"]


def test_fallback_segmenter_splits_explicit_topic_change() -> None:
    messages = [
        runless("m1", "Найди письма клиента", 0, 1),
        runless("m2", "Теперь другая задача: создай встречу", 1, 2),
    ]
    result = segment_missing_runs(
        messages,
        FallbackConfig(topic_change_phrases=["теперь другая задача"]),
        TinyEmbeddingService(),
    )
    assert len(result) == 2


def test_analyze_ignores_ground_truth_and_fake_backend_stays_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "dataset.zip"
    labels = tmp_path / "labels.jsonl"
    generate_demo(dataset, labels, 42)
    with zipfile.ZipFile(dataset, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ground_truth.jsonl", "{ deliberately invalid")

    config = yaml.safe_load(Path("configs/pipeline.yaml").read_text(encoding="utf-8"))
    config["clustering"]["use_umap"] = False
    config["classification"]["known_use_case_threshold"] = -1.0
    config["classification"]["additional_use_case_threshold"] = -1.0
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("network attempted")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    output = analyze_dataset(
        input_path=dataset,
        output_root=tmp_path / "outputs",
        config_path=config_path,
        categories_path=Path("configs/categories.yaml"),
        use_cases_path=Path("configs/known_use_cases.yaml"),
        embedding_backend="fake",
        offline=True,
    )
    metadata = json.loads(
        (output / "pipeline_metadata.json").read_text(encoding="utf-8")
    )
    assert metadata["ground_truth_loaded"] is False
    assert metadata["external_generative_api_called"] is False
    assert metadata["external_generative_api_call_count"] == 0
    assert metadata["effective_parameters"]["economics"] == {
        "employee_cost_per_hour": 1500
    }
    assert metadata["known_use_case_passport_count"] == 31
    rows = [
        json.loads(line)
        for line in (output / "runs_analysis.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    assert rows[0]["economic_passport"]["manual_minutes"]["base"] > 0
    assert rows[0]["local_economics"]["employee_cost_per_hour"] == 1500
    passports = json.loads(
        (output / "known_use_case_passports.json").read_text(encoding="utf-8")
    )
    assert len(passports) == 31
    assert (output / "cluster_enrichments.json").is_file()
    assert (output / "report.md").is_file()
