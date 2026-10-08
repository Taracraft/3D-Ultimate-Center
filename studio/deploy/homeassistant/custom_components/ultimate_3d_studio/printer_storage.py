"""Safe Bambu printer SD-card file management for Studio."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import base64
from pathlib import PurePosixPath
from typing import Any
import zipfile

from .bambu_direct_print import (
    FTPS_ERRORS,
    ImplicitFTP_TLS,
    _close_ftps,
    _connect_ftps,
)

MAX_UPLOAD_BYTES = 600_000_000
MAX_COPY_BYTES = 300_000_000
MAX_PREVIEW_SOURCE_BYTES = 100_000_000
MAX_PREVIEW_BYTES = 750_000
MAX_TREE_DEPTH = 10
MAX_TREE_FOLDERS = 500


class PrinterStorageError(RuntimeError):
    """Raised when one SD-card operation is invalid or fails."""


@dataclass(frozen=True, slots=True)
class PrinterStorageItem:
    path: str
    name: str
    kind: str
    size_bytes: int
    modified: str
    preview_data_url: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "kind": self.kind,
            "size_bytes": self.size_bytes,
            "modified": self.modified,
            "preview_data_url": self.preview_data_url,
        }


def normalize_remote_path(value: str, *, allow_root: bool = True) -> str:
    raw = str(value or "").replace("\\", "/").strip()
    path = PurePosixPath("/" + raw.lstrip("/"))
    if ".." in path.parts:
        raise PrinterStorageError("Unsicherer SD-Kartenpfad.")
    normalized = str(path)
    if normalized == "/" and not allow_root:
        raise PrinterStorageError("Der Wurzelordner darf nicht verändert werden.")
    return normalized


def safe_name(value: str) -> str:
    name = PurePosixPath(str(value or "").strip()).name
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise PrinterStorageError("Ungültiger Datei- oder Ordnername.")
    return name[:180]


def _kind(name: str, facts: dict[str, str]) -> str:
    if str(facts.get("type", "")).lower() == "dir":
        return "folder"
    lowered = name.casefold()
    if lowered.endswith(".3mf"):
        return "project"
    if lowered.endswith(".gcode") or lowered.endswith(".gcode.3mf"):
        return "gcode"
    if lowered.endswith((".stl", ".obj")):
        return "model"
    return "file"


class BambuPrinterStorage:
    """Manage one Bambu printer SD card through authenticated implicit FTPS."""

    def __init__(self, *, host: str, access_code: str, tls_insecure: bool) -> None:
        self.host = host
        self.access_code = access_code
        self.tls_insecure = tls_insecure

    def _connect(self, timeout: float = 20) -> ImplicitFTP_TLS:
        try:
            return _connect_ftps(
                host=self.host,
                access_code=self.access_code,
                tls_insecure=self.tls_insecure,
                timeout=timeout,
            )
        except FTPS_ERRORS as exc:
            raise PrinterStorageError(f"SD-Karte ist nicht erreichbar: {exc}") from exc

    def list_items(self, folder: str = "/", *, include_previews: bool = True) -> dict[str, Any]:
        normalized = normalize_remote_path(folder)
        client = self._connect()
        try:
            entries = self._entries(client, normalized)
            items: list[PrinterStorageItem] = []
            preview_count = 0
            for name, facts in entries:
                if name in {".", ".."}:
                    continue
                path = str(PurePosixPath(normalized) / name)
                kind = _kind(name, facts)
                try:
                    size = int(facts.get("size", 0) or 0)
                except (TypeError, ValueError):
                    size = 0
                preview = ""
                if include_previews and kind == "project" and preview_count < 24:
                    try:
                        preview = self._preview(client, path, size)
                        if preview:
                            preview_count += 1
                    except Exception:
                        preview = ""
                items.append(PrinterStorageItem(
                    path=path,
                    name=name,
                    kind=kind,
                    size_bytes=size,
                    modified=str(facts.get("modify", "") or ""),
                    preview_data_url=preview,
                ))
            items.sort(key=lambda item: (item.kind != "folder", item.name.casefold()))
            parent = "/" if normalized == "/" else str(PurePosixPath(normalized).parent)
            return {
                "folder": normalized,
                "parent": parent,
                "items": [item.as_dict() for item in items],
            }
        finally:
            _close_ftps(client)

    def tree(self) -> list[dict[str, Any]]:
        client = self._connect()
        try:
            result: list[dict[str, Any]] = [
                {"path": "/", "name": "SD-Karte", "depth": 0},
            ]
            self._walk(client, "/", result, depth=1)
            return result
        finally:
            _close_ftps(client)

    def download(self, path: str) -> bytes:
        normalized = normalize_remote_path(path, allow_root=False)
        client = self._connect(timeout=30)
        try:
            payload = BytesIO()
            client.retrbinary(f"RETR {normalized}", payload.write, blocksize=256 * 1024)
            data = payload.getvalue()
            if not data:
                raise PrinterStorageError("Die SD-Datei ist leer.")
            if len(data) > MAX_UPLOAD_BYTES:
                raise PrinterStorageError("Die SD-Datei überschreitet 600 MB.")
            return data
        except FTPS_ERRORS as exc:
            raise PrinterStorageError(f"SD-Datei konnte nicht geladen werden: {exc}") from exc
        finally:
            _close_ftps(client)

    def upload(self, filename: str, data: bytes, folder: str = "/", *, overwrite: bool = False) -> dict[str, Any]:
        name = safe_name(filename)
        if not data:
            raise PrinterStorageError("Die Upload-Datei ist leer.")
        if len(data) > MAX_UPLOAD_BYTES:
            raise PrinterStorageError("Die Upload-Datei überschreitet 600 MB.")
        directory = normalize_remote_path(folder)
        target = str(PurePosixPath(directory) / name)
        client = self._connect(timeout=30)
        try:
            if self._exists(client, target):
                if not overwrite:
                    raise FileExistsError(name)
                self._delete_path(client, target)
            client.storbinary(f"STOR {target}", BytesIO(data), blocksize=256 * 1024)
            remote_size = self._size(client, target)
            if remote_size is not None and remote_size != len(data):
                self._delete_path(client, target)
                raise PrinterStorageError(
                    f"Uploadprüfung fehlgeschlagen: lokal {len(data)}, remote {remote_size} Bytes.",
                )
            return {
                "path": target,
                "name": name,
                "kind": _kind(name, {}),
                "size_bytes": len(data),
            }
        except FileExistsError:
            raise
        except FTPS_ERRORS as exc:
            raise PrinterStorageError(f"Upload zur SD-Karte fehlgeschlagen: {exc}") from exc
        finally:
            _close_ftps(client)

    def create_folder(self, folder: str, name: str) -> dict[str, Any]:
        parent = normalize_remote_path(folder)
        clean = safe_name(name)
        target = str(PurePosixPath(parent) / clean)
        client = self._connect()
        try:
            if self._exists(client, target):
                raise FileExistsError(clean)
            client.mkd(target)
            if not self._exists(client, target):
                raise PrinterStorageError("Der neue SD-Ordner konnte nicht bestätigt werden.")
            return {"path": target, "name": clean, "kind": "folder", "size_bytes": 0}
        except FileExistsError:
            raise
        except FTPS_ERRORS as exc:
            raise PrinterStorageError(f"SD-Ordner konnte nicht erstellt werden: {exc}") from exc
        finally:
            _close_ftps(client)

    def rename(self, path: str, new_name: str) -> dict[str, Any]:
        source = normalize_remote_path(path, allow_root=False)
        clean = safe_name(new_name)
        target = str(PurePosixPath(source).parent / clean)
        client = self._connect()
        try:
            if self._exists(client, target):
                raise FileExistsError(clean)
            client.rename(source, target)
            if self._exists(client, source) or not self._exists(client, target):
                raise PrinterStorageError("Die Umbenennung konnte nicht bestätigt werden.")
            return {"path": target, "name": clean}
        except FileExistsError:
            raise
        except FTPS_ERRORS as exc:
            raise PrinterStorageError(f"SD-Eintrag konnte nicht umbenannt werden: {exc}") from exc
        finally:
            _close_ftps(client)

    def move(self, path: str, target_folder: str, *, overwrite: bool = False) -> dict[str, Any]:
        source = normalize_remote_path(path, allow_root=False)
        folder = normalize_remote_path(target_folder)
        target = str(PurePosixPath(folder) / PurePosixPath(source).name)
        if source == target:
            return {"path": source, "name": PurePosixPath(source).name}
        client = self._connect()
        try:
            if self._exists(client, target):
                if not overwrite:
                    raise FileExistsError(PurePosixPath(target).name)
                self._delete_path(client, target)
            client.rename(source, target)
            if self._exists(client, source) or not self._exists(client, target):
                raise PrinterStorageError("Das Verschieben konnte nicht bestätigt werden.")
            return {"path": target, "name": PurePosixPath(target).name}
        except FileExistsError:
            raise
        except FTPS_ERRORS as exc:
            raise PrinterStorageError(f"SD-Eintrag konnte nicht verschoben werden: {exc}") from exc
        finally:
            _close_ftps(client)

    def copy(self, path: str, target_folder: str, *, overwrite: bool = False) -> dict[str, Any]:
        source = normalize_remote_path(path, allow_root=False)
        folder = normalize_remote_path(target_folder)
        name = PurePosixPath(source).name
        target = str(PurePosixPath(folder) / name)
        client = self._connect(timeout=40)
        try:
            if self._is_directory(client, source):
                raise PrinterStorageError("Ordnerkopien werden nicht unterstützt; bitte einzelne Dateien auswählen.")
            size = self._size(client, source)
            if size is not None and size > MAX_COPY_BYTES:
                raise PrinterStorageError("Die Datei ist für eine SD-interne Kopie größer als 300 MB.")
            if self._exists(client, target):
                if not overwrite:
                    raise FileExistsError(name)
                self._delete_path(client, target)
            payload = BytesIO()
            client.retrbinary(f"RETR {source}", payload.write, blocksize=256 * 1024)
            data = payload.getvalue()
            if not data or len(data) > MAX_COPY_BYTES:
                raise PrinterStorageError("Die SD-Datei konnte nicht sicher kopiert werden.")
            client.storbinary(f"STOR {target}", BytesIO(data), blocksize=256 * 1024)
            remote_size = self._size(client, target)
            if remote_size is not None and remote_size != len(data):
                self._delete_path(client, target)
                raise PrinterStorageError("Die kopierte Datei hat eine abweichende Größe.")
            return {"path": target, "name": name, "size_bytes": len(data)}
        except FileExistsError:
            raise
        except FTPS_ERRORS as exc:
            raise PrinterStorageError(f"SD-Datei konnte nicht kopiert werden: {exc}") from exc
        finally:
            _close_ftps(client)

    def delete(self, path: str) -> None:
        normalized = normalize_remote_path(path, allow_root=False)
        client = self._connect()
        try:
            self._delete_path(client, normalized)
            if self._exists(client, normalized):
                raise PrinterStorageError("Das Löschen konnte nicht bestätigt werden.")
        except FTPS_ERRORS as exc:
            raise PrinterStorageError(f"SD-Eintrag konnte nicht gelöscht werden: {exc}") from exc
        finally:
            _close_ftps(client)

    def _entries(self, client: ImplicitFTP_TLS, folder: str) -> list[tuple[str, dict[str, str]]]:
        try:
            return list(client.mlsd(folder))
        except FTPS_ERRORS:
            result: list[tuple[str, dict[str, str]]] = []
            try:
                for raw in client.nlst(folder):
                    path = PurePosixPath(raw)
                    facts: dict[str, str] = {"type": "file", "size": "0"}
                    current = client.pwd()
                    try:
                        client.cwd(str(path))
                        facts["type"] = "dir"
                    except FTPS_ERRORS:
                        pass
                    finally:
                        try:
                            client.cwd(current)
                        except FTPS_ERRORS:
                            pass
                    result.append((path.name, facts))
            except FTPS_ERRORS:
                return []
            return result

    def _walk(self, client: ImplicitFTP_TLS, folder: str, result: list[dict[str, Any]], *, depth: int) -> None:
        if depth > MAX_TREE_DEPTH or len(result) >= MAX_TREE_FOLDERS:
            return
        for name, facts in self._entries(client, folder):
            if name in {".", ".."} or str(facts.get("type", "")).lower() != "dir":
                continue
            path = str(PurePosixPath(folder) / name)
            result.append({"path": path, "name": name, "depth": depth})
            self._walk(client, path, result, depth=depth + 1)

    def _exists(self, client: ImplicitFTP_TLS, path: str) -> bool:
        normalized = normalize_remote_path(path)
        if normalized == "/":
            return True
        parent = str(PurePosixPath(normalized).parent)
        name = PurePosixPath(normalized).name
        return any(entry_name == name for entry_name, _facts in self._entries(client, parent))

    def _is_directory(self, client: ImplicitFTP_TLS, path: str) -> bool:
        normalized = normalize_remote_path(path)
        current = client.pwd()
        try:
            client.cwd(normalized)
            return True
        except FTPS_ERRORS:
            return False
        finally:
            try:
                client.cwd(current)
            except FTPS_ERRORS:
                pass

    def _size(self, client: ImplicitFTP_TLS, path: str) -> int | None:
        try:
            client.voidcmd("TYPE I")
            value = client.size(path)
            return None if value is None else int(value)
        except FTPS_ERRORS:
            return None

    def _delete_path(self, client: ImplicitFTP_TLS, path: str) -> None:
        try:
            client.delete(path)
            return
        except FTPS_ERRORS:
            pass
        for name, facts in self._entries(client, path):
            if name in {".", ".."}:
                continue
            child = str(PurePosixPath(path) / name)
            if str(facts.get("type", "")).lower() == "dir":
                self._delete_path(client, child)
            else:
                client.delete(child)
        client.rmd(path)

    def _preview(self, client: ImplicitFTP_TLS, path: str, size: int) -> str:
        if size > MAX_PREVIEW_SOURCE_BYTES:
            return ""
        payload = BytesIO()
        client.retrbinary(f"RETR {path}", payload.write, blocksize=128 * 1024)
        raw = payload.getvalue()
        if not raw or len(raw) > MAX_PREVIEW_SOURCE_BYTES:
            return ""
        try:
            archive = zipfile.ZipFile(BytesIO(raw))
        except zipfile.BadZipFile:
            return ""
        with archive:
            candidates = sorted(
                (
                    name for name in archive.namelist()
                    if name.casefold().endswith((".png", ".jpg", ".jpeg", ".webp"))
                ),
                key=lambda name: (
                    0 if "plate_1" in name.casefold() else 1,
                    0 if "thumbnail" in name.casefold() else 1,
                    len(name),
                ),
            )
            for name in candidates:
                image = archive.read(name)
                if not image or len(image) > MAX_PREVIEW_BYTES:
                    continue
                lowered = name.casefold()
                mime = "image/png"
                if lowered.endswith((".jpg", ".jpeg")):
                    mime = "image/jpeg"
                elif lowered.endswith(".webp"):
                    mime = "image/webp"
                return f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}"
        return ""
