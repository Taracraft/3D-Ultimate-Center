"""Read-only verification of an existing Studio HACS zip_release artifact.

HACS extracts release ZIPs directly into custom_components/<domain>. Repository
layout and ZIP layout are separate contracts. This verifier never extracts,
builds, installs, imports packaged code, downloads, or publishes anything.
Expected member hashes must come from an independently reviewed source inventory.
"""
from __future__ import annotations

import argparse
import ast
from hashlib import sha256
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile
import zlib

DOMAIN = "ultimate_3d_studio"
ASSETS = ("ultimate-3d-studio.js", "ultimate-3d-studio.css", "ultimate-3d-studio-build.json")
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_ENTRIES = 2000
MAX_METADATA_BYTES = 1024 * 1024
HACS_KEYS = frozenset({"content_in_root", "country", "filename", "hacs", "hide_default_branch",
                       "homeassistant", "persistent_directory", "render_readme", "zip_release", "name"})
REQUIRED = frozenset({"__init__.py", "config_flow.py", "manifest.json", "strings.json",
                      "translations/de.json", "translations/en.json",
                      *("assets/" + name for name in ASSETS)})


class HacsReleaseError(ValueError):
    """The supplied artifact does not satisfy the selected release contract."""


def _json(raw: bytes) -> dict:
    def finite(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise HacsReleaseError("non-finite JSON value")
        return parsed
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise HacsReleaseError("duplicate JSON key")
            result[key] = value
        return result
    try:
        result = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique, parse_float=finite,
                            parse_constant=lambda _x: (_ for _ in ()).throw(
                                HacsReleaseError("non-finite JSON value")))
    except HacsReleaseError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise HacsReleaseError("invalid JSON object") from None
    if not isinstance(result, dict):
        raise HacsReleaseError("JSON object required")
    return result


