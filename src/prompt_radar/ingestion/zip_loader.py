"""Secure ZIP preflight and extraction."""

from __future__ import annotations

import os
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from prompt_radar.config import ResourceConfig
from prompt_radar.errors import ArchiveSecurityError

_ARCHIVE_EXTENSIONS = {
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
}
_DRIVE_PATH = re.compile(r"^[a-zA-Z]:")
_REPARSE_POINT = 0x400


def _validate_member(info: zipfile.ZipInfo, limits: ResourceConfig) -> None:
    raw_name = info.filename.replace("\\", "/")
    path = PurePosixPath(raw_name)
    if not raw_name or "\x00" in raw_name:
        raise ArchiveSecurityError("ZIP contains an empty or NUL-containing path")
    if raw_name.startswith(("/", "\\")) or _DRIVE_PATH.match(raw_name):
        raise ArchiveSecurityError(f"Absolute ZIP path is forbidden: {raw_name}")
    if any(":" in part for part in path.parts):
        raise ArchiveSecurityError(
            f"ZIP alternate-data-stream path is forbidden: {raw_name}"
        )
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ArchiveSecurityError(f"Unsafe ZIP path component: {raw_name}")
    if len(path.parts) > limits.max_directory_depth + 1:
        raise ArchiveSecurityError(f"ZIP path exceeds directory depth: {raw_name}")
    unix_mode = info.external_attr >> 16
    if stat.S_ISLNK(unix_mode):
        raise ArchiveSecurityError(f"ZIP symlink is forbidden: {raw_name}")
    dos_attributes = info.external_attr & 0xFFFF
    if dos_attributes & _REPARSE_POINT:
        raise ArchiveSecurityError(f"ZIP reparse point is forbidden: {raw_name}")
    if not info.is_dir() and path.suffix.lower() in _ARCHIVE_EXTENSIONS:
        raise ArchiveSecurityError(f"Nested archives are forbidden: {raw_name}")
    max_single = limits.max_single_file_mb * 1024 * 1024
    if info.file_size > max_single:
        raise ArchiveSecurityError(f"ZIP member exceeds single-file limit: {raw_name}")
    if info.file_size and info.compress_size == 0:
        raise ArchiveSecurityError(f"Suspicious zero compressed size: {raw_name}")
    ratio = info.file_size / max(info.compress_size, 1)
    if ratio > limits.max_compression_ratio:
        raise ArchiveSecurityError(
            f"ZIP member compression ratio {ratio:.1f} exceeds limit: {raw_name}"
        )


def secure_extract_zip(
    archive_path: Path, destination: Path, limits: ResourceConfig
) -> Path:
    """Validate every member, then extract without following archive paths."""
    if not zipfile.is_zipfile(archive_path):
        raise ArchiveSecurityError(f"Input is not a valid ZIP: {archive_path}")
    destination = destination.resolve()
    if destination.exists():
        raise ArchiveSecurityError(
            f"Extraction destination already exists: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
    ).resolve()
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if len(members) > limits.max_files:
                raise ArchiveSecurityError(
                    f"ZIP has {len(members)} files; limit is {limits.max_files}"
                )
            total_size = 0
            seen: set[str] = set()
            for info in members:
                _validate_member(info, limits)
                normalized = str(PurePosixPath(info.filename.replace("\\", "/")))
                key = normalized.casefold()
                if key in seen:
                    raise ArchiveSecurityError(f"Duplicate ZIP path: {normalized}")
                seen.add(key)
                total_size += info.file_size
                if total_size > limits.max_unpacked_mb * 1024 * 1024:
                    raise ArchiveSecurityError("ZIP exceeds total unpacked-size limit")
            for info in members:
                relative = Path(*PurePosixPath(info.filename.replace("\\", "/")).parts)
                target = (temp_root / relative).resolve()
                try:
                    target.relative_to(temp_root)
                except ValueError as exc:
                    raise ArchiveSecurityError(
                        f"ZIP member escapes extraction root: {info.filename}"
                    ) from exc
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as source, target.open("xb") as sink:
                    shutil.copyfileobj(source, sink, length=1024 * 1024)
                if target.stat().st_size != info.file_size:
                    raise ArchiveSecurityError(
                        f"Extracted size mismatch: {info.filename}"
                    )
        os.replace(temp_root, destination)
        return destination
    except BaseException:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise
