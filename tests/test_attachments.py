from __future__ import annotations

from pathlib import Path

from prompt_radar.attachments.registry import extract_attachment
from prompt_radar.config import AttachmentConfig
from prompt_radar.models import Attachment


def test_image_without_ocr_does_not_break_pipeline(tmp_path: Path) -> None:
    root = tmp_path
    (root / "attachments").mkdir()
    (root / "attachments" / "x.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    attachment = Attachment(
        attachment_id="a1",
        message_id="m1",
        filename="x.png",
        path="attachments/x.png",
        media_type="image/png",
        size_bytes=8,
    )
    result = extract_attachment(attachment, root, AttachmentConfig())
    assert result.extraction_status == "unsupported_without_ocr"
    assert result.warnings

