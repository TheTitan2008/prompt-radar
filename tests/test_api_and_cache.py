from __future__ import annotations

import socket
import json

import pytest

from prompt_radar.embeddings.cache import embedding_cache_key
from prompt_radar.errors import ExternalApiDisabledError
from prompt_radar.naming.base import ClusterNamingRequest
from prompt_radar.naming.disabled import DisabledClusterNamingProvider
from prompt_radar.naming.payload_builder import build_naming_context
from prompt_radar.naming.qwen_api_stub import QwenApiClusterNamingProvider


def test_disabled_api_never_uses_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("network attempted")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    request = ClusterNamingRequest(1, ["Почта"], ["ответь"], ["письмо"])
    with pytest.raises(ExternalApiDisabledError):
        DisabledClusterNamingProvider().name_cluster(request)
    with pytest.raises(ExternalApiDisabledError):
        QwenApiClusterNamingProvider().name_cluster(request)


def test_cache_key_includes_model_and_preprocessing_versions() -> None:
    base = dict(
        model_id="model",
        tokenizer_version="tok",
        encoding_mode="query",
        text="hello",
    )
    first = embedding_cache_key(
        **base, model_revision="a", preprocessing_version="1"
    )
    second = embedding_cache_key(
        **base, model_revision="b", preprocessing_version="1"
    )
    third = embedding_cache_key(
        **base, model_revision="a", preprocessing_version="2"
    )
    assert len({first, second, third}) == 3


def test_cluster_api_payload_is_compact_and_does_not_send_full_prompt() -> None:
    long_prompt = "start " + ("ctx " * 5000) + "finish"
    request = ClusterNamingRequest(
        7,
        ["Finance"],
        [long_prompt for _ in range(10)],
        ["budget", "report"],
        member_count=10,
        cluster_fingerprint="abc",
    )

    context = build_naming_context(
        request,
        max_examples=10,
        max_example_chars=400,
        max_payload_chars=5000,
    )
    encoded = json.dumps(context, ensure_ascii=False)

    assert len(encoded) <= 5000
    assert context["compact_packet_rules"]["full_prompts_sent"] is False
    assert "ctx " * 100 not in encoded
