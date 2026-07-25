"""Deterministic labor-value helpers using the single approved employee rate."""

from __future__ import annotations

from prompt_radar.naming.base import ClusterNamingResult, MinuteRange

EMPLOYEE_COST_PER_HOUR_RUB = 1500
EMPLOYEE_COST_PER_MINUTE_RUB = EMPLOYEE_COST_PER_HOUR_RUB / 60


def money_value_of_minutes(minutes: float) -> float:
    """Convert saved employee minutes to RUB at the fixed 1500 RUB/hour rate."""
    if minutes < 0:
        raise ValueError("saved minutes cannot be negative")
    return round(minutes * EMPLOYEE_COST_PER_MINUTE_RUB, 2)


def _range_value(duration: MinuteRange) -> dict[str, float]:
    return {
        "low": money_value_of_minutes(duration.low),
        "base": money_value_of_minutes(duration.base),
        "high": money_value_of_minutes(duration.high),
    }


def build_local_economic_context(
    result: ClusterNamingResult,
) -> dict[str, object]:
    """Add local monetary context without asking the external model for wages."""
    return {
        "employee_cost_per_hour": EMPLOYEE_COST_PER_HOUR_RUB,
        "employee_cost_per_minute": EMPLOYEE_COST_PER_MINUTE_RUB,
        "manual_work_value_rub": _range_value(result.manual_minutes),
        "human_followup_cost_rub": _range_value(
            result.human_followup_minutes
        ),
        "saved_time_value_formula": (
            "saved_minutes / 60 * employee_cost_per_hour"
        ),
        "actual_saved_minutes_available": False,
        "note": (
            "Фактическая экономия и ROI не заявляются без телеметрии времени "
            "ИИ и проверки качества результата."
        ),
    }
