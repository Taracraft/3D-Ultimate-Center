"""Standalone V6 gallery catalog with read-only V5 archive compatibility."""
from __future__ import annotations

import base64
from datetime import UTC, datetime
import mimetypes
from pathlib import Path
from typing import Any
import zipfile

from homeassistant.core import HomeAssistant

SUPPORTED_SUFFIXES = {".3mf", ".stl", ".obj"}
PREVIEW_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MAX_SCAN_FILES = 5000


class V6GalleryRuntime:
    """Scan the V6 gallery and expose the existing V5 archive read-only."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._roots: dict[str, Path] = {
            "v6": Path(hass.config.path("ultimate_3d_studio_v6", "gallery")),
            "v5": Path(hass.config.path("printer_control_center", "archive")),
        }
        self._roots["v6"].mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _encode(source: str, relative: str) -> str:
        payload = relative.encode("utf-8")
        token = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
        return f"{source}:{token}"

    @staticmethod
    def _decode_token(token: str) -> str:
        padding = "=" * (-len(token) % 4)
        return base64.urlsafe_b64decode(f"{token}{padding}".encode("ascii")).decode("utf-8")

    def resolve(self, asset_id: str) -> tuple[str, Path, str]:
        source, separator, token = str(asset_id).partition(":")
        if not separator or source not in self._roots or not token:
            raise KeyError("unknown gallery asset")
        relative = self._decode_token(token).replace("\\", "/")
        if relative.startswith("/") or ".." in Path(relative).parts:
            raise ValueError("invalid gallery path")
        root = self._roots[source].resolve(strict=False)
        path = root.joinpath(*Path(relative).parts).resolve(strict=False)
        try:
            path.relative_to(root)
        except ValueError as error:
            raise ValueError("gallery path leaves its storage root") from error
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise KeyError("gallery asset not found")
        return source, path, relative

    def search(self, query: str = "", limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        needle = query.strip().casefold()
        items: list[dict[str, Any]] = []
        scanned = 0

        for source, root in self._roots.items():
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if scanned >= MAX_SCAN_FILES:
                    break
                if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                    continue
                scanned += 1
                relative = path.relative_to(root).as_posix()
                searchable = f"{path.stem} {relative} {source}".casefold()
                if needle and needle not in searchable:
                    continue
                items.append(self._item(source, path, relative))

        items.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
        return items[:limit]

    def _item(self, source: str, path: Path, relative: str) -> dict[str, Any]:
        stat = path.stat()
        asset_id = self._encode(source, relative)
        folder = Path(relative).parent.as_posix()
        if folder == ".":
            folder = ""
        return {
            "asset_id": asset_id,
            "title": path.stem,
            "description": "V5-Archiv (nur lesend)" if source == "v5" else "V6-Galerie",
            "favorite": False,
            "created_at": datetime.fromtimestamp(stat.st_ctime, UTC).isoformat(),
            "updated_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
            "folder_id": folder or None,
            "tags": [path.suffix.lower().lstrip("."), "legacy-v5" if source == "v5" else "v6"],
            "source": source,
            "relative_path": relative,
            "file_name": path.name,
            "format": path.suffix.lower().lstrip("."),
            "size_bytes": stat.st_size,
            "preview_url": f"/api/ultimate_3d_studio_v6/v1/gallery/{asset_id}/preview",
            "download_url": f"/api/ultimate_3d_studio_v6/v1/gallery/{asset_id}/download",
            "read_only": source == "v5",
        }

    def preview(self, asset_id: str) -> tuple[bytes, str] | None:
        _source, path, _relative = self.resolve(asset_id)

        for suffix in PREVIEW_SUFFIXES:
            sidecar = path.with_suffix(suffix)
            if sidecar.is_file():
                return sidecar.read_bytes(), mimetypes.guess_type(sidecar.name)[0] or "image/png"

        if path.suffix.lower() != ".3mf":
            return None

        try:
            with zipfile.ZipFile(path, "r") as archive:
                names = [name for name in archive.namelist() if Path(name).suffix.lower() in PREVIEW_SUFFIXES]
                names.sort(
                    key=lambda name: (
                        0 if "thumbnail_middle" in name.casefold() else 1,
                        0 if "thumbnail" in name.casefold() else 1,
                        len(name),
                    )
                )
                if not names:
                    return None
                selected = names[0]
                payload = archive.read(selected)
                content_type = mimetypes.guess_type(selected)[0] or "image/png"
                return payload, content_type
        except (OSError, zipfile.BadZipFile, KeyError):
            return None

    def download(self, asset_id: str) -> tuple[bytes, str, str]:
        _source, path, _relative = self.resolve(asset_id)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return path.read_bytes(), content_type, path.name
