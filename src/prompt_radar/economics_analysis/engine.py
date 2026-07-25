"""Run, cluster and platform economic ledgers."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

import numpy as np

from prompt_radar.economics_analysis.allocation import allocate_costs
from prompt_radar.economics_analysis.formulas import (
    actual_saved_minutes,
    break_even_quality,
    dec,
    economic_values,
    max_affordable_ai_minutes,
    max_affordable_cost,
    metric,
    money,
    platform_scenarios,
    potential_saved_minutes,
    safe_ratio,
)
from prompt_radar.economics_analysis.models import (
    EconomicPassport,
    FinancialConfig,
    PassportFile,
    QualityEvaluation,
)
from prompt_radar.economics_analysis.quality import (
    EVIDENCE_RANK,
    lowest_evidence,
    quality_summary,
)


def _passport_index(
    passport_file: PassportFile,
) -> dict[tuple[str, str], EconomicPassport]:
    return {
        (item.target_type, item.target_id): item
        for item in passport_file.passports
    }


def _target(
    row: dict[str, Any],
    config: FinancialConfig,
) -> tuple[str | None, str | None, str | None]:
    matches = row.get("known_use_case_matches") or []
    accepted = [item for item in matches if item.get("accepted")]
    if row.get("classification_status") == "matched_known" and accepted:
        if row.get("multiple_goals"):
            return None, None, None
        top_score = accepted[0].get("similarity_score")
        threshold = accepted[0].get(
            "threshold_used", row.get("classification_threshold")
        )
        if (
            top_score is not None
            and threshold is not None
            and float(top_score) - float(threshold)
            < config.minimum_economic_classification_margin
        ):
            return None, None, None
        if len(accepted) > 1:
            second_score = accepted[1].get("similarity_score")
            if (
                top_score is None
                or second_score is None
                or float(top_score) - float(second_score)
                < config.minimum_economic_classification_margin
            ):
                return None, None, None
        item = accepted[0]
        return "known_use_case", str(item["id"]), str(item["name"])
    cluster_id = row.get("cluster_id")
    if isinstance(cluster_id, int) and cluster_id >= 0:
        fingerprint = row.get("cluster_fingerprint")
        if not fingerprint:
            return None, None, None
        return (
            "cluster",
            str(fingerprint),
            str(row.get("cluster_name") or f"Cluster {cluster_id}"),
        )
    primary = row.get("primary_category")
    if isinstance(primary, dict) and primary.get("id"):
        return "category", str(primary["id"]), str(primary.get("name", ""))
    return None, None, None


def _run_status(row: dict[str, Any]) -> str:
    metadata = row.get("run_metadata") or {}
    return str(metadata.get("status") or ("unknown" if metadata.get("is_fallback") else "unknown"))


def _wall_minutes(
    row: dict[str, Any],
) -> tuple[float | None, dict[str, Any] | None]:
    metadata = row.get("run_metadata") or {}
    started = metadata.get("started_at")
    finished = metadata.get("finished_at")
    if not started or not finished:
        return None, None
    start = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
    finish = datetime.fromisoformat(str(finished).replace("Z", "+00:00"))
    minutes = (finish - start).total_seconds() / 60
    if minutes < 0:
        raise ValueError(f"{row['run_id']}: finished_at precedes started_at")
    return minutes, {
        "value": minutes,
        "source": "run_metadata.finished_at-started_at",
        "evidence_level": "E1",
    }


def _prompt_minutes(
    row: dict[str, Any],
    evaluation: QualityEvaluation | None,
    config: FinancialConfig,
) -> tuple[float | None, str | None]:
    if evaluation and evaluation.prompt_minutes is not None:
        return evaluation.prompt_minutes, "quality_evaluation"
    run_metadata = row.get("run_metadata") or {}
    nested = run_metadata.get("metadata") or {}
    for source, mapping in (("run_metadata", run_metadata), ("run_metadata.metadata", nested)):
        if isinstance(mapping, dict) and mapping.get("prompt_minutes") is not None:
            value = float(mapping["prompt_minutes"])
            if value < 0:
                raise ValueError(f"{row['run_id']}: negative prompt_minutes")
            return value, source
    if config.default_prompt_minutes is not None:
        return config.default_prompt_minutes, "cost_config.default_prompt_minutes"
    return None, None


def _status(
    *,
    missing: list[str],
    potential: dict[str, Any] | None,
    break_even: dict[str, float | None] | None,
    roi_lower: float | None,
    roi_upper: float | None,
    evidence: str,
    evaluated: int,
    coverage: float,
    config: FinancialConfig,
    manual_base: float | None,
    ai_wall: float | None = None,
    max_ai_base: float | None = None,
) -> tuple[str, str, list[str]]:
    failed: list[str] = []
    if missing or potential is None or break_even is None:
        return "INSUFFICIENT_EVIDENCE", "Обязательные данные отсутствуют.", missing
    reliable = (
        EVIDENCE_RANK[evidence] >= EVIDENCE_RANK["E2"]
        and evaluated >= config.minimum_proven_evaluations
        and coverage >= config.minimum_proven_coverage
    )
    if reliable and roi_lower is not None and roi_lower > 0:
        return "PROVEN_EFFECTIVE", "Нижняя граница ROI положительна при E2+.", []
    if reliable and roi_upper is not None and roi_upper < 0:
        return "PROVEN_INEFFECTIVE", "Верхняя граница ROI отрицательна.", []
    if reliable and roi_lower is not None and roi_upper is not None and roi_lower <= 0 <= roi_upper:
        return "INCONCLUSIVE", "Доверительный интервал ROI пересекает ноль.", []
    q_high = break_even.get("high")
    q_base = break_even.get("base")
    if q_high is not None and q_high > 1:
        return "IMPOSSIBLE_TO_BREAK_EVEN", "Даже оптимистичный q_break_even > 1.", []
    base = potential["base"]
    high = potential["high"]
    if base["net_value"] < 0 < high["net_value"]:
        return "POTENTIALLY_INEFFECTIVE", "BASE отрицателен, но диапазон пересекает ноль.", []
    if q_base is not None and q_base >= config.high_risk_threshold:
        return "HIGH_RISK", "Требуемое качество близко к 100%.", []
    if manual_base is not None and manual_base <= config.simple_automation_manual_minutes and base["net_value"] < 0:
        return "USE_SIMPLE_AUTOMATION", "Малое ручное время при непропорциональной стоимости.", []
    if base["saved_minutes"] > 0 and base["net_value"] < 0:
        return "OPTIMIZE_COST", "Экономия времени положительна, но стоимость уничтожает ROI.", []
    if (
        base["net_value"] > 0
        and ai_wall is not None
        and max_ai_base is not None
        and max_ai_base > 0
        and ai_wall >= 0.8 * max_ai_base
    ):
        return "OPTIMIZE_LATENCY", "Wall-clock близок к максимально допустимому времени.", []
    if base["roi"] is not None and base["roi"] > 0 and (q_base is None or q_base <= 1):
        return "POTENTIALLY_EFFECTIVE", "BASE-потенциал положителен, доказанного качества недостаточно.", []
    failed.append("positive_potential_roi")
    return "INSUFFICIENT_EVIDENCE", "Нет положительного или доказанного эффекта.", failed


def build_run_ledger(
    rows: list[dict[str, Any]],
    passports: PassportFile,
    quality: dict[str, QualityEvaluation],
    config: FinancialConfig,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    allocations, reconciliation, warnings = allocate_costs(rows, config)
    passport_by_target = _passport_index(passports)
    labor_per_minute = dec(config.employee_cost_per_hour) / Decimal(60)
    ledger: list[dict[str, Any]] = []
    for row in rows:
        run_id = str(row["run_id"])
        evaluation = quality.get(run_id)
        target_type, target_id, target_name = _target(row, config)
        passport = passport_by_target.get((target_type, target_id)) if target_type and target_id else None
        if passport and (passport.abstain or not passport.is_coherent_cluster):
            passport = None
        wall, wall_provenance = _wall_minutes(row)
        prompt, prompt_source = _prompt_minutes(row, evaluation, config)
        missing: list[str] = []
        if passport is None:
            missing.append("economic_passport")
        if prompt is None:
            missing.append("prompt_minutes")
            warnings.append(
                {
                    "run_id": run_id,
                    "code": "missing_prompt_minutes",
                    "message": "prompt_minutes is unknown and was not replaced with zero",
                }
            )
        if wall is None and not (evaluation and evaluation.active_wait_minutes is not None):
            missing.append("ai_wall_minutes")
        allocation = allocations[run_id]
        scenario_specs = {
            "low": ("low", "high", "high", dec(allocation["maximum_fully_loaded_cost"])),
            "base": ("base", "base", "base", dec(allocation["fully_loaded_cost"])),
            "high": ("high", "low", "low", dec(allocation["minimum_fully_loaded_cost"])),
        }
        potential: dict[str, Any] | None = None
        q_break_even: dict[str, float | None] | None = None
        max_costs: dict[str, float | None] | None = None
        max_ai: dict[str, float | None] | None = None
        active_waits: dict[str, float | None] = {}
        if passport is not None:
            for name, (_, _, ratio_key, _) in scenario_specs.items():
                if evaluation and evaluation.active_wait_minutes is not None:
                    active_waits[name] = evaluation.active_wait_minutes
                elif wall is not None:
                    active_waits[name] = float(
                        getattr(passport.active_wait_ratio, ratio_key) * wall
                    )
                else:
                    active_waits[name] = None
        if passport is not None and prompt is not None and all(
            value is not None for value in active_waits.values()
        ):
            potential = {}
            q_break_even = {}
            max_costs = {}
            max_ai = {}
            for name, (manual_key, followup_key, ratio_key, run_cost) in scenario_specs.items():
                manual = dec(getattr(passport.manual_minutes, manual_key))
                followup = dec(getattr(passport.human_followup_minutes, followup_key))
                ratio = dec(getattr(passport.active_wait_ratio, ratio_key))
                active_wait = dec(active_waits[name])
                wall_value = dec(wall or 0)
                saved = potential_saved_minutes(
                    Decimal(1), manual, dec(prompt), active_wait, followup
                )
                potential[name] = economic_values(saved, labor_per_minute, run_cost)
                qbe = break_even_quality(
                    manual,
                    dec(prompt),
                    wall_value,
                    ratio,
                    followup,
                    run_cost,
                    labor_per_minute,
                )
                q_break_even[name] = metric(qbe)
                max_costs[name] = money(
                    max_affordable_cost(
                        Decimal(1),
                        manual,
                        dec(prompt),
                        wall_value,
                        ratio,
                        followup,
                        labor_per_minute,
                    )
                )
                max_ai[name] = metric(
                    max_affordable_ai_minutes(
                        Decimal(1),
                        manual,
                        dec(prompt),
                        followup,
                        run_cost,
                        labor_per_minute,
                        ratio,
                    )
                )
                if qbe is not None and qbe < 0:
                    warnings.append(
                        {
                            "run_id": run_id,
                            "code": "negative_break_even_quality",
                            "message": "q_break_even < 0 indicates inconsistent inputs",
                        }
                    )
        actual = None
        incremental = None
        quality_score = evaluation.quality_score if evaluation else None
        if (
            evaluation is not None
            and passport is not None
            and prompt is not None
            and active_waits.get("base") is not None
        ):
            saved = actual_saved_minutes(
                dec(passport.manual_minutes.base),
                dec(prompt),
                dec(active_waits["base"]),
                dec(evaluation.review_minutes),
                dec(evaluation.rework_minutes),
            )
            actual = economic_values(
                saved, labor_per_minute, dec(allocation["fully_loaded_cost"])
            )
            if (
                evaluation.human_minutes_web is not None
                and evaluation.web_cost is not None
            ):
                agent_human = (
                    dec(prompt)
                    + dec(active_waits["base"])
                    + dec(evaluation.review_minutes)
                    + dec(evaluation.rework_minutes)
                )
                delta_minutes = dec(evaluation.human_minutes_web) - agent_human
                delta_value = delta_minutes * labor_per_minute
                delta_cost = (
                    dec(allocation["fully_loaded_cost"])
                    - dec(evaluation.web_cost)
                )
                incremental_roi = safe_ratio(
                    delta_value - delta_cost, delta_cost
                )
                incremental = {
                    "delta_minutes": metric(delta_minutes),
                    "delta_value": money(delta_value),
                    "delta_cost": money(delta_cost),
                    "incremental_roi": metric(incremental_roi),
                }
        combined_evidence = lowest_evidence(
            [
                level
                for level in (
                    passport.evidence_level if passport else None,
                    evaluation.evidence_level if evaluation else None,
                )
                if level
            ],
            default="E0",
        )
        status, reason, failed_conditions = _status(
            missing=missing,
            potential=potential,
            break_even=q_break_even,
            roi_lower=None,
            roi_upper=None,
            evidence=combined_evidence,
            evaluated=1 if evaluation else 0,
            coverage=1.0 if evaluation else 0.0,
            config=config,
            manual_base=passport.manual_minutes.base if passport else None,
            ai_wall=wall,
            max_ai_base=max_ai.get("base") if max_ai else None,
        )
        run_telemetry = {
            key: (row.get("run_metadata") or {}).get("metadata", {}).get(key)
            for key in (
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "model_calls",
                "retry_count",
                "retry_cost_rub",
                "repeated_tool_call_count",
                "repeated_tool_call_cost_rub",
                "tool_error_count",
                "tool_error_cost_rub",
                "excess_context_cost_rub",
                "model_tier",
            )
        }
        if (
            run_telemetry["input_tokens"] is None
            and run_telemetry["total_tokens"] is None
            and isinstance(row.get("raw_prompt_token_count"), (int, float))
        ):
            run_telemetry["input_tokens"] = row["raw_prompt_token_count"]
            run_telemetry["token_source"] = "analysis.raw_prompt_token_count"
        ledger.append(
            {
                "schema_version": "1.0",
                "run_id": run_id,
                "conversation_id": row.get("conversation_id"),
                "user_id": row.get("user_id"),
                "target_type": target_type,
                "target_id": target_id,
                "target_name": passport.cluster_name if passport else target_name,
                "discovery_status": row.get("discovery_status"),
                "run_status": _run_status(row),
                "manual_minutes": passport.manual_minutes.model_dump() if passport else None,
                "human_followup_minutes": passport.human_followup_minutes.model_dump() if passport else None,
                "prompt_minutes": prompt,
                "ai_wall_minutes": wall,
                "active_wait_minutes": active_waits or None,
                "review_minutes": evaluation.review_minutes if evaluation else None,
                "rework_minutes": evaluation.rework_minutes if evaluation else None,
                "quality_score": quality_score,
                "quality_evidence": evaluation.evidence_level if evaluation else None,
                "quality_evaluation_source": evaluation.evaluation_source if evaluation else None,
                "marginal_cost": allocation["marginal_cost"],
                "fully_loaded_cost": allocation["fully_loaded_cost"],
                "cost_scenarios": allocation["scenario_fully_loaded_costs"],
                "gpu_allocation_method": allocation["gpu_allocation_method"],
                "potential": potential,
                "actual": actual,
                "incremental_comparison": incremental,
                "incremental_comparison_unavailable": incremental is None,
                "break_even_quality": q_break_even,
                "max_affordable_run_cost": max_costs,
                "max_affordable_ai_minutes": max_ai,
                "status": status,
                "status_reason": reason,
                "failed_conditions": failed_conditions,
                "evidence_level": combined_evidence,
                "missing_evidence": missing,
                "assumptions": passport.assumptions if passport else [],
                "uncertainty_drivers": passport.uncertainty_drivers if passport else [],
                "provenance": {
                    "passport": (
                        {
                            "target_type": passport.target_type,
                            "target_id": passport.target_id,
                            "evidence_level": passport.evidence_level,
                            "owner": passport.owner,
                            "valid_from": passport.valid_from.isoformat() if passport.valid_from else None,
                            "valid_to": passport.valid_to.isoformat() if passport.valid_to else None,
                        }
                        if passport
                        else None
                    ),
                    "prompt_minutes": prompt_source,
                    "ai_wall_minutes": wall_provenance,
                    "active_wait_minutes": (
                        "quality_evaluation"
                        if evaluation and evaluation.active_wait_minutes is not None
                        else "passport_ratio_x_ai_wall"
                    ),
                    "cost": allocation,
                },
                "telemetry": run_telemetry,
            }
        )
    return ledger, reconciliation, warnings


def _aggregate_economic_values(
    records: list[dict[str, Any]], scenario: str
) -> dict[str, float | None]:
    saved = sum(dec(item["potential"][scenario]["saved_minutes"]) for item in records)
    labor = sum(dec(item["potential"][scenario]["labor_value"]) for item in records)
    cost_key = {
        "low": "maximum_fully_loaded_cost",
        "base": "fully_loaded_cost",
        "high": "minimum_fully_loaded_cost",
    }[scenario]
    cost = sum(dec(item["provenance"]["cost"][cost_key]) for item in records)
    net = labor - cost
    roi = safe_ratio(net, cost)
    return {
        "saved_minutes": metric(saved),
        "saved_hours": metric(saved / Decimal(60)),
        "labor_value": money(labor),
        "cost": money(cost),
        "net_value": money(net),
        "roi": metric(roi),
        "roi_percent": metric(roi * Decimal(100)) if roi is not None else None,
    }


def _aggregate_break_even_quality(
    records: list[dict[str, Any]], config: FinancialConfig
) -> dict[str, float | None]:
    """Solve the aggregate cluster break-even equation per scenario."""
    labor_per_minute = dec(config.employee_cost_per_hour) / Decimal(60)
    scenario_fields = {
        "low": ("low", "high", "low", "maximum_fully_loaded_cost"),
        "base": ("base", "base", "base", "fully_loaded_cost"),
        "high": ("high", "low", "high", "minimum_fully_loaded_cost"),
    }
    result: dict[str, float | None] = {}
    for name, (
        manual_key,
        followup_key,
        wait_key,
        cost_key,
    ) in scenario_fields.items():
        numerator = Decimal(0)
        denominator = Decimal(0)
        for item in records:
            manual = item["manual_minutes"]
            followup = item["human_followup_minutes"]
            prompt = item["prompt_minutes"]
            waits = item["active_wait_minutes"]
            if (
                manual is None
                or followup is None
                or prompt is None
                or waits is None
            ):
                continue
            denominator += dec(manual[manual_key])
            numerator += (
                dec(prompt)
                + dec(waits[wait_key])
                + dec(followup[followup_key])
                + dec(item["provenance"]["cost"][cost_key])
                / labor_per_minute
            )
        result[name] = metric(
            numerator / denominator if denominator > 0 else None
        )
    return result


def aggregate_clusters(
    ledger: list[dict[str, Any]],
    quality: dict[str, QualityEvaluation],
    config: FinancialConfig,
    warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in ledger:
        key = (str(item["target_type"] or "unresolved"), str(item["target_id"] or item["run_id"]))
        groups[key].append(item)
    clusters: list[dict[str, Any]] = []
    for (target_type, target_id), records in sorted(groups.items()):
        valid = [item for item in records if item["potential"] is not None]
        evaluations = [quality[item["run_id"]] for item in records if item["run_id"] in quality]
        qs = quality_summary(
            evaluations,
            seed=config.bootstrap_seed,
            iterations=config.bootstrap_iterations,
        )
        coverage = len(evaluations) / len(records)
        if 0 < len(evaluations) < config.minimum_proven_evaluations:
            warnings.append(
                {
                    "target_type": target_type,
                    "target_id": target_id,
                    "code": "small_quality_sample",
                    "message": "Quality sample is too small for a proven claim",
                }
            )
        potential = (
            {name: _aggregate_economic_values(valid, name) for name in ("low", "base", "high")}
            if valid
            else None
        )
        roi_lower = None
        roi_upper = None
        if valid and qs["quality_ci_low"] is not None:
            low_saved = Decimal(0)
            high_saved = Decimal(0)
            low_cost = Decimal(0)
            high_cost = Decimal(0)
            for item in valid:
                p = item["manual_minutes"]
                f = item["human_followup_minutes"]
                prompt = item["prompt_minutes"]
                wall = item["ai_wall_minutes"]
                ratios = item["active_wait_minutes"]
                if prompt is None or wall is None or ratios is None:
                    continue
                low_saved += (
                    dec(qs["quality_ci_low"]) * dec(p["low"])
                    - dec(prompt)
                    - dec(ratios["low"])
                    - dec(f["high"])
                )
                high_saved += (
                    dec(qs["quality_ci_high"]) * dec(p["high"])
                    - dec(prompt)
                    - dec(ratios["high"])
                    - dec(f["low"])
                )
                low_cost += dec(item["provenance"]["cost"]["maximum_fully_loaded_cost"])
                high_cost += dec(item["provenance"]["cost"]["minimum_fully_loaded_cost"])
            labor_per_minute = dec(config.employee_cost_per_hour) / Decimal(60)
            lower_net = low_saved * labor_per_minute - low_cost
            upper_net = high_saved * labor_per_minute - high_cost
            roi_lower = metric(safe_ratio(lower_net, low_cost))
            roi_upper = metric(safe_ratio(upper_net, high_cost))
        qbe = None
        if valid:
            qbe = _aggregate_break_even_quality(valid, config)
        missing = sorted({value for item in records for value in item["missing_evidence"]})
        overall_evidence = lowest_evidence(
            [str(item["evidence_level"]) for item in records]
        )
        status, reason, failed = _status(
            missing=missing,
            potential=potential,
            break_even=qbe,
            roi_lower=roi_lower,
            roi_upper=roi_upper,
            evidence=overall_evidence,
            evaluated=len(evaluations),
            coverage=coverage,
            config=config,
            manual_base=records[0]["manual_minutes"]["base"] if records[0]["manual_minutes"] else None,
        )
        durations = [item["ai_wall_minutes"] for item in records if item["ai_wall_minutes"] is not None]
        statuses = Counter(item["run_status"] for item in records)
        clusters.append(
            {
                "schema_version": "1.0",
                "target_type": target_type,
                "target_id": target_id,
                "name": records[0]["target_name"],
                "run_count": len(records),
                "user_count": len({item["user_id"] for item in records}),
                "conversation_count": len({item["conversation_id"] for item in records}),
                "run_status_counts": dict(statuses),
                "manual_minutes": records[0]["manual_minutes"],
                "human_followup_minutes": records[0]["human_followup_minutes"],
                "evaluated_run_count": len(evaluations),
                "evaluation_coverage": coverage,
                **qs,
                "mean_ai_wall_minutes": sum(durations) / len(durations) if durations else None,
                "p90_ai_wall_minutes": float(np.percentile(durations, 90)) if durations else None,
                "potential": potential,
                "roi_lower": roi_lower,
                "roi_base": potential["base"]["roi"] if potential else None,
                "roi_upper": roi_upper,
                "break_even_quality": qbe,
                "marginal_cost": money(sum(dec(item["marginal_cost"]) for item in records)),
                "fully_loaded_cost": money(sum(dec(item["fully_loaded_cost"]) for item in records)),
                "status": status,
                "status_reason": reason,
                "failed_conditions": failed,
                "missing_evidence": missing,
                "quality_evidence_level": qs["evidence_level"],
                "evidence_level": overall_evidence,
                "actual_evaluated": _aggregate_actual(records),
                "recommendations": _recommendations(status, missing),
            }
        )
    return clusters


def _recommendations(status: str, missing: list[str]) -> list[str]:
    values: list[str] = []
    if missing:
        values.append("Собрать недостающие доказательства: " + ", ".join(missing))
    mapping = {
        "OPTIMIZE_COST": "Снизить стоимость модели, инструментов или число вызовов.",
        "HIGH_RISK": "Повысить качество и проверить сценарий на большей выборке.",
        "USE_SIMPLE_AUTOMATION": "Сравнить агент с простым скриптом или правилом.",
        "IMPOSSIBLE_TO_BREAK_EVEN": "Пересмотреть baseline, стоимость и границы сценария.",
        "INCONCLUSIVE": "Увеличить проверенную выборку и провести E2/E3 сравнение.",
    }
    if status in mapping:
        values.append(mapping[status])
    return values or ["Продолжить наблюдение качества и стоимости."]


def _aggregate_actual(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    evaluated = [item for item in records if item.get("actual") is not None]
    if not evaluated:
        return None
    saved = sum(dec(item["actual"]["saved_minutes"]) for item in evaluated)
    labor = sum(dec(item["actual"]["labor_value"]) for item in evaluated)
    cost = sum(dec(item["fully_loaded_cost"]) for item in evaluated)
    net = labor - cost
    roi = safe_ratio(net, cost)
    return {
        "scope": "evaluated_runs_only",
        "evaluated_run_count": len(evaluated),
        "saved_minutes": metric(saved),
        "labor_value": money(labor),
        "cost": money(cost),
        "net_value": money(net),
        "roi": metric(roi),
    }


def build_value_leakage(
    ledger: list[dict[str, Any]], config: FinancialConfig
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    labor_per_minute = dec(config.employee_cost_per_hour) / Decimal(60)
    for item in ledger:
        confirmed = Decimal(0)
        opportunity = Decimal(0)
        reasons: list[str] = []
        status = item["run_status"]
        if status in {"failed", "cancelled"}:
            confirmed += dec(item["marginal_cost"])
            opportunity += dec(item["fully_loaded_cost"]) - dec(item["marginal_cost"])
            reasons.append(f"{status}_run_cost")
        elif status == "partial":
            opportunity += dec(item["fully_loaded_cost"])
            reasons.append("partial_run_cost")
        if item["review_minutes"] is not None:
            opportunity += dec(item["review_minutes"]) * labor_per_minute
            reasons.append("human_review_cost")
        if item["rework_minutes"] is not None:
            opportunity += dec(item["rework_minutes"]) * labor_per_minute
            reasons.append("rework_cost")
        active = (item["active_wait_minutes"] or {}).get("base") if item["active_wait_minutes"] else None
        if active is not None:
            opportunity += dec(active) * labor_per_minute
            reasons.append("active_wait_cost")
        telemetry = item.get("telemetry") or {}
        for count_key, cost_key, signal in (
            ("retry_count", "retry_cost_rub", "retry_cost"),
            (
                "repeated_tool_call_count",
                "repeated_tool_call_cost_rub",
                "repeated_tool_call_cost",
            ),
            ("tool_error_count", "tool_error_cost_rub", "tool_error_cost"),
        ):
            if telemetry.get(count_key):
                explicit_cost = dec(telemetry.get(cost_key) or 0)
                confirmed += explicit_cost
                reasons.append(signal)
        total_tokens = (
            telemetry.get("total_tokens")
            or (
                (telemetry.get("input_tokens") or 0)
                + (telemetry.get("output_tokens") or 0)
            )
        )
        if total_tokens > config.excessive_context_tokens:
            opportunity += dec(telemetry.get("excess_context_cost_rub") or 0)
            reasons.append("excessive_context_token_opportunity")
        if status in {"pending", "running", "abandoned", "unknown"}:
            opportunity += dec(item["fully_loaded_cost"])
            reasons.append("run_without_terminal_outcome")
        manual_base = (item.get("manual_minutes") or {}).get("base")
        if (
            telemetry.get("model_tier") == "expensive"
            and manual_base is not None
            and manual_base <= config.simple_automation_manual_minutes
        ):
            reasons.append("expensive_model_on_simple_task")
        if reasons:
            items.append(
                {
                    "run_id": item["run_id"],
                    "confirmed_wasted_cost": money(confirmed),
                    "optimization_opportunity_cost": money(opportunity),
                    "signals": reasons,
                }
            )
    return {
        "confirmed_wasted_cost": money(sum(dec(item["confirmed_wasted_cost"]) for item in items)),
        "optimization_opportunity_cost": money(
            sum(dec(item["optimization_opportunity_cost"]) for item in items)
        ),
        "items": items,
    }


def aggregate_platform(
    ledger: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    reconciliation: dict[str, Any],
    leakage: dict[str, Any],
    config: FinancialConfig,
) -> dict[str, Any]:
    valid = [item for item in ledger if item["potential"] is not None]
    idle_license = dec(reconciliation["licenses"]["unallocated_idle_license_cost"])
    total_input_tokens = Decimal(0)
    total_output_tokens = Decimal(0)
    total_tokens = Decimal(0)
    for item in ledger:
        telemetry = item.get("telemetry") or {}
        input_tokens = dec(telemetry.get("input_tokens") or 0)
        output_tokens = dec(telemetry.get("output_tokens") or 0)
        combined = dec(
            telemetry.get("total_tokens")
            or (telemetry.get("input_tokens") or 0)
            + (telemetry.get("output_tokens") or 0)
        )
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens
        total_tokens += combined
    potential = None
    if valid:
        potential = {}
        for scenario in ("low", "base", "high"):
            partial = _aggregate_economic_values(valid, scenario)
            cost_key = {
                "low": "maximum_fully_loaded_cost",
                "base": "fully_loaded_cost",
                "high": "minimum_fully_loaded_cost",
            }[scenario]
            total_cost = (
                sum(dec(item["provenance"]["cost"][cost_key]) for item in ledger)
                + idle_license
            )
            labor = dec(partial["labor_value"])
            net = labor - total_cost
            roi = safe_ratio(net, total_cost)
            potential[scenario] = {
                **partial,
                "cost": money(total_cost),
                "net_value": money(net),
                "roi": metric(roi),
                "roi_percent": metric(roi * Decimal(100)) if roi is not None else None,
            }
    fte_month_minutes = (
        dec(config.working_days_per_month) * dec(config.working_hours_per_day) * Decimal(60)
    )
    base_saved = dec((potential or {}).get("base", {}).get("saved_minutes") or 0)
    fte_months_saved = (
        safe_ratio(base_saved, fte_month_minutes) if fte_month_minutes > 0 else None
    )
    fte_value_rub = (
        fte_months_saved * dec(config.average_fte_month_cost_rub)
        if fte_months_saved is not None
        else None
    )
    fully_loaded_platform_period_cost = money(
        sum(dec(item["fully_loaded_cost"]) for item in ledger) + idle_license
    )
    token_cost_full = safe_ratio(dec(fully_loaded_platform_period_cost), total_tokens)
    token_cost_allocated = safe_ratio(
        dec(sum(dec(item["fully_loaded_cost"]) for item in ledger)), total_tokens
    )
    statuses = Counter(item["run_status"] for item in ledger)
    cluster_statuses = Counter(item["status"] for item in clusters)
    return {
        "schema_version": "1.0",
        "platform_cost_scenarios": platform_scenarios(config),
        "selected_platform_scenario": config.default_gpu_allocation_scenario,
        "analysis_period_months": reconciliation["analysis_period_months"],
        "gpu_allocation_method": reconciliation["gpu_allocation_method"],
        "token_allocation_is_proxy": reconciliation["token_allocation_is_proxy"],
        "total_runs": len(ledger),
        "run_status_counts": dict(statuses),
        "failed_partial_cancelled_share": (
            sum(
                statuses.get(name, 0)
                for name in ("failed", "partial", "cancelled", "abandoned")
            )
            / len(ledger)
        ),
        "potential": potential,
        "overall_roi": potential["base"]["roi"] if potential else None,
        "allocated_cost": money(sum(dec(item["fully_loaded_cost"]) for item in ledger)),
        "fully_loaded_platform_period_cost": fully_loaded_platform_period_cost,
        "unallocated_idle_license_cost": reconciliation["licenses"]["unallocated_idle_license_cost"],
        "token_economics": {
            "input_tokens": int(total_input_tokens),
            "output_tokens": int(total_output_tokens),
            "total_tokens": int(total_tokens),
            "allocated_cost_per_token_rub": metric(token_cost_allocated),
            "full_cost_per_token_rub": metric(token_cost_full),
            "allocated_cost_per_1k_tokens_rub": (
                metric(token_cost_allocated * Decimal(1000))
                if token_cost_allocated is not None
                else None
            ),
            "full_cost_per_1k_tokens_rub": (
                metric(token_cost_full * Decimal(1000))
                if token_cost_full is not None
                else None
            ),
            "allocated_cost_per_million_tokens_rub": (
                money(token_cost_allocated * Decimal(1000000))
                if token_cost_allocated is not None
                else None
            ),
            "full_cost_per_million_tokens_rub": (
                money(token_cost_full * Decimal(1000000))
                if token_cost_full is not None
                else None
            ),
        },
        "fte_view": {
            "working_days_per_month": config.working_days_per_month,
            "working_hours_per_day": config.working_hours_per_day,
            "average_fte_month_cost_rub": config.average_fte_month_cost_rub,
            "base_saved_fte_months": metric(fte_months_saved),
            "base_saved_value_rub_by_fte_month": money(fte_value_rub)
            if fte_value_rub is not None
            else None,
            "b_gt_a": (
                bool(fte_value_rub > dec(fully_loaded_platform_period_cost))
                if fte_value_rub is not None
                else None
            ),
        },
        "cluster_status_counts": dict(cluster_statuses),
        "proven_effective_cluster_share": cluster_statuses.get("PROVEN_EFFECTIVE", 0) / len(clusters) if clusters else 0,
        "proven_ineffective_cluster_share": cluster_statuses.get("PROVEN_INEFFECTIVE", 0) / len(clusters) if clusters else 0,
        "insufficient_evidence_cluster_share": cluster_statuses.get("INSUFFICIENT_EVIDENCE", 0) / len(clusters) if clusters else 0,
        "confirmed_wasted_cost": leakage["confirmed_wasted_cost"],
        "optimization_opportunity_cost": leakage["optimization_opportunity_cost"],
        "top_value_leakage": sorted(
            leakage["items"],
            key=lambda item: item["optimization_opportunity_cost"],
            reverse=True,
        )[:10],
        "incremental_comparison_unavailable": not any(
            item.get("incremental_comparison") for item in ledger
        ),
        "external_api_called": False,
    }
