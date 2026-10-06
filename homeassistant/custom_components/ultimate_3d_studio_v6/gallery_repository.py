"""Independent V6 gallery repository preserving the existing V5 archive tree."""
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

from .geometry_export import export_binary_stl

MODEL_SUFFIXES = {".3mf", ".stl", ".obj"}
PREVIEW_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MAX_MODEL_BYTES = 500_000_000
MAX_PREVIEW_BYTES = 2_000_000
MAX_ZIP_BYTES = 2_000_000_000
MAX_ZIP_FILES = 10_000
EXPORT_METADATA = "_ultimate_3d_studio_v6_gallery.json"


def _clean_segment(value: str, *, suffix_required: bool = False) -> str:
    name = Path(str(value or "")).name.strip()
    name = re.sub(r"[^A-Za-z0-9ÄÖÜäöüß._() +\-]", "_", name)
    if not name or name in {".", ".."}:
        raise ValueError("Ungültiger Name")
    if suffix_required and Path(name).suffix.lower() not in MODEL_SUFFIXES:
        raise ValueError("Nur 3MF-, STL- und OBJ-Dateien sind erlaubt")
    return name


def _safe_relative(value: str, *, allow_root: bool = True) -> PurePosixPath:
    raw = str(value or "").replace("\\", "/").strip("/")
    if not raw:
        if allow_root:
            return PurePosixPath(".")
        raise ValueError("Pfad darf nicht leer sein")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsicherer Galeriepfad")
    return path


def _real_path(root: Path, relative: PurePosixPath) -> Path:
    resolved_root = root.resolve(strict=False)
    target = resolved_root.joinpath(*relative.parts).resolve(strict=False)
    try:
        target.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("Galeriepfad verlässt das Stammverzeichnis") from exc
    return target


def _display(path: PurePosixPath) -> str:
    return "" if str(path) == "." else path.as_posix()


