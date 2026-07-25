"""Streaming JSON and JSONL readers."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from prompt_radar.errors import DatasetValidationError


def read_json(path: Path) -> dict[str, Any]:
    """Read one UTF-8 JSON object."""
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetValidationError(f"Cannot read JSON {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise DatasetValidationError(f"{path.name} must contain a JSON object")
    return value


def iter_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yield `(line_number, object)` without loading the whole JSONL file."""
    try:
        stream = path.open("r", encoding="utf-8")
    except OSError as exc:
        raise DatasetValidationError(f"Cannot open {path.name}: {exc}") from exc
    with stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetValidationError(
                    f"{path.name}:{line_number}: invalid JSON: {exc.msg}"
                ) from exc
            if not isinstance(value, dict):
                raise DatasetValidationError(
                    f"{path.name}:{line_number}: expected a JSON object"
                )
            yield line_number, value

