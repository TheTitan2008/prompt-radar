from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from prompt_radar.economics_analysis.allocation import allocate_costs
from prompt_radar.economics_analysis.engine import (
    _aggregate_break_even_quality,
    _aggregate_economic_values,
    _adjustment_factors,
    _status,
)
from prompt_radar.economics_analysis.formulas import (
    actual_saved_minutes,
    break_even_quality,
    economic_values,
    platform_scenarios,
)
from prompt_radar.economics_analysis.loaders import load_financial_config
from prompt_radar.economics_analysis.models import EconomicPassport
from prompt_radar.economics_analysis.quality import (
    bootstrap_mean_interval,
    wilson_interval,
)


@pytest.fixture
def financial_config():
    return load_financial_config(Path("data/economics/cost_config.json"))


def test_fixed_labor_and_platform_control_values(financial_config) -> None:
    assert financial_config.employee_cost_per_hour / 60 == 25
    scenarios = platform_scenarios(financial_config)
    conservative = scenarios["conservative_full_gpu"]
    assert conservative["annual_gpu_amortization"] == 20_000_000
    assert conservative["annual_license_cost"] == 18_000_000
    assert conservative["annual_platform_cost"] == 38_000_000
    assert conservative["break_even_hours_per_year"] == pytest.approx(25333.333333)
    assert conservative["break_even_minutes_per_user_workday"] == pytest.approx(42.222222)
    assert scenarios["platform_token_ratio"]["agent_gpu_share"] == pytest.approx(5 / 6)
    assert scenarios["weighted_users"]["agent_gpu_share"] == pytest.approx(750 / 2050)


def test_invalid_wait_ratio_and_range_are_rejected() -> None:
    raw = {
        "target_type": "cluster",
        "target_id": "1",
        "cluster_name": "Test cluster",
        "business_goal": "Test business goal",
        "manual_steps": [
            {
                "step": "Manual work",
                "minutes_low": 10,
                "minutes_base": 20,
                "minutes_high": 30,
            }
        ],
        "manual_minutes": {"low": 10, "base": 20, "high": 30},
        "human_followup_minutes": {"low": 1, "base": 2, "high": 3},
        "active_wait_ratio": {"low": 0, "base": 0.5, "high": 1.1},
        "manual_time_confidence": 0.5,
        "evidence_level": "E0",
    }
    with pytest.raises(ValidationError):
        EconomicPassport.model_validate(raw)


def test_negative_savings_are_retained_and_zero_cost_has_no_roi() -> None:
    saved = actual_saved_minutes(
        Decimal(10), Decimal(3), Decimal(5), Decimal(4), Decimal(6)
    )
    assert saved == Decimal(-8)
    values = economic_values(saved, Decimal(25), Decimal(0))
    assert values["saved_minutes"] == -8
    assert values["net_value"] == -200
    assert values["roi"] is None
    assert "run_cost=0" in values["roi_explanation"]


def test_break_even_over_one() -> None:
    value = break_even_quality(
        Decimal(10),
        Decimal(5),
        Decimal(10),
        Decimal("0.5"),
        Decimal(5),
        Decimal(100),
        Decimal(25),
    )
    assert value is not None and value > 1


def test_aggregate_roi_is_from_sums_not_mean_roi() -> None:
    rows = [
        {
            "potential": {
                "base": {"saved_minutes": 4, "labor_value": 100}
            },
            "provenance": {
                "cost": {
                    "fully_loaded_cost": 10,
                    "minimum_fully_loaded_cost": 10,
                    "maximum_fully_loaded_cost": 10,
                }
            },
        },
        {
            "potential": {
                "base": {"saved_minutes": 2, "labor_value": 50}
            },
            "provenance": {
                "cost": {
                    "fully_loaded_cost": 100,
                    "minimum_fully_loaded_cost": 100,
                    "maximum_fully_loaded_cost": 100,
                }
            },
        },
    ]
    aggregate = _aggregate_economic_values(rows, "base")
    assert aggregate["roi"] == pytest.approx((150 - 110) / 110, abs=1e-6)
    assert aggregate["roi"] != pytest.approx((9 + -0.5) / 2)


def test_evidence_status_guards(financial_config) -> None:
    potential = {
        "low": {"net_value": 1, "saved_minutes": 1, "roi": 0.1},
        "base": {"net_value": 10, "saved_minutes": 2, "roi": 0.5},
        "high": {"net_value": 20, "saved_minutes": 3, "roi": 1.0},
    }
    qbe = {"low": 0.7, "base": 0.5, "high": 0.3}
    status, _, _ = _status(
        missing=[],
        potential=potential,
        break_even=qbe,
        roi_lower=0.2,
        roi_upper=0.8,
        evidence="E0",
        evaluated=10,
        coverage=1,
        config=financial_config,
        manual_base=60,
    )
    assert status != "PROVEN_EFFECTIVE"
    status, _, _ = _status(
        missing=[],
        potential=potential,
        break_even=qbe,
        roi_lower=0.2,
        roi_upper=0.8,
        evidence="E2",
        evaluated=10,
        coverage=1,
        config=financial_config,
        manual_base=60,
    )
    assert status == "PROVEN_EFFECTIVE"
    status, _, _ = _status(
        missing=[],
        potential=potential,
        break_even=qbe,
        roi_lower=-1.0,
        roi_upper=-0.1,
        evidence="E2",
        evaluated=10,
        coverage=1,
        config=financial_config,
        manual_base=60,
    )
    assert status == "PROVEN_INEFFECTIVE"
    status, _, _ = _status(
        missing=[],
        potential=potential,
        break_even={"low": 1.5, "base": 1.3, "high": 1.1},
        roi_lower=None,
        roi_upper=None,
        evidence="E0",
        evaluated=0,
        coverage=0,
        config=financial_config,
        manual_base=10,
    )
    assert status == "IMPOSSIBLE_TO_BREAK_EVEN"


