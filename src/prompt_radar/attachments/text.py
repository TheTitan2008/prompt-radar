"""Plain-text and CSV extraction."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from prompt_radar.attachments.base import AttachmentExtraction, ExtractedSection
from prompt_radar.models import Attachment


class TextAttachmentExtractor:
    """Decode bounded text without interpreting markup or instructions."""

    def extract(
        self, attachment: Attachment, path: Path
    ) -> AttachmentExtraction:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1251", errors="replace")
        if path.suffix.lower() == ".csv":
            rows = []
            for index, row in enumerate(csv.reader(io.StringIO(text))):
                rows.append(" | ".join(cell[:1000] for cell in row))
                if index >= 9999:
                    break
            text = "\n".join(rows)
        return AttachmentExtraction(
            attachment_id=attachment.attachment_id,
            filename=attachment.filename,
            extraction_status="success",
            sections=[
                ExtractedSection(
                    attachment_id=attachment.attachment_id,
                    filename=attachment.filename,
                    locator="file",
                    text=text,
                )
            ],
        )

