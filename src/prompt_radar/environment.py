"""Minimal allowlisted .env loading for explicit external API activation."""

from __future__ import annotations

import os
from pathlib import Path

_ALLOWED_KEYS = {
    "CLUSTER_ENRICHMENT_API_BASE",
    "CLUSTER_ENRICHMENT_API_KEY",
    "CLUSTER_ENRICHMENT_MODEL",
    "QWEN_API_BASE",
    "QWEN_API_KEY",
    "QWEN_CHAT_MODEL",
    "DEEPSEEK_API_BASE",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_CHAT_MODEL",
}


def load_api_env_file(path: Path) -> None:
    """Load only known API variables without overwriting the process env."""
    if not path.is_file():
        return
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{line_number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in _ALLOWED_KEYS:
            continue
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {'"', "'"}
        ):
            value = value[1:-1]
        os.environ.setdefault(key, value)
