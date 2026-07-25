"""Read-only XLSX extraction."""

from __future__ import annotations

import zipfile
from pathlib import Path

from prompt_radar.attachments.base import AttachmentExtraction, ExtractedSection
from prompt_radar.models import Attachment


class XlsxAttachmentExtractor:
    """Read used XLSX cells without evaluating formulas or macros."""

    def __init__(self, max_cells_per_sheet: int) -> None:
        self.max_cells_per_sheet = max_cells_per_sheet

    def extract(
        self, attachment: Attachment, path: Path
    ) -> AttachmentExtraction:
        if not zipfile.is_zipfile(path):
            return AttachmentExtraction(
                attachment_id=attachment.attachment_id,
                filename=attachment.filename,
                extraction_status="signature_mismatch",
                warnings=["XLSX is not a valid OOXML ZIP container"],
            )
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                return AttachmentExtraction(
                    attachment_id=attachment.attachment_id,
                    filename=attachment.filename,
                    extraction_status="signature_mismatch",
                    warnings=["OOXML workbook structure is missing"],
                )
            if any(name.lower().endswith("vbaproject.bin") for name in names):
                macro_warning = ["VBA payload present and intentionally not executed"]
            else:
                macro_warning = []
        try:
            import openpyxl
        except ImportError:
            return AttachmentExtraction(
                attachment_id=attachment.attachment_id,
                filename=attachment.filename,
                extraction_status="dependency_missing",
                warnings=["Install the attachments dependency group"],
            )
        workbook = openpyxl.load_workbook(
            path, read_only=True, data_only=False, keep_links=False
        )
        sections: list[ExtractedSection] = []
        warnings = macro_warning
        try:
            for sheet in workbook.worksheets:
                rows: list[str] = []
                cell_count = 0
                for row in sheet.iter_rows():
                    values = []
                    for cell in row:
                        if cell.value is None:
                            values.append("")
                            continue
                        cell_count += 1
                        if cell_count > self.max_cells_per_sheet:
                            warnings.append(
                                f"{sheet.title}: used-cell limit reached; truncated"
                            )
                            break
                        value = str(cell.value)
                        if cell.data_type == "f":
                            value = f"[formula not executed] ={value}"
                        values.append(value[:2000])
                    if cell_count > self.max_cells_per_sheet:
                        break
                    if any(values):
                        while values and not values[-1]:
                            values.pop()
                        rows.append(" | ".join(values))
                sections.append(
                    ExtractedSection(
                        attachment_id=attachment.attachment_id,
                        filename=attachment.filename,
                        locator=f"sheet:{sheet.title}",
                        text="\n".join(rows),
                    )
                )
        finally:
            workbook.close()
        return AttachmentExtraction(
            attachment_id=attachment.attachment_id,
            filename=attachment.filename,
            extraction_status="success",
            sections=sections,
            warnings=warnings,
        )

