"""Explicit OpenAI-compatible client for Qwen or DeepSeek cluster enrichment."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from prompt_radar.config import ClusterEnrichmentConfig
from prompt_radar.errors import ExternalApiError
from prompt_radar.naming.base import ClusterNamingRequest, ClusterNamingResult
from prompt_radar.naming.payload_builder import build_chat_completion_payload


@dataclass(frozen=True)
class ApiSettings:
    """Secrets and endpoint settings loaded only from environment variables."""

    api_base: str
    api_key: str
    model: str
    model_revision: str = "provider-managed"

    @classmethod
    def from_environment(cls) -> "ApiSettings":
        api_base = (
            os.getenv("CLUSTER_ENRICHMENT_API_BASE")
            or os.getenv("QWEN_API_BASE")
            or os.getenv("DEEPSEEK_API_BASE")
            or ""
        ).strip()
        api_key = (
            os.getenv("CLUSTER_ENRICHMENT_API_KEY")
            or os.getenv("QWEN_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or ""
        ).strip()
        model = (
            os.getenv("CLUSTER_ENRICHMENT_MODEL")
            or os.getenv("QWEN_CHAT_MODEL")
            or os.getenv("DEEPSEEK_CHAT_MODEL")
            or ""
        ).strip()
        model_revision = (
            os.getenv("CLUSTER_ENRICHMENT_MODEL_REVISION")
            or "provider-managed"
        ).strip()
        missing = [
            name
            for name, value in (
                ("CLUSTER_ENRICHMENT_API_BASE", api_base),
                ("CLUSTER_ENRICHMENT_API_KEY", api_key),
                ("CLUSTER_ENRICHMENT_MODEL", model),
            )
            if not value
        ]
        if missing:
            raise ExternalApiError(
                "Missing external enrichment settings: " + ", ".join(missing)
            )
        return cls(
            api_base=api_base,
            api_key=api_key,
            model=model,
            model_revision=model_revision,
        )

    @property
    def chat_completions_url(self) -> str:
        base = self.api_base.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return base + "/chat/completions"


class OpenAICompatibleClusterEnrichmentProvider:
    """Send one bounded request and strictly validate the JSON response."""

    def __init__(
        self,
        *,
        settings: ApiSettings,
        config: ClusterEnrichmentConfig,
        cache_dir: Path | None = None,
    ) -> None:
        self.settings = settings
        self.config = config
        self.cache_dir = cache_dir
        self.last_call_metadata: dict[str, Any] = {
            "cache_hit": False,
            "http_called": False,
            "usage": {},
        }

    def name_cluster(
        self, request: ClusterNamingRequest
    ) -> ClusterNamingResult:
        if request.member_count < self.config.min_cluster_members:
            raise ExternalApiError(
                "Cluster is below min_cluster_members and must not be sent"
            )
        body = build_chat_completion_payload(
            request,
            model=self.settings.model,
            max_examples=self.config.max_representative_examples,
            max_example_chars=self.config.max_example_chars,
            max_payload_chars=self.config.max_api_payload_chars,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            redact_text=self.config.redact_external_text,
        )
        cache_key = _cache_key(
            self.settings.chat_completions_url,
            self.settings.model_revision,
            body,
        )
        self.last_call_metadata = {
            "cache_key": cache_key,
            "cache_hit": False,
            "http_called": False,
            "usage": {},
        }
        cached = self._read_cache(cache_key)
        if cached is not None:
            self.last_call_metadata.update(
                {
                    "cache_hit": True,
                    "usage": _safe_usage(cached.get("usage")),
                }
            )
            try:
                return ClusterNamingResult.model_validate(cached["result"])
            except (KeyError, TypeError, ValidationError, ValueError):
                self.last_call_metadata["cache_hit"] = False

        http_request = urllib.request.Request(
            self.settings.chat_completions_url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "prompt-radar/0.1.0",
            },
            method="POST",
        )
        try:
            self.last_call_metadata["http_called"] = True
            with urllib.request.urlopen(
                http_request, timeout=self.config.timeout_seconds
            ) as response:
                raw_response = response.read(
                    self.config.max_response_bytes + 1
                )
                if len(raw_response) > self.config.max_response_bytes:
                    raise ExternalApiError(
                        "Cluster enrichment response exceeded the byte limit"
                    )
                envelope = json.loads(raw_response.decode("utf-8"))
        except ExternalApiError:
            raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ExternalApiError(
                f"Cluster enrichment HTTP request failed: {exc}"
            ) from exc
        try:
            content = envelope["choices"][0]["message"]["content"]
            parsed = _parse_json_content(content)
            result = ClusterNamingResult.model_validate(parsed)
            usage = _safe_usage(envelope.get("usage"))
            self.last_call_metadata["usage"] = usage
            self._write_cache(
                cache_key,
                {
                    "schema_version": "1.0",
                    "result": result.model_dump(mode="json"),
                    "usage": usage,
                },
            )
            return result
        except (KeyError, IndexError, TypeError, ValidationError, ValueError) as exc:
            raise ExternalApiError(
                f"Cluster enrichment response failed schema validation: {exc}"
            ) from exc

    def _read_cache(self, cache_key: str) -> dict[str, Any] | None:
        if self.cache_dir is None:
            return None
        path = self.cache_dir / f"{cache_key}.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _write_cache(self, cache_key: str, value: dict[str, Any]) -> None:
        if self.cache_dir is None:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / f"{cache_key}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(path)


def _cache_key(
    url: str, model_revision: str, body: dict[str, object]
) -> str:
    canonical = json.dumps(
        {
            "url": url,
            "model_revision": model_revision,
            "body": body,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _safe_usage(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        item = value.get(name)
        if isinstance(item, int) and item >= 0:
            result[name] = item
    return result


def _parse_json_content(content: Any) -> dict[str, Any]:
    if not isinstance(content, str):
        raise ValueError("choices[0].message.content must be a JSON string")
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            value = "\n".join(lines[1:-1])
            if value.lstrip().startswith("json"):
                value = value.lstrip()[4:].lstrip()
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("model response must be a JSON object")
    return parsed
