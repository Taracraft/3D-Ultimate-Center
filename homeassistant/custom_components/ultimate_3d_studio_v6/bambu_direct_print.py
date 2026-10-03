"""Validated Bambu LAN upload and direct-print helpers for V6."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import ftplib
import io
from pathlib import Path, PurePosixPath
import re
import socket
import ssl
from typing import Any, Callable
from uuid import uuid4
import zipfile

from .bambu_project_archive import safe_project_name
from .gcode_artifact_validation import (
    GCodeValidationError,
    validate_rendered_bambu_gcode,
)

FTP_PORT = 990
FTP_USERNAME = "bblp"
MAX_ARTIFACT_BYTES = 600_000_000
MAX_ARCHIVE_FILES = 10_000
MAX_GCODE_BYTES = 550_000_000
DATA_TLS_SHUTDOWN_TIMEOUT = 2.0
FTPS_ERRORS = (ftplib.Error, OSError, EOFError)
TransferProgressCallback = Callable[[int, int, str], None]
_GENERIC_PROJECT_NAME = re.compile(
    r"^(?:projekt|project|druckplatte|plate|build[ _-]*plate|druckauftrag|print[ _-]*job)[ _-]*\d*$",
    re.IGNORECASE,
)
_TRAILING_PLATE_NAME = re.compile(
    r"[ _-]+druckplatte[ _-]*\d+$",
    re.IGNORECASE,
)


def _report_transfer_progress(
    callback: TransferProgressCallback | None,
    loaded_bytes: int,
    total_bytes: int,
    stage: str,
) -> None:
    if callback is None:
        return
    try:
        callback(
            max(0, min(int(loaded_bytes), int(total_bytes))),
            max(0, int(total_bytes)),
            str(stage),
        )
    except Exception:
        # Fortschrittsbeobachtung darf den sicheren Druckpfad nie beeinflussen.
        pass



class DirectPrintError(RuntimeError):
    """Raised when upload or print preparation is unsafe or invalid."""


@dataclass(frozen=True, slots=True)
class ValidatedPrintArtifact:
    filename: str
    size_bytes: int
    sha256: str
    gcode_path: str
    gcode_size_bytes: int
    validation_report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class UploadedPrintArtifact:
    printer_id: str
    remote_filename: str
    remote_url: str
    size_bytes: int
    sha256: str
    gcode_path: str
    validation_report: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "printer_id": self.printer_id,
            "remote_filename": self.remote_filename,
            "remote_url": self.remote_url,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "gcode_path": self.gcode_path,
            "validation_report": self.validation_report,
        }


class ImplicitFTP_TLS(ftplib.FTP_TLS):
    """Implicit FTPS client adapted to the Bambu server on TCP 990."""

    def connect(
        self,
        host: str = "",
        port: int = 0,
        timeout: float | None = -999,
        source_address=None,
    ):  # type: ignore[override]
        if host:
            self.host = host
        if port:
            self.port = port
        if timeout != -999:
            self.timeout = timeout
        if source_address is not None:
            self.source_address = source_address
        self.sock = socket.create_connection(
            (self.host, self.port),
            self.timeout,
            source_address=self.source_address,
        )
        self.af = self.sock.family
        self.sock = self.context.wrap_socket(
            self.sock,
            server_hostname=self.host,
        )
        self.file = self.sock.makefile("r", encoding=self.encoding)
        self.welcome = self.getresp()
        return self.welcome

    def storbinary(
        self,
        cmd: str,
        fp,
        blocksize: int = 8192,
        callback=None,
        rest=None,
    ):  # type: ignore[override]
        self.voidcmd("TYPE I")
        with self.transfercmd(cmd, rest) as connection:
            while block := fp.read(blocksize):
                connection.sendall(block)
                if callback is not None:
                    callback(block)
            if isinstance(connection, ssl.SSLSocket):
                previous_timeout = connection.gettimeout()
                try:
                    connection.settimeout(DATA_TLS_SHUTDOWN_TIMEOUT)
                    connection.unwrap()
                except FTPS_ERRORS:
                    connection.close()
                finally:
                    try:
                        connection.settimeout(previous_timeout)
                    except FTPS_ERRORS:
                        pass
        return self.voidresp()


def _safe_remote_filename(value: str) -> str:
    raw = Path(value or "Druckauftrag.gcode.3mf").name.strip()
    cleaned = "".join(
        character
        if character.isalnum() or character in "-_. "
        else "_"
        for character in raw
    ).strip(" .")
    if not cleaned:
        cleaned = "Druckauftrag.gcode.3mf"
    lowered = cleaned.casefold()
    if lowered.endswith(".gcode.3mf"):
        stem = cleaned[:-len(".gcode.3mf")]
    elif lowered.endswith(".3mf"):
        stem = cleaned[:-len(".3mf")]
    elif lowered.endswith(".gcode"):
        stem = cleaned[:-len(".gcode")]
    else:
        stem = Path(cleaned).stem
    stem = stem.strip(" .-_") or "Druckauftrag"
    suffix = ".gcode.3mf"
    return f"{stem[:max(1, 180 - len(suffix))].rstrip(' .-_') or 'Druckauftrag'}{suffix}"


def build_remote_3mf_filename(
    project_name: object,
    plate_index: object,
) -> str:
    """Build Projektname_DruckplatteN.3mf without plate placeholders."""
    try:
        normalized_plate_index = int(plate_index)
    except (TypeError, ValueError) as exc:
        raise DirectPrintError("Ungültige Druckplattennummer.") from exc
    if normalized_plate_index < 0 or normalized_plate_index > 255:
        raise DirectPrintError("Ungültige Druckplattennummer.")

    name = safe_project_name(project_name, "Druckauftrag")
    name = _TRAILING_PLATE_NAME.sub("", name).strip(" .-_")
    if not name or _GENERIC_PROJECT_NAME.fullmatch(name):
        raise DirectPrintError(
            "Kein echter Projektname aus Galerie oder Modelldaten verfügbar."
        )
    cleaned = "".join(
        character
        if character.isalnum() or character in "-_. +()"
        else "_"
        for character in name
    )
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip(" .-_")
    suffix = f"_Druckplatte{normalized_plate_index + 1}.3mf"
    maximum_stem = max(1, 180 - len(suffix))
    stem = cleaned[:maximum_stem].rstrip(" .-_") or "Druckauftrag"
    return f"{stem}{suffix}"


def _project_display_name(filename: str) -> str:
    name = Path(filename or "Druckauftrag").name.strip()
    lowered = name.casefold()
    for suffix in (".gcode.3mf", ".3mf", ".gcode"):
        if lowered.endswith(suffix):
            name = name[: -len(suffix)]
            break
    cleaned = "".join(
        character
        if character.isalnum() or character in "-_. +()"
        else "_"
        for character in name
    ).strip(" .-_")
    return (cleaned or "Druckauftrag")[:120]


def validate_gcode_3mf(
    filename: str,
    data: bytes,
    *,
    hardware_limits: dict[str, float] | None = None,
    expected_printer_model: str | None = None,
) -> ValidatedPrintArtifact:
    """Validate archive shape and the complete rendered Bambu machine flow."""
    if not data:
        raise DirectPrintError("Das G-Code-3MF ist leer.")
    if len(data) > MAX_ARTIFACT_BYTES:
        raise DirectPrintError("Das G-Code-3MF überschreitet 600 MB.")
    safe_name = _safe_remote_filename(filename)
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise DirectPrintError(
            "Das Druckartefakt ist kein gültiges 3MF/ZIP-Archiv."
        ) from exc

    with archive:
        infos = archive.infolist()
        if not infos or len(infos) > MAX_ARCHIVE_FILES:
            raise DirectPrintError(
                "Das Druckartefakt enthält eine ungültige Dateianzahl."
            )
        total = 0
        gcode_candidates: list[zipfile.ZipInfo] = []
        preview_paths: list[str] = []
        for info in infos:
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts:
                raise DirectPrintError(
                    f"Unsicherer 3MF-Pfad: {info.filename}"
                )
            total += int(info.file_size)
            if total > MAX_ARTIFACT_BYTES * 3:
                raise DirectPrintError(
                    "Der entpackte 3MF-Inhalt ist unerwartet groß."
                )
            normalized = info.filename.replace("\\", "/").casefold()
            if (
                normalized.startswith("metadata/plate_")
                and normalized.endswith(".gcode")
            ):
                gcode_candidates.append(info)
            if (
                normalized.startswith("metadata/")
                and normalized.endswith(".png")
                and info.file_size > 0
            ):
                preview_paths.append(info.filename.replace("\\", "/"))

        if len(gcode_candidates) != 1:
            raise DirectPrintError(
                "Direktdruck benötigt genau eine eingebettete "
                "Metadata/plate_*.gcode-Datei."
            )
        gcode = gcode_candidates[0]
        if gcode.file_size <= 0 or gcode.file_size > MAX_GCODE_BYTES:
            raise DirectPrintError(
                "Die eingebettete G-Code-Datei hat eine ungültige Größe."
            )
        try:
            with archive.open(gcode) as handle:
                report = validate_rendered_bambu_gcode(handle, hardware_limits=hardware_limits, expected_printer_model=expected_printer_model)
        except GCodeValidationError as exc:
            raise DirectPrintError(
                f"Druckjob nicht freigegeben: {exc}"
            ) from exc
        validation_report = report.as_dict()
        validation_report["preview_paths"] = sorted(preview_paths)
        validation_report["display_preview_available"] = bool(preview_paths)

    return ValidatedPrintArtifact(
        filename=safe_name,
        size_bytes=len(data),
        sha256=sha256(data).hexdigest(),
        gcode_path=gcode.filename.replace("\\", "/"),
        gcode_size_bytes=int(gcode.file_size),
        validation_report=validation_report,
    )


def _ssl_context(tls_insecure: bool) -> ssl.SSLContext:
    if tls_insecure:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    return ssl.create_default_context()


def _close_ftps(
    client: ImplicitFTP_TLS,
    *,
    graceful: bool = True,
) -> None:
    if graceful:
        try:
            client.quit()
            return
        except FTPS_ERRORS:
            pass
    try:
        client.close()
    except FTPS_ERRORS:
        pass


def _connect_ftps(
    *,
    host: str,
    access_code: str,
    tls_insecure: bool,
    timeout: float,
) -> ImplicitFTP_TLS:
    client = ImplicitFTP_TLS(
        context=_ssl_context(tls_insecure),
        timeout=timeout,
    )
    try:
        client.connect(host, FTP_PORT, timeout=timeout)
        client.login(FTP_USERNAME, access_code)
        client.prot_p()
        client.set_pasv(True)
    except FTPS_ERRORS:
        _close_ftps(client, graceful=False)
        raise
    return client


def _remote_file_size(
    *,
    host: str,
    access_code: str,
    filename: str,
    tls_insecure: bool,
) -> int | None:
    client = _connect_ftps(
        host=host,
        access_code=access_code,
        tls_insecure=tls_insecure,
        timeout=20,
    )
    try:
        client.voidcmd("TYPE I")
        value = client.size(filename)
        return None if value is None else int(value)
    finally:
        _close_ftps(client)


def upload_gcode_3mf(
    *,
    host: str,
    access_code: str,
    printer_id: str,
    filename: str,
    data: bytes,
    tls_insecure: bool,
    on_progress: TransferProgressCallback | None = None,
    hardware_limits: dict[str, float] | None = None,
    printer_model: str,
) -> UploadedPrintArtifact:
    """Validate, upload and independently verify one G-code 3MF."""
    if hardware_limits is None:
        raise DirectPrintError("Für das gewählte Druckermodell fehlen geprüfte Hardwaregrenzen.")
    artifact = validate_gcode_3mf(filename, data, hardware_limits=hardware_limits, expected_printer_model=printer_model)
    if not host or not access_code or not printer_id:
        raise DirectPrintError(
            "Drucker-Host, Seriennummer oder Zugangscode fehlt."
        )
    _report_transfer_progress(
        on_progress,
        0,
        artifact.size_bytes,
        "connecting",
    )

    client: ImplicitFTP_TLS | None = None
    upload_error: BaseException | None = None
    uploaded_bytes = 0
    try:
        client = _connect_ftps(
            host=host,
            access_code=access_code,
            tls_insecure=tls_insecure,
            timeout=30,
        )
        def _uploaded(block: bytes) -> None:
            nonlocal uploaded_bytes
            uploaded_bytes = min(
                artifact.size_bytes,
                uploaded_bytes + len(block),
            )
            _report_transfer_progress(
                on_progress,
                uploaded_bytes,
                artifact.size_bytes,
                "uploading",
            )

        if on_progress is None:
            client.storbinary(
                f"STOR {artifact.filename}",
                io.BytesIO(data),
                blocksize=256 * 1024,
            )
        else:
            client.storbinary(
                f"STOR {artifact.filename}",
                io.BytesIO(data),
                blocksize=256 * 1024,
                callback=_uploaded,
            )
    except FTPS_ERRORS as exc:
        upload_error = exc
    finally:
        if client is not None:
            _close_ftps(client, graceful=upload_error is None)

    _report_transfer_progress(
        on_progress,
        uploaded_bytes,
        artifact.size_bytes,
        "verifying",
    )
    try:
        remote_size = _remote_file_size(
            host=host,
            access_code=access_code,
            filename=artifact.filename,
            tls_insecure=tls_insecure,
        )
    except FTPS_ERRORS as verify_error:
        if upload_error is not None:
            raise DirectPrintError(
                "FTPS-Upload konnte nicht bestätigt werden: "
                f"{upload_error}; Remote-Prüfung fehlgeschlagen: "
                f"{verify_error}"
            ) from upload_error
        raise DirectPrintError(
            "FTPS-Remote-Prüfung zum Bambu-Drucker fehlgeschlagen: "
            f"{verify_error}"
        ) from verify_error

    if remote_size is None:
        if upload_error is not None:
            raise DirectPrintError(
                f"FTPS-Upload konnte nicht bestätigt werden: {upload_error}"
            ) from upload_error
        raise DirectPrintError(
            "Der Drucker meldet nach dem Upload keine Dateigröße."
        )
    if remote_size != artifact.size_bytes:
        delete_remote_file(
            host=host,
            access_code=access_code,
            filename=artifact.filename,
            tls_insecure=tls_insecure,
        )
        raise DirectPrintError(
            "FTPS-Größenprüfung fehlgeschlagen: "
            f"lokal {artifact.size_bytes}, remote {remote_size}."
        )

    _report_transfer_progress(
        on_progress,
        artifact.size_bytes,
        artifact.size_bytes,
        "completed",
    )
    return UploadedPrintArtifact(
        printer_id=printer_id,
        remote_filename=artifact.filename,
        remote_url=f"ftp:///{artifact.filename}",
        size_bytes=artifact.size_bytes,
        sha256=artifact.sha256,
        gcode_path=artifact.gcode_path,
        validation_report=artifact.validation_report,
    )


def delete_remote_file(
    *,
    host: str,
    access_code: str,
    filename: str,
    tls_insecure: bool,
) -> bool:
    safe_name = _safe_remote_filename(filename)
    client: ImplicitFTP_TLS | None = None
    try:
        client = _connect_ftps(
            host=host,
            access_code=access_code,
            tls_insecure=tls_insecure,
            timeout=20,
        )
        client.delete(safe_name)
        return True
    except FTPS_ERRORS:
        return False
    finally:
        if client is not None:
            _close_ftps(client)


def build_project_file_command(
    uploaded: UploadedPrintArtifact,
    *,
    use_ams: bool,
    ams_mapping: list[int] | None,
    bed_leveling: bool,
    flow_cali: bool,
    vibration_cali: bool,
    timelapse: bool,
) -> dict[str, Any]:
    mapping = [int(value) for value in (ams_mapping or [])]
    if len(mapping) > 5 or any(value < -1 or value > 255 for value in mapping):
        raise DirectPrintError("Ungültige AMS-Zuordnung.")
    if use_ams:
        if not mapping or len(mapping) > 4 or any(value < 0 for value in mapping):
            raise DirectPrintError(
                "Ungültige AMS-Zuordnung: externe Spule ist für "
                "diesen Auftrag nicht erlaubt."
            )
        markers = uploaded.validation_report.get("markers", {})
        if (
            not markers.get("material_select")
            or not markers.get("material_complete")
        ):
            raise DirectPrintError(
                "Der freigegebene G-Code enthält keinen vollständigen "
                "AMS/BMCU-Materialwechsel."
            )
    sequence_id = uuid4().hex[:16]
    return {
        "print": {
            "sequence_id": sequence_id,
            "command": "project_file",
            "param": uploaded.gcode_path,
            "project_id": "0",
            "profile_id": "0",
            "task_id": "0",
            "subtask_id": "0",
            "subtask_name": _project_display_name(
                uploaded.remote_filename
            ),
            "file": uploaded.remote_filename,
            "url": uploaded.remote_url,
            "md5": "",
            "plate_idx": 0,
            "bed_type": "auto",
            "timelapse": bool(timelapse),
            "bed_leveling": bool(bed_leveling),
            "bed_levelling": bool(bed_leveling),
            "flow_cali": bool(flow_cali),
            "vibration_cali": bool(vibration_cali),
            "layer_inspect": False,
            "use_ams": bool(use_ams),
            "ams_mapping": mapping,
        }
    }
