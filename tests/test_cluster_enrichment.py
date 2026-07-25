from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from prompt_radar.config import ClusterEnrichmentConfig, EconomicsConfig
from prompt_radar.economics import (
    EMPLOYEE_COST_PER_HOUR_RUB,
    build_local_economic_context,
    money_value_of_minutes,
)
from prompt_radar.errors import ExternalApiError
from prompt_radar.naming.base import ClusterNamingRequest, ClusterNamingResult
from prompt_radar.naming.openai_compatible import (
    ApiSettings,
    OpenAICompatibleClusterEnrichmentProvider,
)
from prompt_radar.naming.payload_builder import (
    SYSTEM_PROMPT,
    build_chat_completion_payload,
    build_naming_payload,
)


def _result_payload() -> dict[str, Any]:
    return {
        "cluster_name": "Анализ причин падения продаж",
        "manual_steps": [
            {"step": "Изучить исходные данные", "minutes_base": 15},
            {"step": "Рассчитать показатели", "minutes_base": 20},
            {"step": "Определить причины", "minutes_base": 20},
            {"step": "Подготовить выводы", "minutes_base": 10},
        ],
        "manual_minutes": {"low": 35, "base": 65, "high": 120},
        "human_followup_minutes": {"low": 3, "base": 10, "high": 25},
        "active_wait_ratio": {"low": 0.0, "base": 0.25, "high": 1.0},
        "manual_time_confidence": 0.65,
        "assumptions": ["данные доступны в одном файле"],
    }


def _request(member_count: int = 5) -> ClusterNamingRequest:
    return ClusterNamingRequest(
        cluster_id=7,
        known_categories=[],
        representative_examples=[
            "Определи причины снижения продаж",
            "Сравни показатели продаж по регионам",
        ],
        local_keywords=["продажи", "причины"],
        member_count=member_count,
    )


def test_contract_and_fixed_rate() -> None:
    result = ClusterNamingResult.model_validate(_result_payload())
    context = build_local_economic_context(result)
    assert EMPLOYEE_COST_PER_HOUR_RUB == 1500
    assert money_value_of_minutes(53) == 1325
    assert context["manual_work_value_rub"]["base"] == 1625
    assert EconomicsConfig(employee_cost_per_hour=1500).employee_cost_per_hour == 1500
    with pytest.raises(ValidationError):
        EconomicsConfig(employee_cost_per_hour=3000)


def test_contract_rejects_extra_role_and_inconsistent_steps() -> None:
    with_role = {**_result_payload(), "worker_role": "lawyer"}
    with pytest.raises(ValidationError):
        ClusterNamingResult.model_validate(with_role)
    inconsistent = _result_payload()
    inconsistent["manual_minutes"] = {"low": 35, "base": 66, "high": 120}
    with pytest.raises(ValidationError):
        ClusterNamingResult.model_validate(inconsistent)


def test_payload_is_bounded_and_has_no_labor_rate() -> None:
    payload = build_chat_completion_payload(
        _request(),
        model="deepseek-chat",
        max_examples=1,
        max_example_chars=12,
    )
    encoded = json.dumps(payload, ensure_ascii=False)
    assert payload["response_format"] == {"type": "json_object"}
    assert "employee_cost_per_hour" not in encoded
    assert "1500" not in encoded
    assert "worker_role" not in encoded
    assert "manual_steps" in encoded
    assert "manual_time_confidence" in encoded
    assert "примеры" in SYSTEM_PROMPT.casefold()


def test_external_payload_redacts_common_direct_identifiers() -> None:
    request = _request()
    request.representative_examples = [
        "Write to ivan.petrov@example.com or call +7 (999) 123-45-67; "
        "api_key=very-secret"
    ]
    encoded = json.dumps(
        build_chat_completion_payload(request, model="qwen"),
        ensure_ascii=False,
    )
    assert "ivan.petrov@example.com" not in encoded
    assert "999" not in encoded
    assert "very-secret" not in encoded
    assert "[REDACTED_EMAIL]" in encoded
    assert "[REDACTED_PHONE]" in encoded
    assert "[REDACTED_SECRET]" in encoded


def test_small_cluster_is_never_eligible_or_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview = build_naming_payload(
        _request(member_count=4), eligible=False, minimum_members=5
    )
    assert preview["api_status"] == "skipped_below_minimum"

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("network attempted")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    provider = OpenAICompatibleClusterEnrichmentProvider(
        settings=ApiSettings("https://example.test/v1", "secret", "qwen"),
        config=ClusterEnrichmentConfig(min_cluster_members=5),
    )
    with pytest.raises(ExternalApiError, match="below min_cluster_members"):
        provider.name_cluster(_request(member_count=4))


def test_openai_compatible_request_and_strict_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int = -1) -> bytes:
            envelope = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                _result_payload(), ensure_ascii=False
                            )
                        }
                    }
                ]
            }
            data = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
            return data if limit < 0 else data[:limit]

    def fake_urlopen(
        request: urllib.request.Request, *, timeout: float
    ) -> FakeResponse:
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    provider = OpenAICompatibleClusterEnrichmentProvider(
        settings=ApiSettings(
            "https://api.example.test/v1", "test-key", "deepseek-chat"
        ),
        config=ClusterEnrichmentConfig(min_cluster_members=5),
    )
    result = provider.name_cluster(_request())
    assert result.cluster_name == "Анализ причин падения продаж"
    assert captured["url"] == "https://api.example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["body"]["model"] == "deepseek-chat"


def test_identical_external_request_uses_content_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int = -1) -> bytes:
            envelope = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                _result_payload(), ensure_ascii=False
                            )
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 123,
                    "completion_tokens": 45,
                    "total_tokens": 168,
                },
            }
            return json.dumps(envelope, ensure_ascii=False).encode("utf-8")

    def fake_urlopen(
        request: urllib.request.Request, *, timeout: float
    ) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    provider = OpenAICompatibleClusterEnrichmentProvider(
        settings=ApiSettings("https://api.example.test/v1", "key", "qwen"),
        config=ClusterEnrichmentConfig(),
        cache_dir=tmp_path,
    )

    first = provider.name_cluster(_request())
    assert provider.last_call_metadata["http_called"] is True
    assert provider.last_call_metadata["usage"]["total_tokens"] == 168
    second = provider.name_cluster(_request())

    assert first == second
    assert calls == 1
    assert provider.last_call_metadata["cache_hit"] is True
    assert provider.last_call_metadata["http_called"] is False
