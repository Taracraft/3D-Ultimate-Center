"""Local 3MF file manager for the 3D-Printer Control Center dashboard."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import base64
import json
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Any
import zipfile

_MAX_BYTES = 150_000_000
_PREVIEW_MAX_BYTES = 600_000
_ARCHIVE_ZIP_MAX_BYTES = 1_000_000_000
_ARCHIVE_ZIP_MAX_FILES = 5_000
_EXPORT_METADATA_FILENAME = "_printer_control_center_export.json"


def _clean_segment(value: str, *, require_3mf: bool = False) -> str:
    name = Path(str(value or "")).name.strip()
    name = re.sub(r"[^A-Za-z0-9ÄÖÜäöüß._() +\-]", "_", name)
    if not name:
        raise ValueError("Name is empty")
    if name in {".", ".."}:
        raise ValueError("Invalid name")
    if require_3mf and not name.lower().endswith(".3mf"):
        raise ValueError("Only .3mf files are accepted")
    return name


def _safe_relative(value: str, *, allow_root: bool = True) -> PurePosixPath:
    raw = str(value or "").replace("\\", "/").strip("/")
    if not raw:
        if allow_root:
            return PurePosixPath(".")
        raise ValueError("Path is empty")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe path")
    return path


def _real_path(root: Path, relative: PurePosixPath) -> Path:
    target = (root / Path(*relative.parts)).resolve()
    root = root.resolve()
    if target != root and root not in target.parents:
        raise ValueError("Unsafe path")
    return target


def _preview(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            names = [
                name
                for name in archive.namelist()
                if name.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
            ]
            names.sort(
                key=lambda name: (
                    0 if "plate_1" in name.lower() else 1,
                    0 if "thumbnail" in name.lower() else 1,
                    len(name),
                )
            )
            for name in names:
                image = archive.read(name)
                if not image or len(image) > _PREVIEW_MAX_BYTES:
                    continue
                mime = "image/png"
                if name.lower().endswith((".jpg", ".jpeg")):
                    mime = "image/jpeg"
                elif name.lower().endswith(".webp"):
                    mime = "image/webp"
                return (
                    f"data:{mime};base64,"
                    f"{base64.b64encode(image).decode('ascii')}"
                )
    except Exception:
        return ""
    return ""


def _display_path(path: PurePosixPath) -> str:
    value = str(path)
    return "" if value == "." else value


@dataclass
class ArchiveStats:
    files: int
    folders: int
    bytes: int

    def as_dict(self) -> dict[str, int]:
        return {
            "files": self.files,
            "folders": self.folders,
            "bytes": self.bytes,
        }


class LocalArchiveRepository:
    """Manage a safe local 3MF directory tree inside Home Assistant."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def stats(self) -> dict[str, int]:
        files = 0
        folders = 0
        size = 0
        for path in self.root.rglob("*"):
            if path.is_dir():
                folders += 1
            elif path.is_file():
                files += 1
                size += path.stat().st_size
        return ArchiveStats(files=files, folders=folders, bytes=size).as_dict()

    def tree(self) -> list[dict[str, str]]:
        """Return every archive folder for the graphical move dialog."""
        result: list[dict[str, str]] = [
            {"name": "Hauptordner", "path": ""}
        ]
        for path in sorted(
            (item for item in self.root.rglob("*") if item.is_dir()),
            key=lambda item: item.relative_to(self.root).as_posix().lower(),
        ):
            relative = path.relative_to(self.root).as_posix()
            result.append(
                {
                    "name": path.name,
                    "path": relative,
                }
            )
        return result

    def list_items(self, folder: str = "") -> dict[str, Any]:
        relative = _safe_relative(folder)
        current = _real_path(self.root, relative)
        if not current.exists():
            raise FileNotFoundError(folder)
        if not current.is_dir():
            raise NotADirectoryError(folder)

        items: list[dict[str, Any]] = []
        for path in sorted(
            current.iterdir(),
            key=lambda item: (not item.is_dir(), item.name.lower()),
        ):
            rel = path.relative_to(self.root).as_posix()
            if path.is_dir():
                items.append(
                    {
                        "name": path.name,
                        "path": rel,
                        "size": 0,
                        "modified": path.stat().st_mtime,
                        "preview_data_url": "",
                        "kind": "folder",
                    }
                )
                continue

            if not path.name.lower().endswith(".3mf"):
                continue

            raw = path.read_bytes()
            items.append(
                {
                    "name": path.name,
                    "path": rel,
                    "size": len(raw),
                    "modified": path.stat().st_mtime,
                    "preview_data_url": _preview(raw),
                    "kind": "archive",
                }
            )

        parent = ""
        if relative != PurePosixPath("."):
            parent = _display_path(relative.parent)

        return {
            "folder": _display_path(relative),
            "parent": parent,
            "items": items,
            "stats": self.stats(),
        }

    def upload(
        self,
        filename: str,
        payload: bytes,
        folder: str = "",
    ) -> dict[str, Any]:
        name = _clean_segment(filename, require_3mf=True)
        if not payload:
            raise ValueError("Upload is empty")
        if len(payload) > _MAX_BYTES:
            raise ValueError("Upload exceeds 150 MB")

        directory = _real_path(self.root, _safe_relative(folder))
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / name
        target.write_bytes(payload)
        return {
            "name": target.name,
            "path": target.relative_to(self.root).as_posix(),
            "size": len(payload),
        }

    def create_folder(self, folder: str, name: str) -> dict[str, str]:
        directory = _real_path(self.root, _safe_relative(folder))
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / _clean_segment(name)
        target.mkdir(exist_ok=False)
        return {
            "name": target.name,
            "path": target.relative_to(self.root).as_posix(),
        }

    def delete(self, path: str) -> None:
        target = _real_path(self.root, _safe_relative(path, allow_root=False))
        if not target.exists():
            raise FileNotFoundError(path)
        if target == self.root:
            raise ValueError("Archive root cannot be deleted")
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    def rename(self, path: str, new_name: str) -> dict[str, str]:
        target = _real_path(self.root, _safe_relative(path, allow_root=False))
        if not target.exists():
            raise FileNotFoundError(path)
        clean = _clean_segment(
            new_name,
            require_3mf=target.is_file(),
        )
        destination = target.with_name(clean)
        if destination.exists():
            raise FileExistsError(clean)
        target.rename(destination)
        return {
            "name": destination.name,
            "path": destination.relative_to(self.root).as_posix(),
        }

    def move(self, path: str, target_folder: str, overwrite: bool = False) -> dict[str, str]:
        source = _real_path(self.root, _safe_relative(path, allow_root=False))
        if not source.exists():
            raise FileNotFoundError(path)
        directory = _real_path(self.root, _safe_relative(target_folder))
        if not directory.exists() or not directory.is_dir():
            raise NotADirectoryError(target_folder)
        destination = directory / source.name
        if source == destination:
            return {
                "name": source.name,
                "path": source.relative_to(self.root).as_posix(),
            }
        if source.is_dir() and source in directory.parents:
            raise ValueError("Folder cannot be moved into itself")
        if destination.exists():
            if not overwrite:
                raise FileExistsError(destination.name)
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()

        # Archive source and destination always live below the same HA config
        # directory. Use an actual filesystem rename instead of copy semantics.
        source.rename(destination)
        if source.exists() or not destination.exists():
            raise RuntimeError("Archive move verification failed")
        return {
            "name": destination.name,
            "path": destination.relative_to(self.root).as_posix(),
        }


    def export_zip(self) -> bytes:
        """Return a ZIP backup with the complete gallery folder structure."""
        buffer = BytesIO()
        metadata = {
            "format": "printer-control-center-gallery",
            "version": 1,
            "stats": self.stats(),
        }
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(
                (item for item in self.root.rglob("*") if item.is_dir()),
                key=lambda item: item.relative_to(self.root).as_posix().lower(),
            ):
                relative = path.relative_to(self.root).as_posix().rstrip("/") + "/"
                archive.writestr(relative, b"")
            for path in sorted(
                (item for item in self.root.rglob("*") if item.is_file() and item.name.lower().endswith(".3mf")),
                key=lambda item: item.relative_to(self.root).as_posix().lower(),
            ):
                archive.write(path, arcname=path.relative_to(self.root).as_posix())
            archive.writestr(
                _EXPORT_METADATA_FILENAME,
                json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
            )
        return buffer.getvalue()

    def inspect_import_zip(self, payload: bytes) -> dict[str, Any]:
        """Validate a gallery ZIP and return an import summary."""
        if not payload:
            raise ValueError("ZIP import is empty")
        if len(payload) > _ARCHIVE_ZIP_MAX_BYTES:
            raise ValueError("ZIP import exceeds 1 GB")
        files: list[str] = []
        folders: set[str] = set()
        conflicts: list[str] = []
        total_bytes = 0
        try:
            archive = zipfile.ZipFile(BytesIO(payload))
        except zipfile.BadZipFile as exc:
            raise ValueError("Invalid ZIP archive") from exc
        with archive:
            for info in archive.infolist():
                raw_name = str(info.filename or "").replace("\\", "/")
                if not raw_name or raw_name == _EXPORT_METADATA_FILENAME:
                    continue
                relative = _safe_relative(raw_name.rstrip("/"), allow_root=False)
                target = _real_path(self.root, relative)
                is_directory = info.is_dir() or raw_name.endswith("/")
                if is_directory:
                    folders.add(relative.as_posix())
                    continue
                if not raw_name.lower().endswith(".3mf"):
                    raise ValueError(f"Unsupported file in ZIP: {raw_name}")
                if info.file_size < 0:
                    raise ValueError(f"Invalid ZIP entry size: {raw_name}")
                total_bytes += int(info.file_size)
                if total_bytes > _ARCHIVE_ZIP_MAX_BYTES:
                    raise ValueError("Expanded ZIP import exceeds 1 GB")
                files.append(relative.as_posix())
                folders.update(parent.as_posix() for parent in relative.parents if parent != PurePosixPath("."))
                if target.exists():
                    conflicts.append(relative.as_posix())
                if len(files) > _ARCHIVE_ZIP_MAX_FILES:
                    raise ValueError("ZIP import contains more than 5000 models")
        return {
            "files": len(files),
            "folders": len(folders),
            "bytes": total_bytes,
            "conflicts": conflicts,
        }

    def import_zip(self, payload: bytes, *, overwrite: bool = False) -> dict[str, Any]:
        """Import a validated gallery ZIP while preserving its folder tree."""
        summary = self.inspect_import_zip(payload)
        conflicts = list(summary.get("conflicts", []))
        if conflicts and not overwrite:
            raise FileExistsError(
                "ZIP import contains existing files. Confirm overwrite and retry."
            )
        imported = 0
        created_folders: set[str] = set()
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            for info in archive.infolist():
                raw_name = str(info.filename or "").replace("\\", "/")
                if not raw_name or raw_name == _EXPORT_METADATA_FILENAME:
                    continue
                relative = _safe_relative(raw_name.rstrip("/"), allow_root=False)
                target = _real_path(self.root, relative)
                is_directory = info.is_dir() or raw_name.endswith("/")
                if is_directory:
                    target.mkdir(parents=True, exist_ok=True)
                    created_folders.add(relative.as_posix())
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and not overwrite:
                    raise FileExistsError(relative.as_posix())
                target.write_bytes(archive.read(info))
                imported += 1
        verified_files = 0
        verified_bytes = 0
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            for info in archive.infolist():
                raw_name = str(info.filename or "").replace("\\", "/")
                if not raw_name or raw_name == _EXPORT_METADATA_FILENAME or info.is_dir() or raw_name.endswith("/"):
                    continue
                relative = _safe_relative(raw_name, allow_root=False)
                target = _real_path(self.root, relative)
                if not target.is_file():
                    raise RuntimeError(f"Imported model is missing after extraction: {relative.as_posix()}")
                actual_size = target.stat().st_size
                if actual_size != int(info.file_size):
                    raise RuntimeError(f"Imported model size mismatch: {relative.as_posix()}")
                verified_files += 1
                verified_bytes += actual_size
        if verified_files != imported:
            raise RuntimeError("ZIP import verification count mismatch")
        result = dict(summary)
        result.update({
            "imported": imported,
            "created_folders": len(created_folders),
            "overwritten": len(conflicts) if overwrite else 0,
            "verified_files": verified_files,
            "verified_bytes": verified_bytes,
            "verification": "ok",
        })
        return result

    def preview(self, path: str) -> str:
        """Return the embedded preview for one archived 3MF project."""
        target = _real_path(self.root, _safe_relative(path, allow_root=False))
        if not target.is_file():
            raise FileNotFoundError(path)
        return _preview(target.read_bytes())

    def download(self, path: str) -> bytes:
        target = _real_path(self.root, _safe_relative(path, allow_root=False))
        if not target.is_file():
            raise FileNotFoundError(path)
        return target.read_bytes()