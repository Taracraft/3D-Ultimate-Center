"""Bounded engine package preparation; no activation or engine execution.

Internal API for a trusted, reviewed catalog, never user-supplied release data.
The caller owns a private, stable parent directory and serializes activation.
See PACKAGE_STAGING.md for formats, limits and remaining installer work.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import http.client
import json
import lzma
import os
from pathlib import Path
import shutil
import ssl
import stat
import struct
import tarfile
import tempfile
import time
from urllib.parse import urlsplit
import zipfile
import zlib

from engine_catalog import Artifact, CatalogError, Release, _release, verify_artifact

CHUNK = 65536
MAX_EXPANDED = 2 * 1024**3
MAX_MEMBER = 512 * 1024**2
MAX_ENTRIES = 100000
MAX_ZIP_DIRECTORY = 16 * 1024**2
LZMA_MEMORY = 256 * 1024**2
IO_TIMEOUT = 20
OPERATION_SECONDS = 1800


class StagingError(ValueError):
    """Stable code only; do not expose remote responses or local paths."""


class _Guard:
    def __init__(self, cancelled):
        self.cancelled = cancelled
        self.deadline = time.monotonic() + OPERATION_SECONDS

    def check(self):
        if self.cancelled is not None and self.cancelled():
            raise StagingError("cancelled")
        if time.monotonic() > self.deadline:
            raise StagingError("deadline_exceeded")


def _checked_release(release):
    if type(release) is not Release:
        raise CatalogError("invalid_release")
    data = asdict(release)
    data["system"] = "linux"
    for artifact in data["artifacts"]:
        artifact["files"] = list(artifact["files"])
        for row in artifact["files"]:
            if row.get("archive_path") is None:
                row.pop("archive_path", None)
    data["artifacts"] = list(data["artifacts"])
    return _release(data)


def _private_parent(parent):
    parent = Path(parent).absolute()
    for item in (parent, *parent.parents):
        if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
            raise StagingError("unsafe_parent")
    if not parent.is_dir():
        raise StagingError("missing_parent")
    if os.name != "nt":
        info = parent.stat()
        if info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise StagingError("parent_not_private")
    return parent


def _regular(path):
    path = Path(path)
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise StagingError("unsafe_archive")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                         | getattr(os, "O_BINARY", 0))
    stream = os.fdopen(descriptor, "rb")
    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
        stream.close()
        raise StagingError("unsafe_archive")
    return stream


def _copy_checked(source, target, size, expected, guard, *, read=None):
    digest = hashlib.sha256()
    remaining = size
    reader = read or source.read
    while remaining:
        guard.check()
        chunk = reader(min(CHUNK, remaining))
        if type(chunk) is not bytes or not chunk or len(chunk) > remaining:
            raise StagingError("file_size_mismatch")
        target.write(chunk)
        digest.update(chunk)
        remaining -= len(chunk)
    guard.check()
    if digest.hexdigest() != expected:
        raise StagingError("file_digest_mismatch")


def _download(artifact, target, guard):
    # No proxy environment, cookies, credentials or redirect-following handlers.
    parts = urlsplit(artifact.url)
    context = ssl.create_default_context()
    context.set_alpn_protocols(["http/1.1"])
    connection = http.client.HTTPSConnection(parts.hostname, 443,
                                             timeout=IO_TIMEOUT, context=context)
    try:
        guard.check()
        connection.request("GET", parts.path, headers={
            "Accept-Encoding": "identity", "User-Agent": "Ultimate-Studio-Installer",
            "Connection": "close",
        })
        response = connection.getresponse()
        if 300 <= response.status < 400:
            raise StagingError("redirect_denied")
        if response.status != 200:
            raise StagingError("download_status")
        headers = {}
        for key, value in response.getheaders():
            key = key.lower()
            if key in {"content-length", "transfer-encoding", "content-encoding"}:
                if key in headers:
                    raise StagingError("ambiguous_download_headers")
                headers[key] = value.strip().lower()
        if headers.get("content-encoding", "identity") != "identity":
            raise StagingError("download_encoding")
        length = headers.get("content-length")
        transfer = headers.get("transfer-encoding")
        if transfer and (transfer != "chunked" or length is not None):
            raise StagingError("ambiguous_download_headers")
        if length is not None and (not length.isascii() or not length.isdecimal()
                                   or int(length) != artifact.size_bytes):
            raise StagingError("download_size")
        with target.open("xb") as output:
            _copy_checked(response, output, artifact.size_bytes, artifact.sha256,
                          guard, read=response.read1)
            if response.read1(1):
                raise StagingError("download_size")
            guard.check()
            output.flush()
            os.fsync(output.fileno())
    except (OSError, http.client.HTTPException, ValueError) as exc:
        if isinstance(exc, StagingError):
            raise
        raise StagingError("download_failed") from None
    finally:
        connection.close()


class _Slice:
    def __init__(self, stream, size):
        self.stream = stream
        self.remaining = size

    def read(self, count):
        data = self.stream.read(min(count, self.remaining))
        self.remaining -= len(data)
        return data


def _deb_data(stream):
    if stream.read(8) != b"!<arch>\n":
        raise StagingError("invalid_deb")
    members = []
    stream.seek(0, 2)
    total = stream.tell()
    stream.seek(8)
    while stream.tell() < total:
        header = stream.read(60)
        if len(header) != 60 or header[58:] != b"\x60\n":
            raise StagingError("invalid_deb")
        name = header[:16].decode("ascii").strip().removesuffix("/")
        size_text = header[48:58].decode("ascii").strip()
        if not size_text.isdecimal():
            raise StagingError("invalid_deb")
        size = int(size_text)
        offset = stream.tell()
        if offset + size + (size % 2) > total or len(members) >= 3:
            raise StagingError("invalid_deb")
        members.append((name, offset, size))
        stream.seek(size, 1)
        if size % 2 and stream.read(1) != b"\n":
            raise StagingError("invalid_deb")
    if (len(members) != 3 or members[0][0] != "debian-binary"
            or members[0][2] != 4
            or members[1][0] not in {"control.tar", "control.tar.gz", "control.tar.xz"}
            or members[2][0] not in {"data.tar", "data.tar.gz", "data.tar.xz"}):
        raise StagingError("unsupported_deb")
    stream.seek(members[0][1])
    if stream.read(4) != b"2.0\n":
        raise StagingError("unsupported_deb")
    name, offset, size = members[2]
    stream.seek(offset)
    return _Slice(stream, size), name.removeprefix("data.")


def _expand(source, form, target, guard):
    # Bounded streaming decompression, including an explicit XZ memory budget.
    if form == "tar":
        decoder = None
    elif form == "tar.xz":
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=LZMA_MEMORY)
    elif form == "tar.gz":
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    else:
        raise StagingError("unsupported_compression")
    total = 0
    pending = b""
    with target.open("xb") as output:
        while True:
            guard.check()
            if decoder is None:
                data = source.read(CHUNK)
                if not data:
                    break
            else:
                if form == "tar.xz":
                    chunk = source.read(CHUNK) if decoder.needs_input else b""
                    needs_input = decoder.needs_input
                else:
                    chunk = pending or source.read(CHUNK)
                    needs_input = not pending
                if needs_input and not chunk:
                    raise StagingError("truncated_compression")
                data = decoder.decompress(chunk, max_length=CHUNK)
                if form == "tar.gz":
                    pending = decoder.unconsumed_tail
            total += len(data)
            if total > MAX_EXPANDED:
                raise StagingError("expanded_limit")
            output.write(data)
            if decoder is not None and decoder.eof:
                if decoder.unused_data or source.read(1):
                    raise StagingError("trailing_compression")
                break


def _member_path(name, *, directory=False):
    if name.startswith("./"):
        name = name[2:]
    if directory:
        name = name.removesuffix("/")
    if name in {"", "."} and directory:
        return ""
    if (not name or len(name) > 512 or name.startswith("/")
            or any(ord(c) < 32 for c in name) or any(c in name for c in "\\:\x00")
            or any(part in {"", ".", ".."} for part in name.split("/"))):
        raise StagingError("unsafe_member_path")
    return name


def _target_contract(files):
    names = {}
    for spec in files:
        # Linux target paths must also be representable safely on Windows.
        for part in spec.path.split("/"):
            if (any(c in part for c in '<>"|*') or
                    part.split(".")[0].upper() in
                    {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                     *(f"LPT{i}" for i in range(1, 10))}):
                raise StagingError("unsafe_target_path")
        parts = spec.path.split("/")
        for i in range(1, len(parts) + 1):
            path = "/".join(parts[:i])
            key = path.casefold()
            kind = "file" if i == len(parts) else "directory"
            if key in names and names[key] != (path, kind):
                raise StagingError("conflicting_targets")
            names[key] = (path, kind)


class _Selection:
    def __init__(self, artifact, root, guard):
        self.specs = {f.archive_path or f.path: f for f in artifact.files}
        self.root = root
        self.guard = guard
        self.seen = set()
        self.found = set()
        self.total = 0
        self.count = 0

    def entry(self, name, size, kind, source):
        self.guard.check()
        self.count += 1
        self.total += size
        if self.count > MAX_ENTRIES or size < 0 or size > MAX_MEMBER or self.total > MAX_EXPANDED:
            raise StagingError("archive_limit")
        name = _member_path(name, directory=kind == "directory")
        if not name:
            return
        if name in self.seen:
            raise StagingError("duplicate_member")
        self.seen.add(name)
        spec = self.specs.get(name)
        if kind == "special":
            raise StagingError("special_member")
        # Unselected regular data and links are never materialized or followed.
        if spec is None:
            return
        if kind != "file":
            raise StagingError("selected_not_regular")
        if size != spec.size_bytes:
            raise StagingError("file_size_mismatch")
        target = self.root / spec.path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            _copy_checked(source, output, size, spec.sha256, self.guard)
        target.chmod(0o755 if spec.executable else 0o644)
        self.found.add(name)

    def finish(self):
        if self.found != set(self.specs):
            raise StagingError("manifest_file_missing")


def _extract_tar(path, selection):
    # Parse bounded POSIX headers and GNU long names directly: no extractall,
    # PAX/sparse handling, implicit link resolution or archive-controlled chmod.
    with path.open("rb") as stream:
        total = path.stat().st_size
        pending_name = None
        headers = 0
        while True:
            selection.guard.check()
            header = stream.read(512)
            if len(header) != 512:
                raise StagingError("truncated_tar")
            if header == bytes(512):
                if pending_name is not None:
                    raise StagingError("dangling_long_name")
                if stream.read(512) != bytes(512):
                    raise StagingError("invalid_tar_end")
                while chunk := stream.read(CHUNK):
                    selection.guard.check()
                    if any(chunk):
                        raise StagingError("trailing_tar")
                break
            headers += 1
            if headers > MAX_ENTRIES:
                raise StagingError("archive_limit")
            info = tarfile.TarInfo.frombuf(header, "utf-8", "strict")
            if info.type == tarfile.GNUTYPE_LONGNAME:
                if pending_name is not None or not 1 <= info.size <= 1024:
                    raise StagingError("invalid_long_name")
                data = stream.read(info.size)
                if len(data) != info.size or not data.endswith(b"\x00") or b"\x00" in data[:-1]:
                    raise StagingError("invalid_long_name")
                pending_name = data[:-1].decode("utf-8", "strict")
                stream.seek((-info.size) % 512, 1)
                continue
            if pending_name is not None:
                info.name = pending_name
                pending_name = None
            kind = ("file" if info.type in {tarfile.REGTYPE, tarfile.AREGTYPE}
                    else "directory" if info.isdir()
                    else "link" if info.issym() or info.islnk() else "special")
            offset = stream.tell()
            padded = (info.size + 511) // 512 * 512
            if info.size < 0 or offset + padded > total:
                raise StagingError("truncated_tar")
            if kind != "file" and info.size != 0:
                raise StagingError("invalid_tar_entry")
            selection.entry(info.name, info.size, kind, _Slice(stream, info.size))
            stream.seek(offset + padded)


def _extract_zip(path, selection):
    # Bound the central directory before ZipFile allocates its metadata.
    with path.open("rb") as stream:
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(max(0, size - 65557))
        tail = stream.read(65557)
    index = tail.rfind(b"PK\x05\x06")
    if index < 0 or index + 22 > len(tail):
        raise StagingError("invalid_zip")
    fields = struct.unpack("<4s4H2LH", tail[index:index + 22])
    _, disk, directory_disk, on_disk, count, directory_size, offset, comment = fields
    end = size - len(tail) + index
    if (disk or directory_disk or on_disk != count or count == 65535
            or count > MAX_ENTRIES or directory_size > MAX_ZIP_DIRECTORY
            or offset + directory_size != end or index + 22 + comment != len(tail)):
        raise StagingError("unsupported_zip")
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist()) != count:
            raise StagingError("invalid_zip")
        for info in archive.infolist():
            mode = info.external_attr >> 16
            kind = ("directory" if info.is_dir() else "link" if stat.S_ISLNK(mode)
                    else "file" if stat.S_IFMT(mode) in {0, stat.S_IFREG}
                    else "special")
            if info.flag_bits & 1 or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                raise StagingError("unsupported_zip")
            name = _member_path(info.filename, directory=kind == "directory")
            if name in selection.specs and kind == "file":
                with archive.open(info) as stream:
                    selection.entry(name, info.file_size, kind, stream)
                    if stream.read(1):
                        raise StagingError("file_size_mismatch")
            else:
                selection.entry(name, info.file_size, kind, None)


def prepare_release(release: Release, parent: Path, *, archives=None, cancelled=None) -> Path:
    """Prepare an isolated candidate and return its private work directory.

    archives is an optional exact artifact-ID -> local verified-cache path mapping.
    Without it, download from catalog origins using verified TLS and no redirects.
    The returned payload/<engine> is NOT active. No daemon, engine or script runs.
    The caller must protect the parent against concurrent/privileged mutation,
    validate persistent storage and recheck the manifest immediately at activation.
    Errors clean only this invocation's directory. Hard kills may leave an orphan;
    absence of READY.json means it must never be activated.
    """
    release = _checked_release(release)
    _target_contract(tuple(f for a in release.artifacts for f in a.files))
    parent = _private_parent(parent)
    if archives is not None and (not isinstance(archives, dict)
                                or set(archives) != {a.id for a in release.artifacts}):
        raise StagingError("invalid_cache_mapping")
    guard = _Guard(cancelled)
    guard.check()
    work = Path(tempfile.mkdtemp(prefix=".engine-stage-", dir=parent))
    complete = False
    try:
        payload = work / "payload" / release.engine
        payload.mkdir(parents=True)
        for artifact in release.artifacts:
            guard.check()
            archive_path = work / (artifact.id + ".archive")
            if archives is None:
                _download(artifact, archive_path, guard)
            else:
                with _regular(archives[artifact.id]) as source, archive_path.open("xb") as output:
                    _copy_checked(source, output, artifact.size_bytes, artifact.sha256, guard)
                    if source.read(1):
                        raise StagingError("archive_size_mismatch")
            with archive_path.open("rb") as source:
                verify_artifact(source, artifact)
            selection = _Selection(artifact, payload, guard)
            if artifact.format == "zip":
                _extract_zip(archive_path, selection)
            else:
                expanded = work / (artifact.id + ".tar")
                with archive_path.open("rb") as source:
                    stream, form = (_deb_data(source) if artifact.format == "deb"
                                    else (source, artifact.format))
                    _expand(stream, form, expanded, guard)
                _extract_tar(expanded, selection)
                expanded.unlink()
            selection.finish()
            archive_path.unlink()
        guard.check()
        receipt = {"schema": 1, "state": "prepared", "release": asdict(release),
                   "engine_executed": False, "activated": False}
        with (work / "READY.json").open("x", encoding="utf-8", newline="\n") as output:
            json.dump(receipt, output, sort_keys=True, separators=(",", ":"))
            output.flush()
            os.fsync(output.fileno())
        complete = True
        return work
    except (OSError, ValueError, EOFError, tarfile.TarError, zipfile.BadZipFile,
            lzma.LZMAError, zlib.error) as exc:
        if isinstance(exc, (StagingError, CatalogError)):
            raise
        raise StagingError("staging_failed") from None
    finally:
        if not complete:
            shutil.rmtree(work)
