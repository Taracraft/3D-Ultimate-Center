"""Security checks for downloaded ZIP and 3MF containers."""

from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath


class ArchiveValidationError(ValueError):
    pass


def validate_archive(
    path: str | Path,
    *,
    max_files: int = 5000,
    max_uncompressed_bytes: int = 2 * 1024 * 1024 * 1024,
    max_ratio: float = 200.0,
) -> None:
    source = Path(path)
    if not zipfile.is_zipfile(source):
        return

    total_uncompressed = 0
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        if len(entries) > max_files:
            raise ArchiveValidationError("archive contains too many files")
        for entry in entries:
            name = PurePosixPath(entry.filename)
            if name.is_absolute() or ".." in name.parts:
                raise ArchiveValidationError("archive contains an unsafe path")
            total_uncompressed += entry.file_size
            if total_uncompressed > max_uncompressed_bytes:
                raise ArchiveValidationError("archive exceeds maximum uncompressed size")
            if entry.compress_size > 0:
                ratio = entry.file_size / entry.compress_size
                if ratio > max_ratio:
                    raise ArchiveValidationError("archive contains an excessive compression ratio")