"""Pure Decimal financial and time formulas."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

MONEY_QUANTUM = Decimal("0.01")
METRIC_QUANTUM = Decimal("0.000001")


def dec(value: Any) -> Decimal:
    return Decimal(str(value))


def money(value: Decimal) -> float:
    return float(value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP))


def metric(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value.quantize(METRIC_QUANTUM, rounding=ROUND_HALF_UP))


def safe_ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    return None if denominator == 0 else numerator / denominator


def platform_scenarios(config: Any) -> dict[str, dict[str, float]]:
    gpu_annual = dec(config.gpu_purchase_cost) / dec(config.gpu_lifetime_years)
    licenses_annual = (
        dec(config.license_cost_per_user_month)
        * dec(config.licensed_agent_users)
        * Decimal(12)
    )
    electricity_annual = (
        dec(config.electricity_cost_per_month) * Decimal(12)
        if config.include_cost_components.electricity
        else Decimal(0)
    )
    support_annual = (
        dec(config.support_cost_per_month) * Decimal(12)
        if config.include_cost_components.support
        else Decimal(0)
    )
    development_annual = (
        dec(config.development_cost_per_month) * Decimal(12)
        if config.include_cost_components.development
        else Decimal(0)
    )
    shared_tools_annual = dec(config.shared_tools_cost_per_month) * Decimal(12)
    fixed_overhead_annual = (
        electricity_annual
        + support_annual
        + development_annual
        + shared_tools_annual
    )
    multiplier = dec(config.agent_token_multiplier)
    shares = {
        "conservative_full_gpu": Decimal(1),
        "platform_token_ratio": multiplier / (multiplier + Decimal(1)),
        "weighted_users": (
            dec(config.licensed_agent_users) * multiplier
        )
        / (
            dec(config.licensed_agent_users) * multiplier
            + dec(config.web_users)
        ),
    }
    result: dict[str, dict[str, float]] = {}
    for name, share in shares.items():
        annual_gpu = gpu_annual * share
        annual = licenses_annual + annual_gpu + fixed_overhead_annual
        monthly = annual / Decimal(12)
        hours_year = annual / dec(config.employee_cost_per_hour)
        hours_user_month = (
            hours_year / dec(config.licensed_agent_users) / Decimal(12)
        )
        minutes_day = (
            hours_user_month
            * Decimal(60)
            / dec(config.working_days_per_month)
        )
        result[name] = {
            "agent_gpu_share": metric(share),
            "annual_gpu_amortization": money(annual_gpu),
            "annual_license_cost": money(licenses_annual),
            "annual_electricity_cost": money(electricity_annual),
            "annual_support_cost": money(support_annual),
            "annual_development_cost": money(development_annual),
            "annual_shared_tools_cost": money(shared_tools_annual),
            "annual_fixed_overhead_cost": money(fixed_overhead_annual),
            "annual_platform_cost": money(annual),
            "monthly_platform_cost": money(monthly),
            "cost_per_user_month": money(
                monthly / dec(config.licensed_agent_users)
            ),
            "break_even_hours_per_year": metric(hours_year),
            "break_even_hours_per_user_month": metric(hours_user_month),
            "break_even_minutes_per_user_workday": metric(minutes_day),
        }
    return result


def actual_saved_minutes(
    manual: Decimal,
    prompt: Decimal,
    active_wait: Decimal,
    review: Decimal,
    rework: Decimal,
) -> Decimal:
    return manual - prompt - active_wait - review - rework


def potential_saved_minutes(
    quality: Decimal,
    manual: Decimal,
    prompt: Decimal,
    active_wait: Decimal,
    followup: Decimal,
) -> Decimal:
    return quality * manual - prompt - active_wait - followup


def economic_values(
    saved_minutes: Decimal, labor_per_minute: Decimal, run_cost: Decimal
) -> dict[str, float | None]:
    labor_value = saved_minutes * labor_per_minute
    net_value = labor_value - run_cost
    roi = safe_ratio(net_value, run_cost)
    return {
        "saved_minutes": metric(saved_minutes),
        "labor_value": money(labor_value),
        "net_value": money(net_value),
        "roi": metric(roi),
        "roi_percent": metric(roi * Decimal(100)) if roi is not None else None,
        "roi_explanation": (
            "ROI undefined because run_cost=0" if roi is None else None
        ),
    }


def break_even_quality(
    manual: Decimal,
    prompt: Decimal,
    ai_wall: Decimal,
    active_wait_ratio: Decimal,
    followup: Decimal,
    run_cost: Decimal,
    labor_per_minute: Decimal,
) -> Decimal | None:
    if manual == 0:
        return None
    return (
        prompt
        + active_wait_ratio * ai_wall
        + followup
        + run_cost / labor_per_minute
    ) / manual


def max_affordable_cost(
    quality: Decimal,
    manual: Decimal,
    prompt: Decimal,
    ai_wall: Decimal,
    active_wait_ratio: Decimal,
    followup: Decimal,
    labor_per_minute: Decimal,
) -> Decimal:
    return labor_per_minute * (
        quality * manual
        - prompt
        - active_wait_ratio * ai_wall
        - followup
    )


def max_affordable_ai_minutes(
    quality: Decimal,
    manual: Decimal,
    prompt: Decimal,
    followup: Decimal,
    run_cost: Decimal,
    labor_per_minute: Decimal,
    active_wait_ratio: Decimal,
) -> Decimal | None:
    if active_wait_ratio == 0:
        return None
    return (
        quality * manual
        - prompt
        - followup
        - run_cost / labor_per_minute
    ) / active_wait_ratio
