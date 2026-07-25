"""Fixed and marginal cost allocation with reconciliation."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_FLOOR
from typing import Any

from prompt_radar.economics_analysis.formulas import dec, money, platform_scenarios
from prompt_radar.economics_analysis.models import FinancialConfig

CENT = Decimal("0.01")


def _allocate_cents(
    total: Decimal, weights: dict[str, Decimal]
) -> dict[str, Decimal]:
    """Allocate a monetary total exactly, using largest remainders."""
    target = total.quantize(CENT)
    if not weights:
        return {}
    if any(weight < 0 for weight in weights.values()):
        raise ValueError("allocation weights cannot be negative")
    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        raise ValueError("allocation weights must have a positive sum")
    raw = {
        key: target * weight / weight_sum for key, weight in weights.items()
    }
    allocated = {
        key: (value / CENT).to_integral_value(rounding=ROUND_FLOOR) * CENT
        for key, value in raw.items()
    }
    remaining = int((target - sum(allocated.values())) / CENT)
    order = sorted(
        weights,
        key=lambda key: (raw[key] - allocated[key], key),
        reverse=True,
    )
    for key in order[:remaining]:
        allocated[key] += CENT
    return allocated


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    run_metadata = row.get("run_metadata") or {}
    nested = run_metadata.get("metadata") or {}
    merged = dict(nested) if isinstance(nested, dict) else {}
    # The analysis layer always knows the locally tokenized prompt size even
    # when production GPU/token telemetry was not included in run metadata.
    # It is weaker than provider usage, but a materially better allocation
    # proxy than assigning the same GPU cost to a 10-token and a 100k-token
    # request.
    raw_prompt_tokens = row.get("raw_prompt_token_count")
    if (
        not any(
            isinstance(merged.get(key), (int, float))
            for key in ("total_tokens", "input_tokens", "prompt_tokens")
        )
        and isinstance(raw_prompt_tokens, (int, float))
        and not isinstance(raw_prompt_tokens, bool)
        and raw_prompt_tokens >= 0
    ):
        merged["input_tokens"] = raw_prompt_tokens
        merged["token_proxy_source"] = "analysis.raw_prompt_token_count"
    cost_events = list(merged.get("cost_events") or [])
    for event in run_metadata.get("event_usage") or []:
        if not isinstance(event, dict):
            continue
        usage = event.get("usage") or {}
        if not isinstance(usage, dict):
            continue
        for key in (
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "gpu_seconds",
            "gpu_time_seconds",
            "compute_seconds",
            "model_calls",
            "retry_count",
            "retry_cost_rub",
            "tool_error_count",
            "tool_error_cost_rub",
        ):
            value = usage.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                merged[key] = float(merged.get(key, 0)) + float(value)
        amount = usage.get("amount_rub", usage.get("cost_rub"))
        if isinstance(amount, (int, float)) and not isinstance(amount, bool):
            cost_events.append(
                {
                    "event_id": event.get("event_id"),
                    "component": usage.get("component", "other"),
                    "amount_rub": amount,
                }
            )
    if cost_events:
        merged["cost_events"] = cost_events
    return merged


def _number(source: dict[str, Any], *keys: str) -> Decimal:
    for key in keys:
        value = source.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return dec(value)
    return Decimal(0)


def _allocation_weights(
    rows: list[dict[str, Any]],
) -> tuple[str, dict[str, Decimal]]:
    candidates = [
        (
            "actual_gpu_time",
            lambda meta: _number(meta, "gpu_seconds", "gpu_time_seconds"),
        ),
        (
            "token_proxy",
            lambda meta: _number(meta, "total_tokens")
            or (
                _number(meta, "input_tokens", "prompt_tokens")
                + _number(meta, "output_tokens", "completion_tokens")
            ),
        ),
        (
            "model_calls_or_compute_duration",
            lambda meta: _number(meta, "compute_seconds", "model_calls"),
        ),
    ]
    for method, getter in candidates:
        weights = {
            str(row["run_id"]): getter(_metadata(row)) for row in rows
        }
        if sum(weights.values()) > 0:
            return method, weights
    return "run_count_fallback", {
        str(row["run_id"]): Decimal(1) for row in rows
    }


def _marginal_costs(
    rows: list[dict[str, Any]], config: FinancialConfig
) -> tuple[dict[str, Decimal], list[dict[str, Any]]]:
    results: dict[str, Decimal] = {}
    seen_events: set[str] = set()
    warnings: list[dict[str, Any]] = []
    for row in rows:
        run_id = str(row["run_id"])
        meta = _metadata(row)
        total = Decimal(0)
        events = meta.get("cost_events")
        if isinstance(events, list):
            for event in events:
                if not isinstance(event, dict):
                    continue
                event_id = str(event.get("event_id", ""))
                if event_id and event_id in seen_events:
                    warnings.append(
                        {
                            "run_id": run_id,
                            "code": "duplicate_cost_event",
                            "message": f"Duplicate cost event ignored: {event_id}",
                        }
                    )
                    continue
                if event_id:
                    seen_events.add(event_id)
                component = str(event.get("component", "other"))
                amount = dec(event.get("amount_rub", 0))
                enabled = (
                    (component == "external_api" and config.include_cost_components.external_api)
                    or (component == "tools" and config.include_cost_components.tools)
                    or component in {"variable_gpu", "other"}
                )
                if enabled:
                    total += amount
        else:
            if config.include_cost_components.external_api:
                total += _number(meta, "external_api_cost_rub")
            if config.include_cost_components.tools:
                total += _number(meta, "tool_cost_rub")
            total += _number(
                meta, "variable_gpu_cost_rub", "other_variable_cost_rub"
            )
        results[run_id] = total
    return results, warnings


def allocate_costs(
    rows: list[dict[str, Any]], config: FinancialConfig
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    if not rows:
        raise ValueError("cannot allocate costs without runs")
    scenarios = platform_scenarios(config)
    method, weights = _allocation_weights(rows)
    total_weight = sum(weights.values())
    period = dec(config.analysis_period_months)
    users: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        users[str(row["user_id"])].append(str(row["run_id"]))
    if len(users) > config.licensed_agent_users:
        raise ValueError("active users exceed licensed_agent_users")

    license_per_active_user = dec(config.license_cost_per_user_month) * period
    total_license = (
        dec(config.license_cost_per_user_month)
        * dec(config.licensed_agent_users)
        * period
    ).quantize(CENT)
    shared_fixed_period = (
        (
            dec(config.electricity_cost_per_month)
            if config.include_cost_components.electricity
            else Decimal(0)
        )
        + (
            dec(config.support_cost_per_month)
            if config.include_cost_components.support
            else Decimal(0)
        )
        + (
            dec(config.development_cost_per_month)
            if config.include_cost_components.development
            else Decimal(0)
        )
        + dec(config.shared_tools_cost_per_month)
    ) * period
    shared_fixed_period = shared_fixed_period.quantize(CENT)
    license_by_run: dict[str, Decimal] = {}
    for run_ids in users.values():
        per_user = _allocate_cents(
            license_per_active_user,
            {run_id: Decimal(1) for run_id in run_ids},
        )
        license_by_run.update(per_user)

    marginal, warnings = _marginal_costs(rows, config)
    gpu_period_by_scenario = {
        name: (
            dec(values["annual_gpu_amortization"]) * period / Decimal(12)
        ).quantize(CENT)
        if config.include_cost_components.gpu_amortization
        else Decimal(0)
        for name, values in scenarios.items()
    }
    gpu_by_scenario = {
        name: _allocate_cents(amount, weights)
        for name, amount in gpu_period_by_scenario.items()
    }
    shared_fixed_by_run = _allocate_cents(shared_fixed_period, weights)
    allocations: dict[str, dict[str, Any]] = {}
    for row in rows:
        run_id = str(row["run_id"])
        share = weights[run_id] / total_weight
        gpu = {name: values[run_id] for name, values in gpu_by_scenario.items()}
        selected_gpu = gpu[config.default_gpu_allocation_scenario]
        shared_fixed_cost = shared_fixed_by_run[run_id]
        license_cost = (
            license_by_run[run_id]
            if config.include_cost_components.licenses
            else Decimal(0)
        )
        fully_loaded = (
            marginal[run_id] + selected_gpu + license_cost + shared_fixed_cost
        )
        scenario_costs = {
            name: marginal[run_id] + amount + license_cost + shared_fixed_cost
            for name, amount in gpu.items()
        }
        allocations[run_id] = {
            "marginal_cost": money(marginal[run_id]),
            "allocated_gpu_cost": money(selected_gpu),
            "allocated_license_cost": money(license_cost),
            "allocated_shared_fixed_cost": money(shared_fixed_cost),
            "fully_loaded_cost": money(fully_loaded),
            "scenario_fully_loaded_costs": {
                name: money(value) for name, value in scenario_costs.items()
            },
            "minimum_fully_loaded_cost": money(min(scenario_costs.values())),
            "maximum_fully_loaded_cost": money(max(scenario_costs.values())),
            "gpu_allocation_method": method,
            "gpu_allocation_weight": float(weights[run_id]),
            "gpu_allocation_share": float(share),
        }

    allocated_gpu_selected = sum(
        dec(item["allocated_gpu_cost"]) for item in allocations.values()
    )
    expected_gpu = gpu_period_by_scenario[config.default_gpu_allocation_scenario]
    allocated_license_output = sum(
        dec(item["allocated_license_cost"]) for item in allocations.values()
    )
    allocated_shared_fixed_output = sum(
        dec(item["allocated_shared_fixed_cost"]) for item in allocations.values()
    )
    # Per-user cent rounding can differ from rounding the aggregate active-user
    # amount. Reconcile the ledger against the cents actually allocated.
    idle_license = total_license - allocated_license_output
    reconciliation = {
        "analysis_period_months": config.analysis_period_months,
        "gpu_allocation_method": method,
        "token_allocation_is_proxy": method == "token_proxy",
        "selected_platform_scenario": config.default_gpu_allocation_scenario,
        "gpu": {
            "expected": money(expected_gpu),
            "allocated": money(allocated_gpu_selected),
            "unallocated": money(expected_gpu - allocated_gpu_selected),
            "reconciled": expected_gpu == allocated_gpu_selected,
        },
        "licenses": {
            "total": money(total_license),
            "allocated": money(allocated_license_output),
            "unallocated_idle_license_cost": money(
                idle_license
            ),
            "active_users": len(users),
            "idle_licensed_users": config.licensed_agent_users - len(users),
            "reconciled": (
                total_license == allocated_license_output + idle_license
            ),
        },
        "shared_fixed": {
            "total": money(shared_fixed_period),
            "allocated": money(allocated_shared_fixed_output),
            "unallocated": money(shared_fixed_period - allocated_shared_fixed_output),
            "reconciled": shared_fixed_period == allocated_shared_fixed_output,
            "components": {
                "electricity": money(
                    (
                        dec(config.electricity_cost_per_month)
                        if config.include_cost_components.electricity
                        else Decimal(0)
                    )
                    * period
                ),
                "support": money(
                    (
                        dec(config.support_cost_per_month)
                        if config.include_cost_components.support
                        else Decimal(0)
                    )
                    * period
                ),
                "development": money(
                    (
                        dec(config.development_cost_per_month)
                        if config.include_cost_components.development
                        else Decimal(0)
                    )
                    * period
                ),
                "shared_tools": money(
                    dec(config.shared_tools_cost_per_month) * period
                ),
            },
        },
        "marginal": {
            "allocated": money(sum(marginal.values())),
            "duplicate_cost_events_ignored": sum(
                item["code"] == "duplicate_cost_event" for item in warnings
            ),
        },
    }
    return allocations, reconciliation, warnings
