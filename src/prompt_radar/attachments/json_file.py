"""Bounded JSON extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prompt_radar.attachments.base import AttachmentExtraction, ExtractedSection
from prompt_radar.models import Attachment


def _bounded(value: Any, *, depth: int, max_depth: int, max_chars: int) -> Any:
    if depth >= max_depth:
        return "[max depth reached]"
    if isinstance(value, dict):
        return {
            str(key)[:200]: _bounded(
                item, depth=depth + 1, max_depth=max_depth, max_chars=max_chars
            )
            for key, item in list(value.items())[:1000]
        }
    if isinstance(value, list):
        return [
            _bounded(item, depth=depth + 1, max_depth=max_depth, max_chars=max_chars)
            for item in value[:1000]
        ]
    if isinstance(value, str):
        if len(value) > max_chars:
            return value[:max_chars] + "…[truncated]"
        return value
    return value


class JsonAttachmentExtractor:
    """Parse JSON as data and serialize a bounded representation."""

    def __init__(self, max_depth: int, max_value_chars: int) -> None:
        self.max_depth = max_depth
        self.max_value_chars = max_value_chars

    def extract(
        self, attachment: Attachment, path: Path
    ) -> AttachmentExtraction:
        try:
            with path.open("r", encoding="utf-8-sig") as stream:
                value = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            return AttachmentExtraction(
                attachment_id=attachment.attachment_id,
                filename=attachment.filename,
                extraction_status="failed",
                warnings=[f"invalid JSON: {exc}"],
            )
        text = json.dumps(
            _bounded(
                value,
                depth=0,
                max_depth=self.max_depth,
                max_chars=self.max_value_chars,
            ),
            ensure_ascii=False,
            indent=2,
        )
        return AttachmentExtraction(
            attachment_id=attachment.attachment_id,
            filename=attachment.filename,
            extraction_status="success",
            sections=[
                ExtractedSection(
                    attachment_id=attachment.attachment_id,
                    filename=attachment.filename,
                    locator="json",
                    text=text,
                )
            ],
        )

