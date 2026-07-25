"""Attachment extractor contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from prompt_radar.models import Attachment


@dataclass
class ExtractedSection:
    """Text extracted from one bounded attachment section."""

    attachment_id: str
    filename: str
    locator: str
    text: str


@dataclass
class AttachmentExtraction:
    """Attachment extraction outcome."""

    attachment_id: str
    filename: str
    extraction_status: str
    sections: list[ExtractedSection] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class AttachmentExtractor(Protocol):
    """Protocol for format-specific, non-executing text extractors."""

    def extract(
        self, attachment: Attachment, path: Path
    ) -> AttachmentExtraction:
        """Extract bounded plain text and metadata from a file."""

