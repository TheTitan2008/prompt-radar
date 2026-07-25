from __future__ import annotations

import stat
import zipfile
from pathlib import Path

import pytest

from prompt_radar.config import ResourceConfig
from prompt_radar.errors import ArchiveSecurityError
from prompt_radar.ingestion.zip_loader import secure_extract_zip


def make_zip(path: Path, name: str, data: bytes = b"x") -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, data)
    return path


def test_zip_slip_is_rejected(tmp_path: Path) -> None:
    archive = make_zip(tmp_path / "bad.zip", "../evil.txt")
    with pytest.raises(ArchiveSecurityError, match="Unsafe ZIP path"):
        secure_extract_zip(archive, tmp_path / "out", ResourceConfig())


def test_absolute_path_is_rejected(tmp_path: Path) -> None:
    archive = make_zip(tmp_path / "bad.zip", "C:/Windows/evil.txt")
    with pytest.raises(ArchiveSecurityError, match="Absolute ZIP path"):
        secure_extract_zip(archive, tmp_path / "out", ResourceConfig())


def test_symlink_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    info = zipfile.ZipInfo("link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(info, "../target")
    with pytest.raises(ArchiveSecurityError, match="symlink"):
        secure_extract_zip(archive, tmp_path / "out", ResourceConfig())


def test_high_compression_ratio_is_rejected(tmp_path: Path) -> None:
    archive = make_zip(tmp_path / "bomb.zip", "big.txt", b"0" * 100_000)
    limits = ResourceConfig(max_compression_ratio=2)
    with pytest.raises(ArchiveSecurityError, match="compression ratio"):
        secure_extract_zip(archive, tmp_path / "out", limits)


def test_nested_archive_is_rejected(tmp_path: Path) -> None:
    archive = make_zip(tmp_path / "nested.zip", "attachments/other.zip")
    with pytest.raises(ArchiveSecurityError, match="Nested archives"):
        secure_extract_zip(archive, tmp_path / "out", ResourceConfig())

