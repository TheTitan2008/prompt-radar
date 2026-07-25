"""Human-readable evidence-aware economics report."""

from __future__ import annotations

import html
from collections import Counter
from typing import Any


def _safe(value: object) -> str:
    if value is None:
        return "n/a"
    return html.escape(str(value), quote=True).replace("|", "\\|")


def _target_name(item: dict[str, Any]) -> str:
    return str(item.get("name") or item.get("target_id") or "unknown")


def _has_potential(item: dict[str, Any]) -> bool:
    return bool(((item.get("potential") or {}).get("base") or {}).get("roi") is not None)


def build_economics_report(
    *,
    platform: dict[str, Any],
    clusters: list[dict[str, Any]],
    ledger: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> str:
    """Build a concise report that makes missing evidence visible."""
    base = (platform.get("potential") or {}).get("base") or {}
    token_economics = platform.get("token_economics") or {}
    fte_view = platform.get("fte_view") or {}
    total_runs = len(ledger)
    prompt_count = sum(item.get("prompt_minutes") is not None for item in ledger)
    prompt_assumed_count = sum(
        (item.get("provenance") or {}).get("prompt_minutes")
        == "cost_config.default_prompt_minutes"
        for item in ledger
    )
    prompt_measured_count = prompt_count - prompt_assumed_count
    passport_count = sum(item.get("manual_minutes") is not None for item in ledger)
    potential_count = sum(item.get("potential") is not None for item in ledger)
    actual_count = sum(item.get("actual") is not None for item in ledger)
    quality_count = sum(item.get("quality_score") is not None for item in ledger)
    missing = Counter(
        str(reason)
        for item in ledger
        for reason in (item.get("missing_evidence") or [])
    )

    lines = [
        "# Prompt Radar economics report",
        "",
        "> Qwen/DeepSeek estimates are E0 hypotheses. They do not prove savings "
        "until the output is checked and the manual baseline is validated.",
        "",
        "## Executive summary",
        "",
        f"- Runs: {platform['total_runs']}",
        f"- Analysis period: {_safe(platform.get('analysis_period_months'))} months",
        f"- Selected cost scenario: `{_safe(platform['selected_platform_scenario'])}`",
        f"- GPU allocation: `{_safe(platform.get('gpu_allocation_method'))}`"
        + (" (proxy)" if platform.get("token_allocation_is_proxy") else ""),
        f"- Allocated fully loaded cost: {platform['allocated_cost']:.2f} RUB",
        f"- Idle license cost: {platform['unallocated_idle_license_cost']:.2f} RUB",
        f"- Potential BASE saved minutes: {_safe(base.get('saved_minutes'))}",
        f"- Potential BASE net value: {_safe(base.get('net_value'))} RUB",
        f"- Potential BASE ROI: {_safe(base.get('roi'))}",
        f"- Total tokens: {_safe(token_economics.get('total_tokens'))}",
        f"- Full cost per 1k tokens: {_safe(token_economics.get('full_cost_per_1k_tokens_rub'))} RUB",
        f"- Saved FTE-months (BASE): {_safe(fte_view.get('base_saved_fte_months'))}",
        f"- FTE-month value (BASE): {_safe(fte_view.get('base_saved_value_rub_by_fte_month'))} RUB",
        f"- B > A by FTE view: {_safe(fte_view.get('b_gt_a'))}",
        f"- Confirmed wasted cost: {platform['confirmed_wasted_cost']:.2f} RUB",
        f"- Optimization opportunity: {platform['optimization_opportunity_cost']:.2f} RUB",
        "",
        "## Data completeness",
        "",
        "| Evidence | Runs | Coverage |",
        "|---|---:|---:|",
    ]
    for label, count in (
        ("Prompt effort available (`prompt_minutes`)", prompt_count),
        ("Prompt effort measured", prompt_measured_count),
        ("Prompt effort assumed by cost config", prompt_assumed_count),
        ("Manual baseline / economic passport", passport_count),
        ("Potential calculation available", potential_count),
        ("Quality evaluated", quality_count),
        ("Actual calculation available", actual_count),
    ):
        coverage = count / total_runs if total_runs else 0.0
        lines.append(f"| {label} | {count}/{total_runs} | {coverage:.1%} |")

    if prompt_assumed_count:
        lines.extend(
            [
                "",
                f"> **Prompt effort is assumed for {prompt_assumed_count} runs, "
                "not measured.** Potential ROI is a sensitivity scenario and "
                "must not be presented as an observed result.",
            ]
        )

    if potential_count == 0:
        lines.extend(
            [
                "",
                "> **ROI is not calculable for this dataset yet.** Add "
                "`prompt_minutes` to run telemetry and validated manual-time "
                "baselines to economic passports. Missing values are deliberately "
                "not replaced with zero.",
            ]
        )

    if missing:
        lines.extend(["", "Most frequent missing evidence:"])
        for reason, count in missing.most_common(8):
            lines.append(f"- `{_safe(reason)}`: {count} runs")

    lines.extend(
        [
            "",
            "## Cost scenarios",
            "",
            "| Scenario | Annual cost | Monthly cost | Break-even min/user/day |",
            "|---|---:|---:|---:|",
        ]
    )
    for name, values in platform["platform_cost_scenarios"].items():
        lines.append(
            f"| `{_safe(name)}` | {values['annual_platform_cost']:.2f} | "
            f"{values['monthly_platform_cost']:.2f} | "
            f"{values['break_even_minutes_per_user_workday']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Platform cost structure",
            "",
            f"- Annual GPU amortization: {_safe((platform['platform_cost_scenarios'][platform['selected_platform_scenario']]).get('annual_gpu_amortization'))} RUB",
            f"- Annual licenses: {_safe((platform['platform_cost_scenarios'][platform['selected_platform_scenario']]).get('annual_license_cost'))} RUB",
            f"- Annual electricity: {_safe((platform['platform_cost_scenarios'][platform['selected_platform_scenario']]).get('annual_electricity_cost'))} RUB",
            f"- Annual support: {_safe((platform['platform_cost_scenarios'][platform['selected_platform_scenario']]).get('annual_support_cost'))} RUB",
            f"- Annual development: {_safe((platform['platform_cost_scenarios'][platform['selected_platform_scenario']]).get('annual_development_cost'))} RUB",
            f"- Annual shared tools: {_safe((platform['platform_cost_scenarios'][platform['selected_platform_scenario']]).get('annual_shared_tools_cost'))} RUB",
        ]
    )

    evidence_rows = [
        item
        for item in clusters
        if item.get("run_count", 0) >= 2
        or item.get("evaluated_run_count", 0) > 0
        or _has_potential(item)
    ]
    evidence_rows.sort(
        key=lambda item: (
            not _has_potential(item),
            -int(item.get("evaluated_run_count", 0)),
            -int(item.get("run_count", 0)),
            _target_name(item),
        )
    )
    omitted = len(clusters) - len(evidence_rows)
    lines.extend(
        [
            "",
            "## Use-case and cluster evidence",
            "",
            "| Target | Runs | Evaluated | Coverage | Potential ROI BASE | "
            "ROI interval | q break-even BASE | Status |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for item in evidence_rows:
        potential = (item.get("potential") or {}).get("base") or {}
        qbe = item.get("break_even_quality") or {}
        interval = f"{_safe(item.get('roi_lower'))} … {_safe(item.get('roi_upper'))}"
        lines.append(
            f"| {_safe(_target_name(item))} | {item['run_count']} | "
            f"{item['evaluated_run_count']} | {item['evaluation_coverage']:.2%} | "
            f"{_safe(potential.get('roi'))} | {interval} | "
            f"{_safe(qbe.get('base'))} | `{_safe(item['status'])}` |"
        )
    if omitted:
        lines.extend(
            [
                "",
                f"_Omitted {omitted} singleton targets with neither an economic "
                "calculation nor a quality evaluation. They remain available in "
                "`cluster_economics.json` and `.csv`._",
            ]
        )

    status_counts = Counter(item["status"] for item in clusters)
    lines.extend(["", "## Evidence status counts", ""])
    for status, count in sorted(status_counts.items()):
        lines.append(f"- `{_safe(status)}`: {count}")

    lines.extend(["", "## Required next data actions", ""])
    if prompt_count < total_runs:
        lines.append(
            f"- Record `prompt_minutes` for {total_runs - prompt_count} runs "
            "(never infer missing effort as zero)."
        )
    if passport_count < total_runs:
        lines.append(
            f"- Validate manual-time baselines for {total_runs - passport_count} runs "
            "or their stable use-case/cluster passports."
        )
    if quality_count < total_runs:
        lines.append(
            f"- Evaluate output quality for {total_runs - quality_count} runs; "
            "potential ROI alone is not a proven result."
        )
    if prompt_count == passport_count == quality_count == total_runs:
        lines.append("- No completeness gaps detected; review evidence levels and intervals.")

    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- Potential ROI uses q=1 and is not observed quality.",
            "- Technical run completion is not business-result correctness.",
            "- Tokens are only a GPU allocation proxy when stronger telemetry is absent.",
            "- Negative saved time and negative value are retained.",
            "- Aggregated ROI is calculated from aggregate value and cost, never from mean run ROI.",
            "- Idle licensed users remain in unallocated cost reconciliation.",
            "- A positive proven claim requires E2+, sufficient coverage and a positive lower ROI bound.",
            "",
        ]
    )
    return "\n".join(lines)
