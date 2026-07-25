"""Escaped executive Markdown report generation."""

from __future__ import annotations

import html
from collections import Counter, defaultdict
from typing import Any


def _safe(value: object, limit: int = 240) -> str:
    text = html.escape(str(value), quote=True).replace("|", "\\|")
    return text[:limit] + ("…" if len(text) > limit else "")


def _accepted_match(item: dict[str, Any]) -> dict[str, Any] | None:
    matches = item.get("known_use_case_matches") or []
    accepted = [match for match in matches if match.get("accepted")]
    return accepted[0] if accepted else None


def _run_status(item: dict[str, Any]) -> str:
    return str((item.get("run_metadata") or {}).get("status") or "unknown")


def _run_day(item: dict[str, Any]) -> str:
    started = str((item.get("run_metadata") or {}).get("started_at") or "")
    return started[:10] if len(started) >= 10 else "unknown"


def _problem_reasons(item: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    status = _run_status(item)
    if status in {"failed", "partial", "cancelled", "abandoned"}:
        reasons.append(status)
    if item.get("multiple_goals"):
        reasons.append("multi-goal")
    similarity = float(item.get("classification_similarity") or 0)
    threshold = float(item.get("classification_threshold") or 0)
    if (
        item.get("classification_status") == "matched_known"
        and similarity - threshold < 0.05
    ):
        reasons.append("low classification margin")
    if int(item.get("raw_prompt_token_count") or 0) >= 50_000:
        reasons.append("very long prompt")
    if str(item.get("run_id") or "").startswith("fallback:"):
        reasons.append("fallback run boundary")
    if item.get("discovery_status") == "unresolved":
        reasons.append("unresolved")
    if item.get("economic_abstention_reason"):
        reasons.append("economic abstention")
    return reasons


def _recommendations(
    analyses: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
) -> list[str]:
    recommendations: list[str] = []
    unresolved = sum(
        item.get("discovery_status") == "unresolved" for item in analyses
    )
    failed = sum(
        _run_status(item) in {"failed", "partial", "cancelled", "abandoned"}
        for item in analyses
    )
    low_margin = sum(
        "low classification margin" in _problem_reasons(item)
        for item in analyses
    )
    very_long = sum(
        int(item.get("raw_prompt_token_count") or 0) >= 50_000
        for item in analyses
    )
    abstained = sum(
        cluster.get("api_enrichment_status") == "precomputed_abstained"
        for cluster in clusters
    )
    if low_margin:
        recommendations.append(
            f"Review and calibrate known-use-case thresholds: {low_margin} "
            "runs have a classification margin below 0.05."
        )
    if unresolved:
        recommendations.append(
            f"Manually review {unresolved} unresolved runs and either extend "
            "the catalog or mark them as non-business noise."
        )
    if clusters:
        recommendations.append(
            f"Validate {len(clusters)} emerging cluster candidate(s) with "
            "process owners before adding them to the known catalog."
        )
    if abstained:
        recommendations.append(
            f"Recluster or split {abstained} incoherent cluster(s); do not "
            "assign one economic baseline to mixed business processes."
        )
    if failed:
        recommendations.append(
            f"Inspect {failed} failed/partial/cancelled/abandoned runs for "
            "agent reliability and tool-integration problems."
        )
    if very_long:
        recommendations.append(
            f"Optimize {very_long} prompts above 50k routed tokens using "
            "retrieval, context compression or reusable source indexes."
        )
    if not recommendations:
        recommendations.append(
            "No high-priority deterministic warning was found; continue "
            "monitoring frequency, quality and cost on the next period."
        )
    return recommendations


def build_markdown_report(
    *,
    dataset_id: str,
    analyses: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    model_id: str,
    model_revision: str,
    external_api_call_count: int,
) -> str:
    """Create a compact CTO-oriented report without rendering raw markup."""
    status_counts = Counter(item["discovery_status"] for item in analyses)
    mode_counts = Counter(item["processing_mode"] for item in analyses)
    run_status_counts = Counter(_run_status(item) for item in analyses)
    known_counts: Counter[tuple[str, str]] = Counter()
    category_counts: Counter[tuple[str, str]] = Counter()
    daily: dict[str, Counter[str]] = defaultdict(Counter)
    for item in analyses:
        match = _accepted_match(item)
        if match is not None:
            known_counts[(str(match.get("id")), str(match.get("name")))] += 1
        category = item.get("primary_category")
        if isinstance(category, dict) and category.get("id"):
            category_counts[
                (str(category["id"]), str(category.get("name") or category["id"]))
            ] += 1
        day = _run_day(item)
        daily[day]["runs"] += 1
        daily[day][str(item.get("discovery_status") or "unknown")] += 1
        daily[day][_run_status(item)] += 1
    problem_rows = [
        (item, _problem_reasons(item))
        for item in analyses
        if _problem_reasons(item)
    ]
    problem_rows.sort(
        key=lambda pair: (
            -len(pair[1]),
            -int(pair[0].get("raw_prompt_token_count") or 0),
            str(pair[0].get("run_id")),
        )
    )

    lines = [
        "# Prompt Radar — executive report",
        "",
        "> Результаты относятся к синтетическому или переданному набору. "
        "Cosine similarity не является вероятностью, а кластер требует "
        "проверки владельцем процесса.",
        "",
        "## Executive summary",
        "",
        f"- Dataset: `{_safe(dataset_id)}`",
        f"- Runs analyzed: {len(analyses)}",
        f"- Known: {status_counts.get('known', 0)}",
        f"- Emerging candidates: {status_counts.get('emerging', 0)}",
        f"- Unresolved: {status_counts.get('unresolved', 0)}",
        f"- Problem-signal runs: {len(problem_rows)}",
        f"- Failed/partial/cancelled/abandoned: "
        f"{sum(run_status_counts.get(value, 0) for value in ('failed', 'partial', 'cancelled', 'abandoned'))}",
        f"- Warnings: {len(warnings)}",
        f"- External cluster enrichment calls: {external_api_call_count}",
        "",
        "## Most frequent known use cases",
        "",
        "| Rank | Use case | Runs | Share |",
        "|---:|---|---:|---:|",
    ]
    for rank, ((_, name), count) in enumerate(
        known_counts.most_common(15), start=1
    ):
        share = count / len(analyses) if analyses else 0
        lines.append(
            f"| {rank} | {_safe(name)} | {count} | {share:.1%} |"
        )
    if not known_counts:
        lines.append("| — | No confident known matches | 0 | 0.0% |")

    lines.extend(
        [
            "",
            "## Category distribution",
            "",
            "| Category | Runs | Share |",
            "|---|---:|---:|",
        ]
    )
    for (_, name), count in category_counts.most_common():
        share = count / len(analyses) if analyses else 0
        lines.append(f"| {_safe(name)} | {count} | {share:.1%} |")
    if not category_counts:
        lines.append("| No primary category | 0 | 0.0% |")

    lines.extend(
        [
            "",
            "## Time dynamics",
            "",
            "| Day | Runs | Known | Emerging | Unresolved | Failed-like |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for day in sorted(daily):
        values = daily[day]
        failed_like = sum(
            values.get(status, 0)
            for status in ("failed", "partial", "cancelled", "abandoned")
        )
        lines.append(
            f"| {_safe(day)} | {values['runs']} | {values['known']} | "
            f"{values['emerging']} | {values['unresolved']} | {failed_like} |"
        )
    if len(daily) < 2:
        lines.extend(
            [
                "",
                "> Недостаточно двух временных периодов для доказательного "
                "вывода о росте или снижении сценариев.",
            ]
        )

    lines.extend(["", "## Emerging cluster candidates", ""])
    if not clusters:
        lines.append("No stable residual clusters were found.")
    else:
        for cluster in clusters:
            label = cluster.get("cluster_name") or cluster.get(
                "provisional_label"
            )
            lines.extend(
                [
                    f"### {_safe(label)}",
                    "",
                    f"- Stable fingerprint: `{_safe(cluster.get('cluster_fingerprint'))}`",
                    f"- Members: {cluster.get('member_count', 0)}",
                    f"- Label source: `{_safe(cluster.get('label_source', 'unknown'))}`",
                    f"- Enrichment status: `{_safe(cluster.get('api_enrichment_status', 'not_requested'))}`",
                    "- Keywords: "
                    + ", ".join(
                        f"`{_safe(word)}`"
                        for word in (cluster.get("keywords") or [])
                    ),
                ]
            )
            if cluster.get("enrichment_abstention_reason"):
                lines.append(
                    "- Abstention: "
                    + _safe(cluster["enrichment_abstention_reason"])
                )
            representatives = cluster.get("representative_examples") or []
            if representatives:
                lines.extend(["", "Representative tasks:"])
                for representative in representatives[:3]:
                    lines.append(
                        "- "
                        + _safe(
                            representative.get("task_passport_text")
                            or representative.get("run_id"),
                            limit=320,
                        )
                    )
            lines.append("")

    lines.extend(
        [
            "## Problem signals",
            "",
            "| Run | Signal | Status | Tokens | Goal |",
            "|---|---|---|---:|---|",
        ]
    )
    for item, reasons in problem_rows[:25]:
        lines.append(
            f"| {_safe(item.get('run_id'))} | {_safe(', '.join(reasons))} | "
            f"{_safe(_run_status(item))} | "
            f"{int(item.get('raw_prompt_token_count') or 0)} | "
            f"{_safe(item.get('current_goal'))} |"
        )
    if not problem_rows:
        lines.append("| — | No deterministic problem signal | — | 0 | — |")

    lines.extend(["", "## Recommended actions", ""])
    for index, recommendation in enumerate(
        _recommendations(analyses, clusters), start=1
    ):
        lines.append(f"{index}. {_safe(recommendation, limit=500)}")

    lines.extend(
        [
            "",
            "## Technical provenance",
            "",
            f"- Embedding model: `{_safe(model_id)}`",
            f"- Revision: `{_safe(model_revision)}`",
            "- Processing modes: "
            + ", ".join(
                f"`{_safe(mode)}`={count}"
                for mode, count in sorted(mode_counts.items())
            ),
            "- Full run-level evidence is available in "
            "`runs_analysis.jsonl/csv/parquet`; it is intentionally not "
            "duplicated into this executive report.",
            "",
            "## Interpretation limits",
            "",
            "- HDBSCAN groups vectors; it does not prove a business process.",
            "- Draft catalog mappings and thresholds require calibration.",
            "- External or precomputed estimates are hypotheses until reviewed.",
            "- ROI is calculated only by the separate `economics` command.",
            "- Images require OCR for text extraction.",
            "",
        ]
    )
    return "\n".join(lines)
