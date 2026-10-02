"""Short-lived one-time authorization and transfer records for V6 direct printing."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from threading import RLock
from time import monotonic
from typing import Any

from homeassistant.core import HomeAssistant

from .bambu_direct_print import UploadedPrintArtifact
from .const import DOMAIN

DATA_DIRECT_PRINT_RUNTIME = "direct_print_runtime"
TOKEN_TTL = timedelta(minutes=10)
TRANSFER_TTL = timedelta(minutes=30)
_TRANSFER_STAGE_LABELS = {
    "preparing": "Druckdatei wird vom Slicing Server geladen",
    "connecting": "Sichere FTPS-Verbindung zum Drucker wird aufgebaut",
    "uploading": "Druckjob wird per Bambu LAN an den Drucker übertragen",
    "verifying": "Übertragene Dateigröße und SHA-256 werden geprüft",
    "completed": "Druckjob vollständig übertragen und verifiziert",
    "error": "Übertragung fehlgeschlagen",
}


class DirectPrintAuthorizationError(RuntimeError):
    """Raised when a prepared direct-print authorization is invalid or expired."""


@dataclass(slots=True)
class PreparedDirectPrint:
    token: str
    job_id: str
    printer_id: str
    uploaded: UploadedPrintArtifact
    created_at: datetime
    expires_at: datetime
    used: bool = False

    def public(self, *, printer_name: str, printer_state: str) -> dict[str, Any]:
        return {
            "token": self.token,
            "job_id": self.job_id,
            "printer_id": self.printer_id,
            "printer_name": printer_name,
            "printer_state": printer_state,
            "remote_filename": self.uploaded.remote_filename,
            "size_bytes": self.uploaded.size_bytes,
            "sha256": self.uploaded.sha256,
            "gcode_path": self.uploaded.gcode_path,
            "validation_report": self.uploaded.validation_report,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "requires_final_confirmation": True,
        }


@dataclass(slots=True)
class DirectPrintTransfer:
    job_id: str
    printer_id: str
    printer_name: str
    filename: str
    loaded_bytes: int
    total_bytes: int
    stage: str
    active: bool
    status: str
    error: str
    started_at: datetime
    updated_at: datetime
    expires_at: datetime
    started_monotonic: float

    def public(self) -> dict[str, Any]:
        elapsed_seconds = max(0.0, monotonic() - self.started_monotonic)
        rate = (
            self.loaded_bytes / elapsed_seconds
            if self.loaded_bytes > 0 and elapsed_seconds >= 0.05
            else 0.0
        )
        progress = (
            min(100.0, max(0.0, self.loaded_bytes / self.total_bytes * 100.0))
            if self.total_bytes > 0
            else 0.0
        )
        eta = (
            max(0.0, (self.total_bytes - self.loaded_bytes) / rate)
            if self.active
            and rate > 0
            and self.total_bytes > self.loaded_bytes
            else None
        )
        return {
            "job_id": self.job_id,
            "printer_id": self.printer_id,
            "printer_name": self.printer_name,
            "filename": self.filename,
            "loaded_bytes": self.loaded_bytes,
            "total_bytes": self.total_bytes,
            "progress": progress,
            "rate_bytes_per_second": rate,
            "eta_seconds": eta,
            "elapsed_seconds": elapsed_seconds,
            "stage": self.stage,
            "stage_label": _TRANSFER_STAGE_LABELS.get(
                self.stage,
                "Druckjob wird verarbeitet",
            ),
            "active": self.active,
            "status": self.status,
            "error": self.error or None,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class DirectPrintRuntime:
    def __init__(self) -> None:
        self._items: dict[str, PreparedDirectPrint] = {}
        self._transfers: dict[tuple[str, str], DirectPrintTransfer] = {}
        self._lock = RLock()

    def _purge_locked(self) -> None:
        now = datetime.now(UTC)
        self._items = {
            token: item
            for token, item in self._items.items()
            if not item.used and item.expires_at > now
        }
        self._transfers = {
            key: item
            for key, item in self._transfers.items()
            if item.expires_at > now
        }

    def create(self, *, job_id: str, printer_id: str, uploaded: UploadedPrintArtifact) -> PreparedDirectPrint:
        with self._lock:
            self._purge_locked()
            now = datetime.now(UTC)
            token = token_urlsafe(32)
            item = PreparedDirectPrint(
                token=token,
                job_id=job_id,
                printer_id=printer_id,
                uploaded=uploaded,
                created_at=now,
                expires_at=now + TOKEN_TTL,
            )
            self._items[token] = item
            return item

    def consume(self, token: str, *, job_id: str, printer_id: str, expected_sha256: str) -> PreparedDirectPrint:
        with self._lock:
            self._purge_locked()
            item = self._items.get(token)
            if item is None:
                raise DirectPrintAuthorizationError("Druckfreigabe ist ungültig oder abgelaufen.")
            if item.used:
                raise DirectPrintAuthorizationError("Druckfreigabe wurde bereits verwendet.")
            if item.job_id != job_id or item.printer_id != printer_id:
                raise DirectPrintAuthorizationError("Druckfreigabe gehört zu einem anderen Auftrag oder Drucker.")
            if item.uploaded.sha256 != expected_sha256:
                raise DirectPrintAuthorizationError("Artefakt-Prüfsumme stimmt nicht mit der Druckfreigabe überein.")
            item.used = True
            self._items.pop(token, None)
            return item

    def discard(self, token: str) -> PreparedDirectPrint | None:
        with self._lock:
            self._purge_locked()
            item = self._items.pop(token, None)
            if item is not None:
                item.used = True
            return item

    def begin_transfer(
        self,
        *,
        job_id: str,
        printer_id: str,
        printer_name: str,
        filename: str,
        total_bytes: int,
    ) -> DirectPrintTransfer:
        with self._lock:
            self._purge_locked()
            now = datetime.now(UTC)
            item = DirectPrintTransfer(
                job_id=job_id,
                printer_id=printer_id,
                printer_name=printer_name,
                filename=filename,
                loaded_bytes=0,
                total_bytes=max(0, int(total_bytes)),
                stage="preparing",
                active=True,
                status="running",
                error="",
                started_at=now,
                updated_at=now,
                expires_at=now + TRANSFER_TTL,
                started_monotonic=monotonic(),
            )
            self._transfers[(job_id, printer_id)] = item
            return item

    def update_transfer(
        self,
        *,
        job_id: str,
        printer_id: str,
        loaded_bytes: int,
        total_bytes: int,
        stage: str,
    ) -> DirectPrintTransfer | None:
        with self._lock:
            self._purge_locked()
            item = self._transfers.get((job_id, printer_id))
            if item is None:
                return None
            item.total_bytes = max(
                item.total_bytes,
                max(0, int(total_bytes)),
            )
            bounded_loaded = max(0, int(loaded_bytes))
            if item.total_bytes > 0:
                bounded_loaded = min(bounded_loaded, item.total_bytes)
            item.loaded_bytes = max(item.loaded_bytes, bounded_loaded)
            item.stage = str(stage or item.stage)
            item.updated_at = datetime.now(UTC)
            item.expires_at = item.updated_at + TRANSFER_TTL
            return item

    def complete_transfer(
        self,
        *,
        job_id: str,
        printer_id: str,
    ) -> DirectPrintTransfer | None:
        with self._lock:
            item = self._transfers.get((job_id, printer_id))
            if item is None:
                return None
            item.loaded_bytes = max(item.loaded_bytes, item.total_bytes)
            item.stage = "completed"
            item.active = False
            item.status = "success"
            item.error = ""
            item.updated_at = datetime.now(UTC)
            item.expires_at = item.updated_at + TRANSFER_TTL
            return item

    def fail_transfer(
        self,
        *,
        job_id: str,
        printer_id: str,
        error: str,
    ) -> DirectPrintTransfer | None:
        with self._lock:
            item = self._transfers.get((job_id, printer_id))
            if item is None:
                return None
            item.stage = "error"
            item.active = False
            item.status = "error"
            item.error = str(error or "Unbekannter Übertragungsfehler")
            item.updated_at = datetime.now(UTC)
            item.expires_at = item.updated_at + TRANSFER_TTL
            return item

    def transfer_status(
        self,
        *,
        job_id: str,
        printer_id: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            self._purge_locked()
            item = self._transfers.get((job_id, printer_id))
            return item.public() if item is not None else None


def get_direct_print_runtime(hass: HomeAssistant) -> DirectPrintRuntime:
    data = hass.data.setdefault(DOMAIN, {})
    runtime = data.get(DATA_DIRECT_PRINT_RUNTIME)
    if not isinstance(runtime, DirectPrintRuntime):
        runtime = DirectPrintRuntime()
        data[DATA_DIRECT_PRINT_RUNTIME] = runtime
    return runtime