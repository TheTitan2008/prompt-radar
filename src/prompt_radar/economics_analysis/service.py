"""Offline economics command orchestration and artifact writing."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from prompt_radar.economics_analysis.engine import (
    aggregate_clusters,
    aggregate_platform,
    build_run_ledger,
    build_value_leakage,
)
from prompt_radar.economics_analysis.loaders import (
    load_analysis_rows,
    load_analysis_passports,
    load_financial_config,
    load_passports,
    load_quality,
    merge_passports,
    read_json,
    sha256_file,
)
from prompt_radar.economics_analysis.reporting import build_economics_report
from prompt_radar.economics_analysis.statistics_report import (
    build_statistics_html,
    build_statistics_summary,
)
from prompt_radar.io_utils import atomic_write_text, write_csv, write_json, write_jsonl


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=3,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for name in ("pydantic", "numpy", "pandas", "pyarrow"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "not-installed"
    return result


def _flat_run(item: dict[str, Any]) -> dict[str, Any]:
    potential = item.get("potential") or {}
    actual = item.get("actual") or {}
    return {
        "run_id": item["run_id"],
        "conversation_id": item["conversation_id"],
        "user_id": item["user_id"],
        "target_type": item["target_type"],
        "target_id": item["target_id"],
        "run_status": item["run_status"],
        "manual_minutes_low": (item.get("manual_minutes") or {}).get("low"),
        "manual_minutes_base": (item.get("manual_minutes") or {}).get("base"),
        "manual_minutes_high": (item.get("manual_minutes") or {}).get("high"),
        "prompt_minutes": item["prompt_minutes"],
        "ai_wall_minutes": item["ai_wall_minutes"],
        "quality_score": item["quality_score"],
        "quality_evidence": item["quality_evidence"],
        "marginal_cost": item["marginal_cost"],
        "fully_loaded_cost": item["fully_loaded_cost"],
        "potential_saved_minutes_base": (potential.get("base") or {}).get("saved_minutes"),
        "potential_roi_base": (potential.get("base") or {}).get("roi"),
        "actual_saved_minutes": actual.get("saved_minutes"),
        "actual_roi": actual.get("roi"),
        "break_even_quality_base": (item.get("break_even_quality") or {}).get("base"),
        "status": item["status"],
        "missing_evidence": json.dumps(item["missing_evidence"], ensure_ascii=False),
    }


def _flat_cluster(item: dict[str, Any]) -> dict[str, Any]:
    potential = item.get("potential") or {}
    return {
        "target_type": item["target_type"],
        "target_id": item["target_id"],
        "name": item["name"],
        "run_count": item["run_count"],
        "user_count": item["user_count"],
        "conversation_count": item["conversation_count"],
        "evaluated_run_count": item["evaluated_run_count"],
        "evaluation_coverage": item["evaluation_coverage"],
        "mean_quality": item["mean_quality"],
        "quality_ci_low": item["quality_ci_low"],
        "quality_ci_high": item["quality_ci_high"],
        "potential_saved_minutes_base": (potential.get("base") or {}).get("saved_minutes"),
        "potential_roi_base": (potential.get("base") or {}).get("roi"),
        "roi_lower": item["roi_lower"],
        "roi_upper": item["roi_upper"],
        "break_even_quality_base": (item.get("break_even_quality") or {}).get("base"),
        "fully_loaded_cost": item["fully_loaded_cost"],
        "status": item["status"],
        "evidence_level": item["evidence_level"],
    }


def run_economics(
    *,
    analysis_dir: Path,
    passports_path: Path | None,
    cost_config_path: Path,
    output_dir: Path,
    quality_path: Path | None = None,
) -> Path:
    """Execute the fully offline evidence-aware economics layer."""
    required = (
        "pipeline_metadata.json",
        "validation_report.json",
        "clusters.json",
        "cluster_members.jsonl",
    )
    missing = [name for name in required if not (analysis_dir / name).is_file()]
    if missing:
        raise ValueError(f"analysis directory missing required files: {missing}")
    if output_dir.exists():
        raise ValueError(f"economics output already exists: {output_dir}")
    rows = load_analysis_rows(analysis_dir)
    automatic_passports, cluster_bindings, binding_warnings = (
        load_analysis_passports(analysis_dir, rows)
    )
    explicit_passports = (
        load_passports(passports_path) if passports_path is not None else None
    )
    passports = merge_passports(
        automatic_passports,
        explicit_passports,
        cluster_bindings,
    )
    quality = load_quality(quality_path)
    config = load_financial_config(cost_config_path)
    known_run_ids = {str(row["run_id"]) for row in rows}
    unknown_quality = sorted(set(quality) - known_run_ids)
    if unknown_quality:
        raise ValueError(f"quality evaluations reference unknown runs: {unknown_quality}")
    output_dir.mkdir(parents=True)

    ledger, reconciliation, warnings = build_run_ledger(
        rows, passports, quality, config
    )
    warnings[:0] = binding_warnings
    clusters = aggregate_clusters(ledger, quality, config, warnings)
    leakage = build_value_leakage(ledger, config)
    platform_result = aggregate_platform(
        ledger, clusters, reconciliation, leakage, config
    )

    write_jsonl(output_dir / "run_economic_ledger.jsonl", ledger)
    write_csv(output_dir / "run_economic_ledger.csv", [_flat_run(item) for item in ledger])
    write_json(output_dir / "cluster_economics.json", clusters)
    write_csv(output_dir / "cluster_economics.csv", [_flat_cluster(item) for item in clusters])
    write_json(output_dir / "platform_economics.json", platform_result)
    write_json(output_dir / "cost_reconciliation.json", reconciliation)
    write_json(output_dir / "value_leakage.json", leakage)
    write_jsonl(output_dir / "economics_warnings.jsonl", warnings)
    statistics = build_statistics_summary(
        rows=rows,
        ledger=ledger,
        platform=platform_result,
    )
    write_json(output_dir / "statistics_summary.json", statistics)
    atomic_write_text(
        output_dir / "statistics_report.html",
        build_statistics_html(statistics),
    )
    try:
        import pandas as pd

        pd.DataFrame(ledger).to_parquet(
            output_dir / "run_economic_ledger.parquet", index=False
        )
    except (ImportError, OSError, ValueError, TypeError) as exc:
        warnings.append(
            {
                "code": "parquet_output_skipped",
                "message": str(exc),
            }
        )
        write_jsonl(output_dir / "economics_warnings.jsonl", warnings)

    inputs = {
        "analysis_runs": analysis_dir / "runs_analysis.jsonl",
        "analysis_metadata": analysis_dir / "pipeline_metadata.json",
        "analysis_validation": analysis_dir / "validation_report.json",
        "analysis_clusters": analysis_dir / "clusters.json",
        "analysis_cluster_members": analysis_dir / "cluster_members.jsonl",
        "cost_config": cost_config_path,
    }
    if passports_path is not None:
        inputs["passports_override"] = passports_path
    if quality_path is not None:
        inputs["quality"] = quality_path
    metadata = {
        "schema_version": "1.0",
        "passport_schema_version": passports.schema_version,
        "automatic_passport_count": len(automatic_passports.passports),
        "explicit_passport_override_count": (
            len(explicit_passports.passports) if explicit_passports else 0
        ),
        "cost_schema_version": config.schema_version,
        "analysis_schema_version": read_json(
            analysis_dir / "pipeline_metadata.json"
        ).get("schema_version"),
        "git_commit": _git_commit(),
        "python_version": platform.python_version(),
        "dependency_versions": _versions(),
        "currency": config.currency,
        "employee_cost_per_hour": config.employee_cost_per_hour,
        "labor_cost_per_minute": config.employee_cost_per_hour / 60,
        "average_fte_month_cost_rub": config.average_fte_month_cost_rub,
        "cost_allocation_method": reconciliation["gpu_allocation_method"],
        "selected_platform_scenario": config.default_gpu_allocation_scenario,
        "bootstrap_seed": config.bootstrap_seed,
        "bootstrap_iterations": config.bootstrap_iterations,
        "rounding_rules": {
            "money": "Decimal ROUND_HALF_UP to 0.01 RUB",
            "metrics": "Decimal ROUND_HALF_UP to 0.000001",
        },
        "inputs": {
            name: {"path": str(path.resolve()), "sha256": sha256_file(path)}
            for name, path in inputs.items()
            if path.is_file()
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "processed_records": len(ledger),
        "skipped_records": 0,
        "warning_count": len(warnings),
        "quality_evaluation_count": len(quality),
        "external_api_called": False,
    }
    write_json(output_dir / "economics_metadata.json", metadata)
    atomic_write_text(
        output_dir / "economics_report.md",
        build_economics_report(
            platform=platform_result,
            clusters=clusters,
            ledger=ledger,
            warnings=warnings,
        ),
    )
    return output_dir
