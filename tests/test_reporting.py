from __future__ import annotations

from prompt_radar.reporting.markdown_report import build_markdown_report


def test_executive_report_uses_final_cluster_label_and_actions() -> None:
    analyses = [
        {
            "run_id": "r1",
            "processing_mode": "short_direct",
            "discovery_status": "known",
            "classification_status": "matched_known",
            "classification_similarity": 0.9,
            "classification_threshold": 0.56,
            "known_use_case_matches": [
                {
                    "id": "jira",
                    "name": "Jira tasks",
                    "accepted": True,
                }
            ],
            "primary_category": {"id": "tasks", "name": "Tasks"},
            "run_metadata": {
                "status": "completed",
                "started_at": "2026-07-01T10:00:00Z",
            },
            "raw_prompt_token_count": 20,
            "current_goal": "Show Jira tasks",
        },
        {
            "run_id": "r2",
            "processing_mode": "long_extractive",
            "discovery_status": "unresolved",
            "classification_status": "residual",
            "classification_similarity": 0.3,
            "classification_threshold": 0.56,
            "known_use_case_matches": [],
            "primary_category": None,
            "run_metadata": {
                "status": "failed",
                "started_at": "2026-07-02T10:00:00Z",
            },
            "raw_prompt_token_count": 60_000,
            "current_goal": "Unknown task",
        },
    ]
    clusters = [
        {
            "cluster_id": 0,
            "cluster_fingerprint": "a" * 64,
            "member_count": 5,
            "provisional_label": "Old provisional label",
            "cluster_name": "Reviewed cluster",
            "label_source": "local_precomputed",
            "api_enrichment_status": "precomputed_success",
            "keywords": ["reviewed"],
            "representative_examples": [],
        }
    ]
    report = build_markdown_report(
        dataset_id="dataset",
        analyses=analyses,
        clusters=clusters,
        warnings=[],
        model_id="model",
        model_revision="revision",
        external_api_call_count=0,
    )
    assert "Reviewed cluster" in report
    assert "Old provisional label" not in report
    assert "Most frequent known use cases" in report
    assert "Time dynamics" in report
    assert "Problem signals" in report
    assert "Recommended actions" in report
    assert "runs_analysis.jsonl/csv/parquet" in report
