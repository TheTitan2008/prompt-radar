from __future__ import annotations

import json
from pathlib import Path

import pytest

from prompt_radar.analysis_binding import analysis_binding_hash
from prompt_radar.economics_analysis.loaders import (
    load_analysis_passports,
    merge_passports,
)
from prompt_radar.economics_analysis.models import PassportFile


def test_analysis_hash_is_independent_of_run_order() -> None:
    values = {
        "dataset_id": "dataset",
        "configuration_hash": "config",
        "model_id": "model",
        "model_revision": "revision",
        "preprocessing_version": "1",
    }
    assert analysis_binding_hash(**values, run_ids=["b", "a"]) == (
        analysis_binding_hash(**values, run_ids=["a", "b"])
    )


def test_api_cluster_passport_is_loaded_and_stale_override_is_rejected(
    tmp_path: Path,
) -> None:
    metadata = {
        "dataset_id": "dataset",
        "configuration_hash": "config",
        "model_id": "embedding",
        "model_revision": "revision",
        "preprocessing_version": "1",
    }
    (tmp_path / "pipeline_metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    rows = [
        {
            "run_id": "run-1",
            "cluster_id": 0,
            "task_passport_text": "Create a Jira ticket from a client email",
        }
    ]
    passport = {
        "cluster_name": "Client email to Jira",
        "business_goal": "Register a client request",
        "manual_steps": [{"step": "Read and register", "minutes_base": 10}],
        "manual_minutes": {"low": 7, "base": 10, "high": 15},
        "human_followup_minutes": {"low": 1, "base": 2, "high": 3},
        "active_wait_ratio": {"low": 0, "base": 0.1, "high": 0.3},
        "manual_time_confidence": 0.5,
        "assumptions": [],
        "uncertainty_drivers": [],
    }
    (tmp_path / "clusters.json").write_text(
        json.dumps(
            [
                {
                    "cluster_id": 0,
                    "source_model": "qwen",
                    "source_model_revision": "deployment-1",
                    "source_prompt_version": "1.0.0",
                    "economic_passport": passport,
                }
            ]
        ),
        encoding="utf-8",
    )

    automatic, bindings, _ = load_analysis_passports(tmp_path, rows)
    assert len(automatic.passports) == 1
    loaded = automatic.passports[0]
    assert loaded.target_id == rows[0]["cluster_fingerprint"]
    assert loaded.source_model == "qwen"
    assert loaded.evidence_level == "E0"

    stale = loaded.model_copy(update={"analysis_hash": "stale"})
    with pytest.raises(ValueError, match="analysis_hash"):
        merge_passports(
            automatic,
            PassportFile(schema_version="1.0", passports=[stale]),
            bindings,
        )