def _encode_path(path: str) -> str:
    return base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_path(token: str) -> str:
    padding = "=" * (-len(token) % 4)
    try:
        return base64.urlsafe_b64decode(f"{token}{padding}".encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Ungültige Galerie-ID") from exc


def _preview_from_3mf(payload: bytes) -> tuple[bytes, str] | None:
    try:
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            names = [name for name in archive.namelist() if Path(name).suffix.lower() in PREVIEW_SUFFIXES]
            names.sort(key=lambda name: (
                0 if "plate_1" in name.casefold() else 1,
                0 if "thumbnail_middle" in name.casefold() else 1,
                0 if "thumbnail" in name.casefold() else 1,
                len(name),
            ))
            for name in names:
                image = archive.read(name)
                if not image or len(image) > MAX_PREVIEW_BYTES:
                    continue
                suffix = Path(name).suffix.lower()
                content_type = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/webp" if suffix == ".webp" else "image/png"
                return image, content_type
    except (zipfile.BadZipFile, KeyError, OSError):
        return None
    return None


@dataclass(frozen=True)
class GalleryStats:
    files: int
    folders: int
    bytes: int

    def as_dict(self) -> dict[str, int]:
        return {"files": self.files, "folders": self.folders, "bytes": self.bytes}


class V6GalleryRepository:
    """Safe read/write model library with V5-compatible folder semantics."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def asset_id(relative: str) -> str:
        return f"path:{_encode_path(relative)}"

    @staticmethod
    def path_from_asset_id(asset_id: str) -> str:
        prefix, separator, token = str(asset_id).partition(":")
        if prefix != "path" or not separator or not token:
            raise ValueError("Ungültige Galerie-ID")
        return _decode_path(token)

    def stats(self) -> dict[str, int]:
        files = folders = size = 0
        for path in self.root.rglob("*"):
            if path.is_dir():
                folders += 1
            elif path.is_file() and path.suffix.lower() in MODEL_SUFFIXES:
                files += 1
                size += path.stat().st_size
        return GalleryStats(files, folders, size).as_dict()

    def tree(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = [{"name": "Hauptordner", "path": "", "depth": 0}]
        for path in sorted(
            (item for item in self.root.rglob("*") if item.is_dir()),
            key=lambda item: item.relative_to(self.root).as_posix().casefold(),
        ):
            relative = path.relative_to(self.root).as_posix()
            result.append({
                "name": path.name,
                "path": relative,
                "depth": len(PurePosixPath(relative).parts),
            })
        return result

    def list_folder(self, folder: str = "", query: str = "", recursive: bool = False) -> dict[str, Any]:
        relative = _safe_relative(folder)
        current = _real_path(self.root, relative)
        if not current.exists():
            raise FileNotFoundError(folder)
        if not current.is_dir():
            raise NotADirectoryError(folder)
        needle = query.strip().casefold()
        iterator = current.rglob("*") if recursive or needle else current.iterdir()
        items: list[dict[str, Any]] = []
        for path in iterator:
            if path == current:
                continue
            if path.is_dir():
                if needle and needle not in path.name.casefold() and needle not in path.relative_to(self.root).as_posix().casefold():
                    continue
                if not recursive and path.parent != current:
                    continue
                items.append(self._folder_item(path))
                continue
            if path.suffix.lower() not in MODEL_SUFFIXES:
                continue
            relative_path = path.relative_to(self.root).as_posix()
            if needle and needle not in f"{path.stem} {relative_path}".casefold():
                continue
            items.append(self._file_item(path))
        items.sort(key=lambda item: (item["kind"] != "folder", str(item["name"]).casefold()))
        parent = "" if relative == PurePosixPath(".") else _display(relative.parent)
        return {
            "folder": _display(relative),
            "parent": parent,
            "items": items,
            "tree": self.tree(),
            "stats": self.stats(),
            "canonical_root": self.root.as_posix(),
        }

    def _folder_item(self, path: Path) -> dict[str, Any]:
        relative = path.relative_to(self.root).as_posix()
        return {
            "asset_id": self.asset_id(relative),
            "kind": "folder",
            "name": path.name,
            "title": path.name,
            "path": relative,
            "folder_id": path.parent.relative_to(self.root).as_posix() if path.parent != self.root else "",
            "size_bytes": 0,
            "modified": path.stat().st_mtime,
            "read_only": False,
        }

    def _file_item(self, path: Path) -> dict[str, Any]:
        relative = path.relative_to(self.root).as_posix()
        stat = path.stat()
        return {
            "asset_id": self.asset_id(relative),
            "kind": "model",
            "name": path.name,
            "title": path.stem,
            "path": relative,
            "relative_path": relative,
            "folder_id": path.parent.relative_to(self.root).as_posix() if path.parent != self.root else "",
            "file_name": path.name,
            "format": path.suffix.lower().lstrip("."),
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
            "updated_at": stat.st_mtime,
            "preview_url": f"/api/ultimate_3d_studio_v6/v1/gallery/manage/{self.asset_id(relative)}/preview",
            "download_url": f"/api/ultimate_3d_studio_v6/v1/gallery/manage/{self.asset_id(relative)}/download",
            "cad_url": f"/api/ultimate_3d_studio_v6/v1/gallery/manage/{self.asset_id(relative)}/model-stl",
            "read_only": False,
        }

    def resolve(self, asset_id_or_path: str) -> Path:
        relative = self.path_from_asset_id(asset_id_or_path) if str(asset_id_or_path).startswith("path:") else str(asset_id_or_path)
        target = _real_path(self.root, _safe_relative(relative, allow_root=False))
        if target == self.root.resolve(strict=False):
            raise ValueError("Der Galerie-Hauptordner ist kein veränderbarer Eintrag")
        if not target.exists():
            raise FileNotFoundError(relative)
        return target

    def preview(self, asset_id_or_path: str) -> tuple[bytes, str] | None:
        path = self.resolve(asset_id_or_path)
        if not path.is_file():
            return None
        for suffix in PREVIEW_SUFFIXES:
            sidecar = path.with_suffix(suffix)
            if sidecar.is_file() and sidecar.stat().st_size <= MAX_PREVIEW_BYTES:
                content_type = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/webp" if suffix == ".webp" else "image/png"
                return sidecar.read_bytes(), content_type
        if path.suffix.lower() == ".3mf":
            return _preview_from_3mf(path.read_bytes())
        return None

    def download(self, asset_id_or_path: str) -> tuple[bytes, str]:
        path = self.resolve(asset_id_or_path)
        if not path.is_file() or path.suffix.lower() not in MODEL_SUFFIXES:
            raise FileNotFoundError(asset_id_or_path)
        return path.read_bytes(), path.name

    def model_stl(self, asset_id_or_path: str) -> tuple[bytes, str]:
        path = self.resolve(asset_id_or_path)
        if not path.is_file():
            raise FileNotFoundError(asset_id_or_path)
        if path.suffix.lower() == ".stl":
            return path.read_bytes(), path.name
        if path.suffix.lower() != ".3mf":
            raise ValueError("CAD-Import wird für dieses Dateiformat noch nicht unterstützt")
        return export_binary_stl(path.read_bytes(), f"Ultimate 3D Studio V6 {path.stem}"), f"{path.stem}.stl"

    def upload(self, filename: str, payload: bytes, folder: str = "", overwrite: bool = False) -> dict[str, Any]:
        name = _clean_segment(filename, suffix_required=True)
        if not payload:
            raise ValueError("Upload ist leer")
        if len(payload) > MAX_MODEL_BYTES:
            raise ValueError("Upload überschreitet 500 MB")
        directory = _real_path(self.root, _safe_relative(folder))
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / name
        if target.exists() and not overwrite:
            raise FileExistsError(name)
        target.write_bytes(payload)
        return self._file_item(target)

    def create_folder(self, folder: str, name: str) -> dict[str, Any]:
        directory = _real_path(self.root, _safe_relative(folder))
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / _clean_segment(name)
        target.mkdir(exist_ok=False)
        return self._folder_item(target)

    def rename(self, path: str, new_name: str) -> dict[str, Any]:
        source = self.resolve(path)
        name = _clean_segment(new_name, suffix_required=source.is_file())
        target = source.with_name(name)
        if target.exists():
            raise FileExistsError(name)
        source.rename(target)
        return self._folder_item(target) if target.is_dir() else self._file_item(target)

    def move(self, path: str, target_folder: str, overwrite: bool = False) -> dict[str, Any]:
        source = self.resolve(path)
        directory = _real_path(self.root, _safe_relative(target_folder))
        if not directory.is_dir():
            raise NotADirectoryError(target_folder)
        if source.is_dir() and (source == directory or source in directory.parents):
            raise ValueError("Ordner kann nicht in sich selbst verschoben werden")
        target = directory / source.name
        if source == target:
            return self._folder_item(source) if source.is_dir() else self._file_item(source)
        if target in source.parents:
            raise ValueError("Das Ziel enthält die Quelle und darf nicht überschrieben werden")
        if target.exists():
            if not overwrite:
                raise FileExistsError(target.name)
            shutil.rmtree(target) if target.is_dir() else target.unlink()
        source.rename(target)
        return self._folder_item(target) if target.is_dir() else self._file_item(target)

    def delete(self, path: str) -> dict[str, str]:
        target = self.resolve(path)
        relative = target.relative_to(self.root).as_posix()
        shutil.rmtree(target) if target.is_dir() else target.unlink()
        return {"path": relative, "deleted": "true"}

    def export_zip(self) -> bytes:
        buffer = BytesIO()
        metadata = {
            "format": "ultimate-3d-studio-v6-gallery",
            "version": 1,
            "stats": self.stats(),
            "preserves_existing_v5_tree": True,
        }
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(self.root.rglob("*"), key=lambda item: item.relative_to(self.root).as_posix().casefold()):
                relative = path.relative_to(self.root).as_posix()
                if path.is_dir():
                    archive.writestr(relative.rstrip("/") + "/", b"")
                elif path.suffix.lower() in MODEL_SUFFIXES or path.suffix.lower() in PREVIEW_SUFFIXES:
                    archive.write(path, arcname=relative)
            archive.writestr(EXPORT_METADATA, json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"))
        return buffer.getvalue()

    def inspect_zip(self, payload: bytes) -> dict[str, Any]:
        if not payload:
            raise ValueError("ZIP-Import ist leer")
        if len(payload) > MAX_ZIP_BYTES:
            raise ValueError("ZIP-Import überschreitet 2 GB")
        files: list[str] = []
        folders: set[str] = set()
        conflicts: list[str] = []
        total = 0
        try:
            archive = zipfile.ZipFile(BytesIO(payload))
        except zipfile.BadZipFile as exc:
            raise ValueError("Ungültiges ZIP-Archiv") from exc
        with archive:
            for info in archive.infolist():
                raw = str(info.filename or "").replace("\\", "/")
                if not raw or raw == EXPORT_METADATA:
                    continue
                relative = _safe_relative(raw.rstrip("/"), allow_root=False)
                target = _real_path(self.root, relative)
                if info.is_dir() or raw.endswith("/"):
                    folders.add(relative.as_posix())
                    continue
                suffix = Path(raw).suffix.lower()
                if suffix not in MODEL_SUFFIXES and suffix not in PREVIEW_SUFFIXES:
                    raise ValueError(f"Nicht unterstützte Datei im ZIP: {raw}")
                total += int(info.file_size)
                if total > MAX_ZIP_BYTES:
                    raise ValueError("Entpacktes ZIP überschreitet 2 GB")
                files.append(relative.as_posix())
                folders.update(parent.as_posix() for parent in relative.parents if parent != PurePosixPath("."))
                if target.exists():
                    conflicts.append(relative.as_posix())
                if len(files) > MAX_ZIP_FILES:
                    raise ValueError("ZIP enthält mehr als 10000 Dateien")
        return {"files": len(files), "folders": len(folders), "bytes": total, "conflicts": conflicts}

    def import_zip(self, payload: bytes, overwrite: bool = False) -> dict[str, Any]:
        summary = self.inspect_zip(payload)
        if summary["conflicts"] and not overwrite:
            raise FileExistsError("ZIP enthält vorhandene Dateien")
        imported = overwritten = 0
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            for info in archive.infolist():
                raw = str(info.filename or "").replace("\\", "/")
                if not raw or raw == EXPORT_METADATA:
                    continue
                relative = _safe_relative(raw.rstrip("/"), allow_root=False)
                target = _real_path(self.root, relative)
                if info.is_dir() or raw.endswith("/"):
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    if not overwrite:
                        raise FileExistsError(relative.as_posix())
                    overwritten += 1
                target.write_bytes(archive.read(info))
                imported += 1
        result = dict(summary)
        result.update({"imported": imported, "overwritten": overwritten, "verification": "ok"})
        return result
