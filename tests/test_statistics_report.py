from __future__ import annotations

from prompt_radar.economics_analysis.statistics_report import (
    build_statistics_html,
    build_statistics_summary,
)


def test_person_statistics_reconcile_value_time_and_cost() -> None:
    rows = [
        {
            "run_id": "r1",
            "conversation_id": "c1",
            "user_id": "u1",
            "user_display_name": "Татьяна Белякова",
            "user_department": "МИФИ",
            "processing_mode": "short_direct",
            "discovery_status": "known",
            "current_goal": "Подготовить ответ студенту",
            "primary_category": {"name": "Поиск знаний"},
            "known_use_case_matches": [],
            "cluster_name": "Ответы студентам МИФИ",
        },
        {
            "run_id": "r2",
            "conversation_id": "c2",
            "user_id": "u1",
            "user_display_name": "Татьяна Белякова",
            "user_department": "МИФИ",
            "processing_mode": "long_context",
            "discovery_status": "emerging",
            "current_goal": "Проверить правила",
            "primary_category": {"name": "Поиск знаний"},
            "known_use_case_matches": [],
            "cluster_name": "Ответы студентам МИФИ",
        },
    ]
    ledger = [
        {
            "run_id": "r1",
            "user_id": "u1",
            "target_name": "Ответы студентам МИФИ",
            "run_status": "completed",
            "ai_wall_minutes": 5,
            "fully_loaded_cost": 10,
            "potential": {
                "base": {"saved_minutes": 4, "labor_value": 100}
            },
            "actual": {
                "saved_minutes": 3,
                "labor_value": 75,
            },
            "provenance": {"prompt_minutes": "quality_evaluation"},
        },
        {
            "run_id": "r2",
            "user_id": "u1",
            "target_name": "Ответы студентам МИФИ",
            "run_status": "failed",
            "ai_wall_minutes": 10,
            "fully_loaded_cost": 20,
            "potential": None,
            "actual": None,
            "provenance": {
                "prompt_minutes": "cost_config.default_prompt_minutes"
            },
        },
    ]
    platform = {
        "analysis_period_months": 1,
        "gpu_allocation_method": "token_proxy",
        "fully_loaded_platform_period_cost": 30,
        "potential": {
            "base": {
                "saved_minutes": 4,
                "labor_value": 100,
                "net_value": 70,
                "roi": 70 / 30,
            }
        },
    }

    summary = build_statistics_summary(
        rows=rows,
        ledger=ledger,
        platform=platform,
    )

    assert summary["totals"]["runs"] == 2
    assert summary["totals"]["users"] == 1
    person = summary["users"][0]
    assert person["run_count"] == 2
    assert person["conversation_count"] == 2
    assert person["ai_processing_minutes"] == 15
    assert person["potential_saved_minutes"] == 4
    assert person["potential_gross_value"] == 100
    assert person["allocated_platform_cost"] == 30
    assert person["potential_net_value"] == 70
    assert person["actual_net_value"] == 65
    assert sum(item["count"] for item in summary["request_types"]) == 2


def test_html_is_self_contained_and_escapes_user_content() -> None:
    summary = {
        "basis": {
            "prompt_effort_assumed_runs": 0,
            "gpu_allocation_method": "token_proxy",
            "analysis_period_months": 1,
        },
        "totals": {
            "runs": 1,
            "users": 1,
            "conversations": 1,
            "ai_processing_minutes": 60,
            "potential_saved_minutes": 30,
            "potential_gross_value": 750,
            "fully_loaded_platform_period_cost": 100,
            "potential_net_value": 650,
            "potential_roi": 6.5,
            "actual_evaluated_runs": 0,
        },
        "request_types": [{"name": "Задача", "count": 1}],
        "statuses": [{"name": "completed", "count": 1}],
        "processing_modes": [{"name": "short_direct", "count": 1}],
        "categories": [{"name": "Прочее", "count": 1}],
        "users": [
            {
                "user_id": "u1",
                "display_name": "<script>alert(1)</script>",
                "department": None,
                "role": None,
                "run_count": 1,
                "conversation_count": 1,
                "ai_processing_minutes": 60,
                "average_ai_processing_minutes": 60,
                "potential_covered_runs": 1,
                "potential_coverage": 1.0,
                "potential_saved_minutes": 30,
                "potential_gross_value": 750,
                "allocated_platform_cost": 100,
                "potential_net_value": 650,
                "actual_evaluated_runs": 0,
                "actual_saved_minutes": 0,
                "actual_gross_value": 0,
                "actual_cost": 0,
                "actual_net_value": None,
                "status_counts": {"completed": 1},
                "request_types": [{"name": "Задача", "count": 1}],
                "tasks": [
                    {
                        "run_id": "r1",
                        "conversation_id": "c1",
                        "request_type": "Задача",
                        "status": "completed",
                        "processing_mode": "short_direct",
                        "ai_processing_minutes": 60,
                        "potential_saved_minutes": 30,
                        "actual_saved_minutes": None,
                        "goal": "<img src=x onerror=alert(1)>",
                    }
                ],
            }
        ],
    }

    report = build_statistics_html(summary)

    assert "<style>" in report
    assert "<script>alert(1)</script>" not in report
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in report
    assert "<img src=x onerror=alert(1)>" not in report