def _metadata(path: Path) -> dict:
    if path.is_symlink():
        raise HacsReleaseError("linked metadata is not accepted")
    with path.open("rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise HacsReleaseError("regular metadata file required")
        raw = stream.read(MAX_METADATA_BYTES + 1)
    if len(raw) > MAX_METADATA_BYTES:
        raise HacsReleaseError("metadata exceeds size limit")
    return _json(raw)


def _name(name: str, *, directory: bool = False) -> str:
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise HacsReleaseError("unsafe archive member path")
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise HacsReleaseError("unsafe archive member path")
    if name.startswith("/"):
        raise HacsReleaseError("unsafe archive member path")
    while name.startswith("./"):
        name = name[2:]
    if name.startswith("/"):
        raise HacsReleaseError("unsafe archive member path")
    if directory:
        name = name.removesuffix("/")
        if not name:
            return ""
    parts = name.split("/")
    if any(not p or p in (".", "..") or p.endswith((".", " ")) for p in parts):
        raise HacsReleaseError("unsafe archive member path")
    if PurePosixPath(name).is_absolute():
        raise HacsReleaseError("unsafe archive member path")
    return name


def _imports(payloads: dict[str, bytes]) -> int:
    count = 0
    for name, raw in payloads.items():
        if not name.endswith(".py"):
            continue
        try:
            tree = ast.parse(raw.decode("utf-8-sig"))
        except (SyntaxError, UnicodeError, RecursionError):
            raise HacsReleaseError("invalid packaged Python source") from None
        parents = PurePosixPath(name).parent.parts
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            count += 1
            if node.level > len(parents) + 1:
                raise HacsReleaseError("relative import escapes integration")
            prefix = parents[:len(parents) - node.level + 1]
            # `from . import NAME` may import a package attribute or dynamic
            # export, not necessarily a NAME.py module. Verify its package;
            # runtime attribute availability is outside static module closure.
            if node.module is None:
                package = "/".join((*prefix, "__init__.py"))
                if package not in payloads:
                    raise HacsReleaseError("missing relative Python package")
                continue
            modules = [node.module]
            for module in modules:
                relative = "/".join((*prefix, *module.split(".")))
                if relative + ".py" not in payloads and relative + "/__init__.py" not in payloads:
                    raise HacsReleaseError("missing relative Python module")
    return count


def verify_release(archive: Path, hacs: dict, expected_files: dict[str, str], *,
                   expected_version: str, expected_build_id: str,
                   expected_archive_sha256: str) -> dict:
    """Verify externally pinned bytes; success is not installation approval."""
    if not isinstance(hacs, dict) or hacs.get("zip_release") is not True:
        raise HacsReleaseError("zip_release must be explicitly true")
    if not isinstance(hacs.get("name"), str) or not hacs["name"].strip() or hacs.keys() - HACS_KEYS:
        raise HacsReleaseError("invalid HACS repository metadata")
    for key in ("content_in_root", "hide_default_branch", "render_readme"):
        if key in hacs and type(hacs[key]) is not bool:
            raise HacsReleaseError("invalid HACS boolean metadata")
    filename = hacs.get("filename")
    if not isinstance(filename, str) or _name(filename) != filename or "/" in filename or not filename.endswith(".zip"):
        raise HacsReleaseError("safe release filename required")
    if archive.name != filename:
        raise HacsReleaseError("archive filename does not match hacs.json")
    if not isinstance(expected_version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?", expected_version):
        raise HacsReleaseError("invalid expected version")
    if not isinstance(expected_build_id, str) or not re.fullmatch(r"[a-f0-9]{10}", expected_build_id):
        raise HacsReleaseError("invalid expected build identity")
    if not isinstance(expected_archive_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_archive_sha256):
        raise HacsReleaseError("archive must have an external SHA-256 pin")
    if not isinstance(expected_files, dict) or not REQUIRED <= expected_files.keys():
        raise HacsReleaseError("reviewed member inventory missing required files")
    for name, digest in expected_files.items():
        if _name(name) != name or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise HacsReleaseError("invalid reviewed member inventory")
    if archive.is_symlink():
        raise HacsReleaseError("linked archive is not accepted")
    try:
        with archive.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_ARCHIVE_BYTES:
                raise HacsReleaseError("archive size or file type rejected")
            digest = sha256()
            remaining = before.st_size
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise HacsReleaseError("archive changed during hashing")
                digest.update(chunk)
                remaining -= len(chunk)
            if stream.read(1):
                raise HacsReleaseError("archive grew during hashing")
            if digest.hexdigest() != expected_archive_sha256:
                raise HacsReleaseError("archive differs from external SHA-256 pin")
            stream.seek(0)
            payloads = {}
            seen = set()
            directory_names = set()
            total = 0
            with zipfile.ZipFile(stream) as zf:
                members = zf.infolist()
                if len(members) > MAX_ENTRIES:
                    raise HacsReleaseError("too many archive members")
                for member in members:
                    name = _name(member.filename, directory=member.is_dir())
                    if member.orig_filename != member.filename:
                        raise HacsReleaseError("ambiguous archive member name")
                    key = name.casefold()
                    if key in seen:
                        raise HacsReleaseError("duplicate or aliased archive member")
                    seen.add(key)
                    mode = member.external_attr >> 16
                    if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR) or member.flag_bits & 1:
                        raise HacsReleaseError("linked, special or encrypted archive member")
                    if member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                        raise HacsReleaseError("unsupported archive compression")
                    if member.is_dir():
                        if stat.S_IFMT(mode) == stat.S_IFREG or member.file_size:
                            raise HacsReleaseError("inconsistent archive directory")
                        directory_names.add(name)
                        continue
                    if stat.S_IFMT(mode) == stat.S_IFDIR:
                        raise HacsReleaseError("inconsistent archive file")
                    if name.startswith("custom_components/") or name.startswith(DOMAIN + "/"):
                        raise HacsReleaseError("release ZIP must use integration-root layout")
                    if name not in expected_files:
                        raise HacsReleaseError("unexpected archive file")
                    if name.startswith("assets/"):
                        if name not in {"assets/" + a for a in ASSETS}:
                            raise HacsReleaseError("unexpected frontend asset")
                    elif PurePosixPath(name).suffix not in (".py", ".json", ".yaml", ".yml") or any(p.startswith(".") or p == "__pycache__" for p in PurePosixPath(name).parts):
                        raise HacsReleaseError("forbidden integration file")
                    if not 0 <= member.file_size <= MAX_MEMBER_BYTES:
                        raise HacsReleaseError("archive member exceeds size limit")
                    total += member.file_size
                    if total > MAX_TOTAL_BYTES:
                        raise HacsReleaseError("archive exceeds expanded size limit")
                    with zf.open(member) as item:
                        raw = item.read(MAX_MEMBER_BYTES + 1)
                    if len(raw) != member.file_size or len(raw) > MAX_MEMBER_BYTES:
                        raise HacsReleaseError("archive member size mismatch")
                    if sha256(raw).hexdigest() != expected_files[name]:
                        raise HacsReleaseError("member differs from reviewed source inventory")
                    payloads[name] = raw
            if payloads.keys() != expected_files.keys():
                raise HacsReleaseError("archive misses reviewed files")
            allowed_dirs = {str(p) for name in payloads for p in PurePosixPath(name).parents if str(p) != "."}
            if not directory_names <= allowed_dirs | {""}:
                raise HacsReleaseError("unexpected archive directory")
            after = os.fstat(stream.fileno())
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise HacsReleaseError("archive changed during verification")
    except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, zlib.error):
        raise HacsReleaseError("archive could not be verified") from None
    manifest = _json(payloads["manifest.json"])
    build = _json(payloads["assets/" + ASSETS[2]])
    if not isinstance(manifest.get("name"), str) or not manifest["name"].strip() or not isinstance(manifest.get("codeowners"), list) or not all(isinstance(owner, str) and owner for owner in manifest["codeowners"]):
        raise HacsReleaseError("required integration manifest fields missing")
    from urllib.parse import urlsplit
    for key in ("documentation", "issue_tracker"):
        if not isinstance(manifest.get(key), str):
            raise HacsReleaseError("invalid integration documentation URL")
        try:
            parsed = urlsplit(manifest.get(key, ""))
            if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
                raise HacsReleaseError("invalid integration documentation URL")
        except (TypeError, ValueError):
            raise HacsReleaseError("invalid integration documentation URL") from None
    if manifest.get("domain") != DOMAIN or manifest.get("version") != expected_version or manifest.get("config_flow") is not True:
        raise HacsReleaseError("integration manifest identity mismatch")
    if build.get("version") != expected_version or build.get("build_id") != expected_build_id:
        raise HacsReleaseError("frontend build identity mismatch")
    for asset, meta in ((ASSETS[0], build), (ASSETS[1], build.get("css"))):
        if not isinstance(meta, dict):
            raise HacsReleaseError("frontend asset metadata missing")
        raw = payloads["assets/" + asset]
        if type(meta.get("size_bytes")) is not int or meta["size_bytes"] != len(raw) or meta.get("sha256") != sha256(raw).hexdigest():
            raise HacsReleaseError("frontend asset integrity mismatch")
    for name, raw in payloads.items():
        if name.endswith(".json"):
            _json(raw)
    return {"integration": DOMAIN, "version": expected_version, "build_id": expected_build_id,
            "archive_sha256": expected_archive_sha256, "files": len(payloads),
            "expanded_bytes": total, "relative_imports_verified": _imports(payloads),
            "artifact_contract_verified": True, "installation_verified": False,
            "repository_structure_verified": False,
            "publication_approved": False, "product_release_complete": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--hacs-json", type=Path, required=True)
    parser.add_argument("--expected-files-json", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    try:
        result = verify_release(args.archive, _metadata(args.hacs_json),
                                _metadata(args.expected_files_json),
                                expected_version=args.version, expected_build_id=args.build_id,
                                expected_archive_sha256=args.sha256)
    except (HacsReleaseError, OSError):
        print(json.dumps({"artifact_contract_verified": False, "error": "hacs_release_contract_rejected"}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
