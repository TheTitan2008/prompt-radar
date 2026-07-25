"""Attachment format dispatch with signature-aware handling."""

from __future__ import annotations

from pathlib import Path

from prompt_radar.attachments.base import AttachmentExtraction
from prompt_radar.attachments.docx_file import DocxAttachmentExtractor
from prompt_radar.attachments.json_file import JsonAttachmentExtractor
from prompt_radar.attachments.pdf_file import PdfAttachmentExtractor
from prompt_radar.attachments.tabular import XlsxAttachmentExtractor
from prompt_radar.attachments.text import TextAttachmentExtractor
from prompt_radar.config import AttachmentConfig
from prompt_radar.models import Attachment


def extract_attachment(
    attachment: Attachment,
    root: Path,
    config: AttachmentConfig,
) -> AttachmentExtraction:
    """Dispatch to a bounded extractor and never perform OCR or execution."""
    path = root.joinpath(*Path(attachment.path.replace("\\", "/")).parts)
    suffix = path.suffix.casefold()
    if suffix in {".png", ".jpg", ".jpeg"}:
        return AttachmentExtraction(
            attachment_id=attachment.attachment_id,
            filename=attachment.filename,
            extraction_status="unsupported_without_ocr",
            warnings=["Image retained as metadata; OCR is disabled"],
        )
    if suffix in {".txt", ".md", ".csv"}:
        extractor = TextAttachmentExtractor()
    elif suffix == ".json":
        extractor = JsonAttachmentExtractor(
            config.max_json_depth, config.max_json_value_chars
        )
    elif suffix == ".xlsx":
        extractor = XlsxAttachmentExtractor(config.max_cells_per_sheet)
    elif suffix == ".docx":
        extractor = DocxAttachmentExtractor()
    elif suffix == ".pdf":
        extractor = PdfAttachmentExtractor()
    else:
        return AttachmentExtraction(
            attachment_id=attachment.attachment_id,
            filename=attachment.filename,
            extraction_status="unsupported",
            warnings=[f"Unsupported attachment type: {suffix or '[none]'}"],
        )
    return extractor.extract(attachment, path)

