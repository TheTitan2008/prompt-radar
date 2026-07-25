"""Bounded attachment text extraction."""

from prompt_radar.attachments.base import (
    AttachmentExtraction,
    AttachmentExtractor,
    ExtractedSection,
)
from prompt_radar.attachments.registry import extract_attachment

__all__ = [
    "AttachmentExtraction",
    "AttachmentExtractor",
    "ExtractedSection",
    "extract_attachment",
]