def test_wilson_and_reproducible_bootstrap() -> None:
    low, high = wilson_interval(5, 10)
    assert low == pytest.approx(0.23659, rel=1e-4)
    assert high == pytest.approx(0.76341, rel=1e-4)
    first = bootstrap_mean_interval([0.2, 0.6, 1.0], seed=42, iterations=1000)
    second = bootstrap_mean_interval([0.2, 0.6, 1.0], seed=42, iterations=1000)
    assert first == second


def test_reconciliation_idle_users_and_duplicate_cost_events(financial_config) -> None:
    rows = [
        {
            "run_id": "r1",
            "user_id": "u1",
            "run_metadata": {
                "metadata": {
                    "input_tokens": 100,
                    "cost_events": [
                        {
                            "event_id": "cost-1",
                            "component": "external_api",
                            "amount_rub": 5,
                        }
                    ],
                }
            },
        },
        {
            "run_id": "r2",
            "user_id": "u2",
            "run_metadata": {
                "metadata": {
                    "input_tokens": 200,
                    "cost_events": [
                        {
                            "event_id": "cost-1",
                            "component": "external_api",
                            "amount_rub": 5,
                        }
                    ],
                }
            },
        },
    ]
    allocations, reconciliation, warnings = allocate_costs(
        rows, financial_config
    )
    assert set(allocations) == {"r1", "r2"}
    assert reconciliation["gpu"]["reconciled"] is True
    assert reconciliation["licenses"]["reconciled"] is True
    assert reconciliation["licenses"]["idle_licensed_users"] == 148
    assert reconciliation["licenses"]["unallocated_idle_license_cost"] == 1480
    assert reconciliation["gpu_allocation_method"] == "token_proxy"
    assert sum(item["code"] == "duplicate_cost_event" for item in warnings) == 1


def test_analysis_prompt_tokens_are_used_before_run_count_fallback(
    financial_config,
) -> None:
    rows = [
        {
            "run_id": "small",
            "user_id": "u1",
            "raw_prompt_token_count": 10,
            "run_metadata": {"metadata": {}},
        },
        {
            "run_id": "large",
            "user_id": "u2",
            "raw_prompt_token_count": 1000,
            "run_metadata": {"metadata": {}},
        },
    ]

    allocations, reconciliation, _ = allocate_costs(rows, financial_config)

    assert reconciliation["gpu_allocation_method"] == "token_proxy"
    assert (
        allocations["large"]["allocated_gpu_cost"]
        > allocations["small"]["allocated_gpu_cost"]
    )


def test_license_reconciliation_with_fractional_analysis_period(
    financial_config,
) -> None:
    config = financial_config.model_copy(
        update={"analysis_period_months": 0.203657407407407}
    )
    rows = [
        {
            "run_id": f"r{index}",
            "user_id": f"u{index}",
            "raw_prompt_token_count": 1,
            "run_metadata": {"metadata": {}},
        }
        for index in range(81)
    ]

    _, reconciliation, _ = allocate_costs(rows, config)

    licenses = reconciliation["licenses"]
    assert licenses["reconciled"] is True
    assert licenses["total"] == pytest.approx(
        licenses["allocated"] + licenses["unallocated_idle_license_cost"],
        abs=0.01,
    )


@pytest.mark.parametrize("run_count", [100, 400, 1000])
def test_reconciliation_is_exact_for_large_datasets(
    financial_config, run_count: int
) -> None:
    rows = [
        {
            "run_id": f"r{index:04d}",
            "user_id": f"u{index % 10}",
            "run_metadata": {"metadata": {"input_tokens": 1}},
        }
        for index in range(run_count)
    ]
    allocations, reconciliation, _ = allocate_costs(rows, financial_config)
    assert reconciliation["gpu"]["reconciled"] is True
    assert sum(
        Decimal(str(item["allocated_gpu_cost"]))
        for item in allocations.values()
    ) == Decimal(str(reconciliation["gpu"]["expected"]))


def test_cluster_break_even_uses_weighted_aggregate_equation(
    financial_config,
) -> None:
    def record(manual: float, prompt: float) -> dict:
        return {
            "manual_minutes": {
                "low": manual,
                "base": manual,
                "high": manual,
            },
            "human_followup_minutes": {"low": 0, "base": 0, "high": 0},
            "prompt_minutes": prompt,
            "active_wait_minutes": {"low": 0, "base": 0, "high": 0},
            "provenance": {
                "cost": {
                    "minimum_fully_loaded_cost": 0,
                    "fully_loaded_cost": 0,
                    "maximum_fully_loaded_cost": 0,
                }
            },
        }

    result = _aggregate_break_even_quality(
        [record(10, 9), record(100, 10)],
        financial_config,
    )
    assert result["base"] == pytest.approx(19 / 110, abs=1e-6)
    assert result["base"] != pytest.approx((0.9 + 0.1) / 2)


def test_run_adjustment_factors_use_size_complexity_and_attachments() -> None:
    factors, assumptions = _adjustment_factors(
        {
            "current_goal": "сделай итоговый отчёт и проанализируй таблицу",
            "raw_prompt_token_count": 60000,
            "attachment_ids": ["a1", "a2", "a3"],
            "attachment_token_count": 60000,
            "categories": [{"id": "finance"}],
            "multiple_goals": False,
        }
    )

    assert factors["size_bucket"] == "huge"
    assert factors["attachment_bucket"] == "huge_files"
    assert factors["complexity_bucket"] == "production_deliverable"
    assert factors["size_factor"] == 2.5
    assert assumptions == []
