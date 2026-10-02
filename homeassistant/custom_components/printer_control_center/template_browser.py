"""FTPS-backed SD-card browser and file manager for Bambu printers."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import base64
import ftplib
import logging
from pathlib import PurePosixPath
import socket
import ssl
import time
from typing import Any
import zipfile

from .const import TEMPLATE_PREVIEW_MAX_BYTES

_LOGGER = logging.getLogger(__name__)


class ImplicitFTP_TLS(ftplib.FTP_TLS):
    """Implicit TLS variant for Bambu FTPS on TCP 990."""

    def connect(self, host: str = "", port: int = 0, timeout: float | None = -999, source_address=None):
        if host:
            self.host = host
        if port:
            self.port = port
        if timeout != -999:
            self.timeout = timeout
        self.source_address = source_address

        self.sock = socket.create_connection(
            (self.host, self.port),
            self.timeout,
            source_address=self.source_address,
        )
        self.af = self.sock.family
        self.sock = self.context.wrap_socket(self.sock, server_hostname=self.host)
        self.file = self.sock.makefile("r", encoding=self.encoding)
        self.welcome = self.getresp()
        return self.welcome


@dataclass
class TemplateItem:
    path: str
    name: str
    size: int
    modified: str = ""
    preview_data_url: str = ""
    kind: str = "file"

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "size": self.size,
            "modified": self.modified,
            "preview_data_url": self.preview_data_url,
            "kind": self.kind,
        }


class SdTemplateBrowser:
    """FTPS-backed file manager for one printer SD card."""

    def __init__(self, host: str, access_code: str) -> None:
        self.host = host
        self.access_code = access_code
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    def _connect(self) -> ImplicitFTP_TLS:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        ftp = ImplicitFTP_TLS(context=context, timeout=12)
        ftp.connect(self.host, 990, timeout=12)
        ftp.login("bblp", self.access_code)
        ftp.prot_p()
        return ftp

    def _invalidate(self) -> None:
        self._cache.clear()

    def list_items(self, folder: str = "/", force: bool = False) -> list[dict[str, Any]]:
        normalized = self._normalize(folder)
        cached = self._cache.get(normalized)
        if not force and cached and (time.monotonic() - cached[0]) < 20:
            return [dict(item) for item in cached[1]]

        ftp = self._connect()
        try:
            items = self._list_folder(ftp, normalized)

            previews = 0
            for item in items:
                if item.kind != "project" or previews >= 36:
                    continue
                try:
                    item.preview_data_url = self._preview_for(ftp, item.path)
                    previews += 1
                except Exception:
                    _LOGGER.debug("Unable to extract SD preview for %s", item.path, exc_info=True)

            result = [item.as_dict() for item in items]
            self._cache[normalized] = (time.monotonic(), result)
            return [dict(item) for item in result]
        finally:
            self._close(ftp)

    # Backwards-compatible alias for existing HTTP endpoint.
    def list_templates(self, force: bool = False) -> list[dict[str, Any]]:
        return self.list_items("/", force)

    def tree(self) -> list[dict[str, Any]]:
        ftp = self._connect()
        try:
            folders = [{"path": "/", "name": "SD-Karte"}]
            self._walk_folders(ftp, "/", folders, depth=0)
            return folders
        finally:
            self._close(ftp)

    def create_folder(self, folder: str, name: str) -> dict[str, Any]:
        parent = self._normalize(folder)
        safe_name = self._safe_name(name)
        target = str(PurePosixPath(parent) / safe_name)
        ftp = self._connect()
        try:
            ftp.mkd(target)
            if not self._path_exists(ftp, target):
                raise RuntimeError("SD-card folder creation verification failed")
            self._invalidate()
            return {"path": target, "name": safe_name, "kind": "folder", "size": 0}
        finally:
            self._close(ftp)

    def rename(self, path: str, new_name: str) -> dict[str, Any]:
        source = self._normalize(path)
        safe_name = self._safe_name(new_name)
        target = str(PurePosixPath(source).parent / safe_name)
        ftp = self._connect()
        try:
            ftp.rename(source, target)
            self._invalidate()
            return {"path": target, "name": safe_name}
        finally:
            self._close(ftp)

    def move(self, path: str, target_folder: str = "/", overwrite: bool = False) -> dict[str, Any]:
        source = self._normalize(path)
        folder = self._normalize(target_folder)
        target = str(PurePosixPath(folder) / PurePosixPath(source).name)
        if source == target:
            return {"path": source, "name": PurePosixPath(source).name}
        ftp = self._connect()
        try:
            if self._path_exists(ftp, target):
                if not overwrite:
                    raise FileExistsError(PurePosixPath(target).name)
                self._delete_path(ftp, target)
            ftp.rename(source, target)
            if self._path_exists(ftp, source) or not self._path_exists(ftp, target):
                raise RuntimeError("SD-card move verification failed")
            self._invalidate()
            return {"path": target, "name": PurePosixPath(target).name}
        finally:
            self._close(ftp)

    def delete(self, path: str) -> None:
        normalized = self._normalize(path)
        ftp = self._connect()
        try:
            self._delete_path(ftp, normalized)
            if self._path_exists(ftp, normalized):
                raise RuntimeError("SD-card delete verification failed")
            self._invalidate()
        finally:
            self._close(ftp)

    def preview(self, path: str) -> str:
        """Return the embedded preview for one SD-card 3MF project."""
        normalized = self._normalize(path)
        ftp = self._connect()
        try:
            return self._preview_for(ftp, normalized)
        finally:
            self._close(ftp)

    def download(self, path: str) -> bytes:
        normalized = self._normalize(path)
        ftp = self._connect()
        try:
            payload = BytesIO()
            ftp.retrbinary(f"RETR {normalized}", payload.write)
            return payload.getvalue()
        finally:
            self._close(ftp)

    def upload(self, filename: str, payload: bytes, folder: str = "/") -> dict[str, Any]:
        """Upload one 3MF project to the printer SD card."""
        safe_name = PurePosixPath(str(filename or "")).name
        if not safe_name or not safe_name.lower().endswith(".3mf"):
            raise ValueError("Only .3mf uploads are accepted")
        if not payload:
            raise ValueError("Upload is empty")
        if len(payload) > 150_000_000:
            raise ValueError("Upload exceeds 150 MB")

        normalized_folder = self._normalize(folder)
        target = str(PurePosixPath(normalized_folder) / safe_name)
        ftp = self._connect()
        try:
            ftp.storbinary(f"STOR {target}", BytesIO(payload))
            self._invalidate()
            return {"path": target, "name": safe_name, "size": len(payload)}
        finally:
            self._close(ftp)

    def _list_folder(self, ftp: ImplicitFTP_TLS, folder: str) -> list[TemplateItem]:
        entries = self._entries(ftp, folder)
        collected: list[TemplateItem] = []

        for name, facts in entries:
            if name in (".", ".."):
                continue

            path = str(PurePosixPath(folder) / name)
            kind = str(facts.get("type", "file")).lower()

            if kind == "dir":
                collected.append(
                    TemplateItem(
                        path=path,
                        name=name,
                        size=0,
                        modified=str(facts.get("modify", "") or ""),
                        kind="folder",
                    )
                )
                continue

            try:
                size = int(facts.get("size", 0) or 0)
            except ValueError:
                size = 0

            lowered = name.lower()
            collected.append(
                TemplateItem(
                    path=path,
                    name=name,
                    size=size,
                    modified=str(facts.get("modify", "") or ""),
                    kind="project" if lowered.endswith(".3mf") else "file",
                )
            )

        return sorted(
            collected,
            key=lambda item: (
                0 if item.kind == "folder" else 1,
                item.name.lower(),
            ),
        )

    def _path_exists(self, ftp: ImplicitFTP_TLS, path: str) -> bool:
        normalized = self._normalize(path)
        parent = str(PurePosixPath(normalized).parent)
        name = PurePosixPath(normalized).name
        return any(entry_name == name for entry_name, _facts in self._entries(ftp, parent))

    def _entries(self, ftp: ImplicitFTP_TLS, folder: str) -> list[tuple[str, dict[str, str]]]:
        try:
            return list(ftp.mlsd(folder))
        except Exception:
            _LOGGER.debug("MLSD failed for %s; using NLST fallback", folder, exc_info=True)

        result: list[tuple[str, dict[str, str]]] = []
        try:
            for raw in ftp.nlst(folder):
                path = PurePosixPath(raw)
                name = path.name
                facts: dict[str, str] = {"type": "file", "size": "0"}
                try:
                    current = ftp.pwd()
                    ftp.cwd(str(path))
                    ftp.cwd(current)
                    facts["type"] = "dir"
                except Exception:
                    pass
                result.append((name, facts))
        except Exception:
            return []
        return result

    def _walk_folders(self, ftp: ImplicitFTP_TLS, folder: str, target: list[dict[str, Any]], depth: int) -> None:
        if depth >= 8 or len(target) >= 300:
            return
        for name, facts in self._entries(ftp, folder):
            if name in (".", "..") or str(facts.get("type", "")).lower() != "dir":
                continue
            path = str(PurePosixPath(folder) / name)
            target.append({"path": path, "name": name})
            self._walk_folders(ftp, path, target, depth + 1)

    def _delete_path(self, ftp: ImplicitFTP_TLS, path: str) -> None:
        try:
            ftp.delete(path)
            return
        except Exception:
            pass

        entries = self._entries(ftp, path)
        for name, facts in entries:
            if name in (".", ".."):
                continue
            child = str(PurePosixPath(path) / name)
            if str(facts.get("type", "")).lower() == "dir":
                self._delete_path(ftp, child)
            else:
                ftp.delete(child)
        ftp.rmd(path)

    def _preview_for(self, ftp: ImplicitFTP_TLS, path: str) -> str:
        payload = BytesIO()
        ftp.retrbinary(f"RETR {self._normalize(path)}", payload.write)
        raw = payload.getvalue()

        if len(raw) > 80_000_000:
            return ""

        with zipfile.ZipFile(BytesIO(raw)) as archive:
            candidates = [
                name
                for name in archive.namelist()
                if name.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
            ]

            preferred = sorted(
                candidates,
                key=lambda name: (
                    0 if "plate_1" in name.lower() else 1,
                    0 if "thumbnail" in name.lower() else 1,
                    0 if "metadata" in name.lower() else 1,
                    len(name),
                ),
            )

            for name in preferred:
                image = archive.read(name)
                if not image or len(image) > TEMPLATE_PREVIEW_MAX_BYTES:
                    continue

                lowered = name.lower()
                mime = "image/png"
                if lowered.endswith((".jpg", ".jpeg")):
                    mime = "image/jpeg"
                elif lowered.endswith(".webp"):
                    mime = "image/webp"

                encoded = base64.b64encode(image).decode("ascii")
                return f"data:{mime};base64,{encoded}"

        return ""

    @staticmethod
    def _safe_name(name: str) -> str:
        safe = PurePosixPath(str(name or "").strip()).name
        if not safe or safe in {".", ".."}:
            raise ValueError("Invalid name")
        return safe

    @staticmethod
    def _normalize(path: str) -> str:
        normalized = str(PurePosixPath("/" + str(path or "").lstrip("/")))
        if ".." in PurePosixPath(normalized).parts:
            raise ValueError("Invalid SD-card path")
        return normalized

    @staticmethod
    def _close(ftp: ImplicitFTP_TLS) -> None:
        try:
            ftp.quit()
        except Exception:
            ftp.close()