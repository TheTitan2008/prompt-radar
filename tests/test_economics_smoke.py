from __future__ import annotations

import json
import socket
from pathlib import Path

from prompt_radar.economics_analysis.loaders import load_financial_config, load_passports
from prompt_radar.economics_analysis.engine import build_run_ledger
from prompt_radar.economics_analysis.service import run_economics


def _analysis_row(*, prompt: float | None = 2.0, status: str = "failed") -> dict:
    metadata = {
        "status": status,
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:05:00Z",
        "metadata": {"input_tokens": 1000},
    }
    if prompt is not None:
        metadata["metadata"]["prompt_minutes"] = prompt
    return {
        "run_id": "r1",
        "conversation_id": "c1",
        "user_id": "u1",
        "classification_status": "matched_known",
        "discovery_status": "known",
        "cluster_id": -1,
        "known_use_case_matches": [
            {
                "id": "daily_email_digest",
                "name": "Ежедневная сводка почты",
                "accepted": True,
            }
        ],
        "run_metadata": metadata,
    }


def test_unknown_quality_does_not_become_actual_quality() -> None:
    config = load_financial_config(Path("data/economics/cost_config.json"))
    passports = load_passports(
        Path("data/economics/cluster_economic_passports.json")
    )
    ledger, _, _ = build_run_ledger(
        [_analysis_row()], passports, {}, config
    )
    assert ledger[0]["run_status"] == "failed"
    assert ledger[0]["quality_score"] is None
    assert ledger[0]["actual"] is None
    assert ledger[0]["potential"] is not None


def test_missing_prompt_is_not_replaced_with_zero() -> None:
    config = load_financial_config(Path("data/economics/cost_config.json"))
    passports = load_passports(
        Path("data/economics/cluster_economic_passports.json")
    )
    ledger, _, warnings = build_run_ledger(
        [_analysis_row(prompt=None)], passports, {}, config
    )
    assert ledger[0]["prompt_minutes"] is None
    assert ledger[0]["potential"] is None
    assert ledger[0]["status"] == "INSUFFICIENT_EVIDENCE"
    assert any(item["code"] == "missing_prompt_minutes" for item in warnings)


def test_missing_passport_is_insufficient() -> None:
    config = load_financial_config(Path("data/economics/cost_config.json"))
    passports = load_passports(
        Path("data/economics/cluster_economic_passports.json")
    )
    row = _analysis_row()
    row["known_use_case_matches"][0]["id"] = "unknown"
    ledger, _, _ = build_run_ledger([row], passports, {}, config)
    assert ledger[0]["status"] == "INSUFFICIENT_EVIDENCE"
    assert "economic_passport" in ledger[0]["missing_evidence"]


def test_multi_goal_known_match_is_not_given_the_first_business_baseline() -> None:
    config = load_financial_config(Path("data/economics/cost_config.json"))
    passports = load_passports(
        Path("data/economics/cluster_economic_passports.json")
    )
    row = _analysis_row()
    row["multiple_goals"] = True

    ledger, _, _ = build_run_ledger([row], passports, {}, config)

    assert ledger[0]["target_id"] is None
    assert ledger[0]["potential"] is None
    assert "economic_passport" in ledger[0]["missing_evidence"]


def test_low_margin_known_match_is_not_used_for_economics() -> None:
    config = load_financial_config(Path("data/economics/cost_config.json"))
    passports = load_passports(
        Path("data/economics/cluster_economic_passports.json")
    )
    row = _analysis_row()
    row["known_use_case_matches"][0].update(
        {
            "similarity_score": 0.61,
            "threshold_used": 0.60,
        }
    )

    ledger, _, _ = build_run_ledger([row], passports, {}, config)

    assert ledger[0]["target_id"] is None
    assert ledger[0]["potential"] is None


def test_economics_command_is_offline_and_keeps_failed_denominator(
    tmp_path: Path, monkeypatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("network attempted")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "runs_analysis.jsonl").write_text(
        json.dumps(_analysis_row(), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for name, content in {
        "pipeline_metadata.json": {"schema_version": "1.0"},
        "validation_report.json": {"valid": True},
        "clusters.json": [],
    }.items():
        (analysis / name).write_text(
            json.dumps(content), encoding="utf-8"
        )
    (analysis / "cluster_members.jsonl").write_text("", encoding="utf-8")
    source = load_passports(
        Path("data/economics/cluster_economic_passports.json")
    )
    known_only = source.model_copy(
        update={
            "passports": [
                item
                for item in source.passports
                if item.target_type == "known_use_case"
            ]
        }
    )
    override = tmp_path / "known_passports.json"
    override.write_text(
        known_only.model_dump_json(indent=2),
        encoding="utf-8",
    )
    output = run_economics(
        analysis_dir=analysis,
        passports_path=override,
        quality_path=None,
        cost_config_path=Path("data/economics/cost_config.json"),
        output_dir=tmp_path / "economics",
    )
    platform = json.loads(
        (output / "platform_economics.json").read_text(encoding="utf-8")
    )
    assert platform["total_runs"] == 1
    assert platform["run_status_counts"]["failed"] == 1
    assert platform["external_api_called"] is False
    assert (output / "economics_report.md").is_file()
