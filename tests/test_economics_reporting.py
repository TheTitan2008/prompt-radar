from __future__ import annotations

from prompt_radar.economics_analysis.reporting import build_economics_report


def test_report_surfaces_missing_inputs_and_compacts_empty_singletons() -> None:
    platform = {
        "total_runs": 2,
        "selected_platform_scenario": "base",
        "analysis_period_months": 1.0,
        "gpu_allocation_method": "run_count_fallback",
        "token_allocation_is_proxy": False,
        "allocated_cost": 10.0,
        "unallocated_idle_license_cost": 0.0,
        "potential": None,
        "confirmed_wasted_cost": 0.0,
        "optimization_opportunity_cost": 0.0,
        "platform_cost_scenarios": {
            "base": {
                "annual_platform_cost": 100.0,
                "monthly_platform_cost": 10.0,
                "break_even_minutes_per_user_workday": 1.0,
            }
        },
    }
    ledger = [
        {
            "prompt_minutes": None,
            "manual_minutes": None,
            "potential": None,
            "actual": None,
            "quality_score": None,
            "missing_evidence": ["prompt_minutes", "economic_passport"],
            "provenance": {"prompt_minutes": None},
        }
        for _ in range(2)
    ]
    clusters = [
        {
            "target_id": f"target-{index}",
            "name": None,
            "run_count": 1,
            "evaluated_run_count": 0,
            "evaluation_coverage": 0.0,
            "potential": None,
            "break_even_quality": None,
            "roi_lower": None,
            "roi_upper": None,
            "status": "INSUFFICIENT_EVIDENCE",
        }
        for index in range(2)
    ]

    report = build_economics_report(
        platform=platform,
        clusters=clusters,
        ledger=ledger,
        warnings=[],
    )

    assert "ROI is not calculable" in report
    assert "`prompt_minutes`: 2 runs" in report
    assert "Omitted 2 singleton targets" in report
    assert "| target-0 |" not in report


def test_report_distinguishes_assumed_prompt_effort_from_measurement() -> None:
    platform = {
        "total_runs": 1,
        "selected_platform_scenario": "base",
        "analysis_period_months": 0.2,
        "gpu_allocation_method": "token_proxy",
        "token_allocation_is_proxy": True,
        "allocated_cost": 1.0,
        "unallocated_idle_license_cost": 0.0,
        "potential": {"base": {"saved_minutes": 1, "net_value": 1, "roi": 1}},
        "confirmed_wasted_cost": 0.0,
        "optimization_opportunity_cost": 0.0,
        "platform_cost_scenarios": {
            "base": {
                "annual_platform_cost": 1.0,
                "monthly_platform_cost": 1.0,
                "break_even_minutes_per_user_workday": 1.0,
            }
        },
    }
    ledger = [
        {
            "prompt_minutes": 3,
            "manual_minutes": {"base": 10},
            "potential": {"base": {"roi": 1}},
            "actual": None,
            "quality_score": None,
            "missing_evidence": [],
            "provenance": {
                "prompt_minutes": "cost_config.default_prompt_minutes"
            },
        }
    ]

    report = build_economics_report(
        platform=platform,
        clusters=[],
        ledger=ledger,
        warnings=[],
    )

    assert "Prompt effort measured | 0/1" in report
    assert "Prompt effort assumed by cost config | 1/1" in report
    assert "Prompt effort is assumed for 1 runs" in report
