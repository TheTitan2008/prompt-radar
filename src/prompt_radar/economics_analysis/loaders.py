"""Input loading and hashing for offline economics runs."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from prompt_radar.analysis_binding import (
    CLUSTER_ENRICHMENT_PROMPT_VERSION,
    analysis_binding_hash,
    cluster_fingerprint,
    member_run_ids_hash,
)
from prompt_radar.economics_analysis.models import (
    EconomicPassport,
    FinancialConfig,
    PassportFile,
    QualityEvaluation,
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{number}: expected JSON object")
        rows.append(value)
    return rows


def load_analysis_rows(directory: Path) -> list[dict[str, Any]]:
    jsonl = directory / "runs_analysis.jsonl"
    if jsonl.is_file():
        return read_jsonl(jsonl)
    parquet = directory / "runs_analysis.parquet"
    if parquet.is_file():
        try:
            import pandas as pd
        except ImportError as exc:
            raise ValueError("Parquet input requires pandas") from exc
        return pd.read_parquet(parquet).to_dict(orient="records")
    raise ValueError("analysis directory has no runs_analysis.jsonl or parquet")


def load_passports(path: Path) -> PassportFile:
    return PassportFile.model_validate(read_json(path))


def _distributed_step_minutes(
    steps: list[dict[str, Any]], total: float
) -> list[float]:
    bases = [Decimal(str(item["minutes_base"])) for item in steps]
    base_total = sum(bases)
    if base_total <= 0:
        raise ValueError("manual step base total must be positive")
    target = Decimal(str(total))
    values = [target * value / base_total for value in bases]
    values[-1] = target - sum(values[:-1])
    return [float(value) for value in values]


def _economic_passport_from_analysis(
    raw: dict[str, Any],
    *,
    target_type: str,
    target_id: str,
    binding: dict[str, Any] | None = None,
) -> EconomicPassport:
    steps = list(raw.get("manual_steps") or [])
    manual = dict(raw.get("manual_minutes") or {})
    lows = _distributed_step_minutes(steps, float(manual["low"]))
    highs = _distributed_step_minutes(steps, float(manual["high"]))
    expanded_steps = [
        {
            "step": str(item["step"]),
            "minutes_low": lows[index],
            "minutes_base": float(item["minutes_base"]),
            "minutes_high": highs[index],
        }
        for index, item in enumerate(steps)
    ]
    binding = binding or {}
    return EconomicPassport.model_validate(
        {
            "target_type": target_type,
            "target_id": target_id,
            "is_coherent_cluster": True,
            "abstain": False,
            "abstention_reason": None,
            "cluster_name": str(raw["cluster_name"]),
            "business_goal": str(raw.get("business_goal") or raw["cluster_name"]),
            "manual_steps": expanded_steps,
            "manual_minutes": manual,
            "human_followup_minutes": raw["human_followup_minutes"],
            "active_wait_ratio": raw["active_wait_ratio"],
            "manual_time_confidence": raw["manual_time_confidence"],
            "assumptions": list(raw.get("assumptions") or []),
            "uncertainty_drivers": list(raw.get("uncertainty_drivers") or []),
            # API and draft catalog estimates enter economics as E0. A separate,
            # explicit human evidence file is required to raise the level.
            "evidence_level": "E0",
            "requires_human_validation": True,
            "owner": raw.get("estimation_source"),
            **binding,
        }
    )


def load_analysis_passports(
    directory: Path,
    rows: list[dict[str, Any]],
) -> tuple[PassportFile, dict[str, dict[str, str]], list[dict[str, Any]]]:
    """Load embedded known/API passports and bind cluster identities to this run."""
    metadata = read_json(directory / "pipeline_metadata.json")
    dataset_id = str(metadata.get("dataset_id") or "")
    configuration_hash = str(metadata.get("configuration_hash") or "")
    model_id = str(metadata.get("model_id") or "")
    model_revision = str(metadata.get("model_revision") or "")
    preprocessing_version = str(metadata.get("preprocessing_version") or "")
    computed_analysis_hash = analysis_binding_hash(
        dataset_id=dataset_id,
        configuration_hash=configuration_hash,
        model_id=model_id,
        model_revision=model_revision,
        preprocessing_version=preprocessing_version,
        run_ids=[str(row["run_id"]) for row in rows],
    )
    stored_analysis_hash = metadata.get("analysis_hash")
    if stored_analysis_hash and str(stored_analysis_hash) != computed_analysis_hash:
        raise ValueError("pipeline metadata analysis_hash does not match analysis rows")

    cluster_rows: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        cluster_id = row.get("cluster_id")
        if isinstance(cluster_id, int) and cluster_id >= 0:
            cluster_rows.setdefault(str(cluster_id), []).append(row)

    bindings: dict[str, dict[str, str]] = {}
    for cluster_id, members in cluster_rows.items():
        member_hash = member_run_ids_hash(str(row["run_id"]) for row in members)
        fingerprint = cluster_fingerprint(
            analysis_hash=computed_analysis_hash,
            member_ids_hash=member_hash,
            task_passport_texts=[
                str(row.get("task_passport_text") or "") for row in members
            ],
        )
        binding = {
            "analysis_dataset_id": dataset_id,
            "analysis_hash": computed_analysis_hash,
            "analysis_configuration_hash": configuration_hash,
            "cluster_fingerprint": fingerprint,
            "member_run_ids_hash": member_hash,
            "source_model": model_id,
            "source_model_revision": model_revision,
            "source_prompt_version": CLUSTER_ENRICHMENT_PROMPT_VERSION,
        }
        bindings[cluster_id] = binding
        for row in members:
            existing = row.get("cluster_fingerprint")
            if existing and str(existing) != fingerprint:
                raise ValueError(
                    f"cluster {cluster_id}: stored fingerprint does not match members"
                )
            row["cluster_fingerprint"] = fingerprint
            row["analysis_hash"] = computed_analysis_hash

    passports: dict[tuple[str, str], EconomicPassport] = {}
    warnings: list[dict[str, Any]] = []
    for row in rows:
        raw = row.get("economic_passport")
        matches = [
            item
            for item in (row.get("known_use_case_matches") or [])
            if item.get("accepted")
        ]
        if not isinstance(raw, dict) or not matches:
            continue
        target_id = str(matches[0]["id"])
        key = ("known_use_case", target_id)
        converted = _economic_passport_from_analysis(
            raw,
            target_type="known_use_case",
            target_id=target_id,
        )
        previous = passports.get(key)
        if previous and previous.model_dump() != converted.model_dump():
            raise ValueError(f"conflicting embedded passport for {target_id}")
        passports[key] = converted

    clusters_path = directory / "clusters.json"
    clusters = read_json(clusters_path)
    if not isinstance(clusters, list):
        raise ValueError("clusters.json must contain a JSON array")
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        cluster_id = str(cluster.get("cluster_id"))
        raw = cluster.get("economic_passport")
        binding = bindings.get(cluster_id)
        if not isinstance(raw, dict) or binding is None:
            continue
        for field in (
            "source_model",
            "source_model_revision",
            "source_prompt_version",
        ):
            stored = cluster.get(field)
            if stored:
                binding[field] = str(stored)
        fingerprint = binding["cluster_fingerprint"]
        passports[("cluster", fingerprint)] = _economic_passport_from_analysis(
            raw,
            target_type="cluster",
            target_id=fingerprint,
            binding=binding,
        )

    return (
        PassportFile(schema_version="1.0", passports=list(passports.values())),
        bindings,
        warnings,
    )


def merge_passports(
    automatic: PassportFile,
    override: PassportFile | None,
    cluster_bindings: dict[str, dict[str, str]],
) -> PassportFile:
    """Merge explicit overrides while rejecting unbound or stale cluster passports."""
    merged = {
        (item.target_type, item.target_id): item for item in automatic.passports
    }
    if override is None:
        return PassportFile(schema_version="1.0", passports=list(merged.values()))
    binding_by_fingerprint = {
        value["cluster_fingerprint"]: value for value in cluster_bindings.values()
    }
    for passport in override.passports:
        if passport.target_type == "cluster":
            fingerprint = passport.cluster_fingerprint
            if not fingerprint or fingerprint not in binding_by_fingerprint:
                raise ValueError(
                    "cluster passport is not bound to this analysis: "
                    f"target_id={passport.target_id}"
                )
            expected = binding_by_fingerprint[fingerprint]
            for field in (
                "analysis_dataset_id",
                "analysis_hash",
                "analysis_configuration_hash",
                "member_run_ids_hash",
                "source_model",
                "source_model_revision",
                "source_prompt_version",
            ):
                if getattr(passport, field) != expected[field]:
                    raise ValueError(
                        f"cluster passport binding mismatch for {field}: "
                        f"target_id={passport.target_id}"
                    )
            passport = passport.model_copy(update={"target_id": fingerprint})
        merged[(passport.target_type, passport.target_id)] = passport
    return PassportFile(schema_version="1.0", passports=list(merged.values()))


def load_quality(path: Path | None) -> dict[str, QualityEvaluation]:
    if path is None:
        return {}
    evaluations = [
        QualityEvaluation.model_validate(item) for item in read_jsonl(path)
    ]
    by_run: dict[str, QualityEvaluation] = {}
    for item in evaluations:
        if item.run_id in by_run:
            raise ValueError(f"duplicate quality evaluation: {item.run_id}")
        by_run[item.run_id] = item
    return by_run


def load_financial_config(path: Path) -> FinancialConfig:
    return FinancialConfig.model_validate(read_json(path))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
