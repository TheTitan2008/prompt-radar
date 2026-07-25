"""Text-bearing PDF extraction without OCR."""

from __future__ import annotations

from pathlib import Path

from prompt_radar.attachments.base import AttachmentExtraction, ExtractedSection
from prompt_radar.models import Attachment


class PdfAttachmentExtractor:
    """Extract per-page PDF text and report image-only pages."""

    def extract(
        self, attachment: Attachment, path: Path
    ) -> AttachmentExtraction:
        if path.read_bytes()[:5] != b"%PDF-":
            return AttachmentExtraction(
                attachment_id=attachment.attachment_id,
                filename=attachment.filename,
                extraction_status="signature_mismatch",
                warnings=["PDF signature is missing"],
            )
        try:
            from pypdf import PdfReader
        except ImportError:
            return AttachmentExtraction(
                attachment_id=attachment.attachment_id,
                filename=attachment.filename,
                extraction_status="dependency_missing",
                warnings=["Install the attachments dependency group"],
            )
        try:
            reader = PdfReader(path, strict=True)
            sections = [
                ExtractedSection(
                    attachment_id=attachment.attachment_id,
                    filename=attachment.filename,
                    locator=f"page:{index}",
                    text=page.extract_text() or "",
                )
                for index, page in enumerate(reader.pages, 1)
            ]
        except Exception as exc:
            return AttachmentExtraction(
                attachment_id=attachment.attachment_id,
                filename=attachment.filename,
                extraction_status="failed",
                warnings=[f"PDF parsing failed: {exc}"],
            )
        warnings = []
        if not any(section.text.strip() for section in sections):
            warnings.append("PDF has no extractable text; OCR is disabled")
        return AttachmentExtraction(
            attachment_id=attachment.attachment_id,
            filename=attachment.filename,
            extraction_status="success",
            sections=sections,
            warnings=warnings,
        )

