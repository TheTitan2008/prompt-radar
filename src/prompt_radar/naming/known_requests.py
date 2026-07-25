"""Prepare auditable API request bodies for all known use-case passports."""

from __future__ import annotations

from prompt_radar.classification.catalogs import KnownUseCase
from prompt_radar.naming.base import ClusterNamingRequest
from prompt_radar.naming.payload_builder import build_chat_completion_payload


def build_known_passport_requests(
    use_cases: list[KnownUseCase],
    *,
    model: str = "<configured-qwen-or-deepseek-model>",
) -> list[dict[str, object]]:
    """Create one unsent request template per known use case."""
    requests: list[dict[str, object]] = []
    for index, use_case in enumerate(use_cases, start=1):
        context = ClusterNamingRequest(
            cluster_id=-index,
            known_categories=use_case.category_ids,
            representative_examples=[
                use_case.name,
                use_case.description,
                *use_case.examples,
                f"Системы: {', '.join(use_case.systems)}",
                f"Ожидаемый результат: {use_case.expected_outcome}",
            ],
            local_keywords=[*use_case.actions, *use_case.systems],
            member_count=0,
        )
        requests.append(
            {
                "use_case_id": use_case.id,
                "use_case_name": use_case.name,
                "request": build_chat_completion_payload(
                    context,
                    model=model,
                ),
                "api_called": False,
                "purpose": "refresh_known_use_case_draft_passport",
            }
        )
    return requests
