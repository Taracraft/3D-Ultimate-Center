"""Strict, offline installer catalog contract. See ENGINE_CATALOG.md and LICENSE.

This module neither downloads nor executes an engine. Only the shipped, trusted
catalog may be supplied by the future installer; user requests select IDs only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import BinaryIO
from urllib.parse import urlsplit

MAX_CATALOG_BYTES = 4 * 1024 * 1024
MAX_ARTIFACT_BYTES = 2 * 1024**3
MAX_INSTALLED_BYTES = 8 * 1024**3
MAX_FILES = 100000
ENTRYPOINTS = {
    "bambu_studio": "bin/bambu-studio",
    "prusaslicer": "bin/prusa-slicer",
    "curaengine": "bin/CuraEngine",
}
UPSTREAMS = {
    "bambu_studio": "https://github.com/bambulab/BambuStudio/",
    "prusaslicer": "https://github.com/prusa3d/PrusaSlicer/",
    "curaengine": "https://github.com/Ultimaker/",
}
DOWNLOAD_PREFIXES = (
    "https://github.com/Taracraft/3D-Ultimate-Center/releases/download/",
    "https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/",
    "https://github.com/bambulab/BambuStudio/releases/download/",
    "https://github.com/prusa3d/PrusaSlicer/releases/download/",
    "https://github.com/Ultimaker/CuraEngine/releases/download/",
    "https://github.com/Ultimaker/Cura/releases/download/",
    "https://deb.debian.org/debian/pool/",
)
ROLES = frozenset(("engine", "runtime", "resources", "profiles", "license"))


class CatalogError(ValueError):
    """Stable error code; never include raw URLs or supplied catalog values."""


@dataclass(frozen=True)
class FileSpec:
    path: str
    sha256: str
    size_bytes: int
    role: str
    executable: bool
    archive_path: str | None = None


@dataclass(frozen=True)
class SourceArchive:
    kind: str
    url: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class SourceComponent:
    id: str
    package: str
    component_version: str
    license: str
    source_revision: str
    archives: tuple[SourceArchive, ...]
    files: tuple[str, ...]
    notices: tuple[str, ...]


@dataclass(frozen=True)
class Artifact:
    id: str
    component_version: str
    url: str
    sha256: str
    size_bytes: int
    format: str
    license: str
    source_url: str
    source_revision: str
    files: tuple[FileSpec, ...]
    source_components: tuple[SourceComponent, ...] = ()


@dataclass(frozen=True)
class Release:
    engine: str
    version: str
    architecture: str
    artifacts: tuple[Artifact, ...]

    @property
    def download_bytes(self) -> int:
        return sum(a.size_bytes for a in self.artifacts)

    @property
    def installed_bytes(self) -> int:
        return sum(f.size_bytes for a in self.artifacts for f in a.files)


def release_document(release: Release) -> dict:
    """Internal receipt record; absent new metadata preserves legacy identities."""
    if type(release) is not Release:
        raise CatalogError("invalid_release")
    data = json.loads(json.dumps(asdict(release), allow_nan=False))
    for artifact in data["artifacts"]:
        if not artifact.get("source_components"):
            artifact.pop("source_components", None)
    return data


def catalog_release_document(release: Release) -> dict:
    """Validator-compatible release record for engine_catalog.json."""
    receipt = release_document(release)
    data = {
        "engine": receipt["engine"],
        "version": receipt["version"],
        "system": "linux",
        "architecture": receipt["architecture"],
        "artifacts": receipt["artifacts"],
    }
    for artifact in data["artifacts"]:
        for file_spec in artifact["files"]:
            if file_spec.get("archive_path") is None:
                file_spec.pop("archive_path", None)
    return data


@dataclass(frozen=True)
class Catalog:
    releases: tuple[Release, ...]
    pending: tuple[str, ...]

    def select(self, engine: str, *, system: str, architecture: str) -> Release:
        if type(engine) is not str or engine not in ENTRYPOINTS:
            raise CatalogError("unknown_engine")
        if system != "linux" or architecture != "amd64":
            raise CatalogError("unsupported_platform")
        for release in self.releases:
            if release.engine == engine and release.architecture == architecture:
                return release
        raise CatalogError("engine_not_approved")


def _keys(value: object, names: str) -> dict:
    if type(value) is not dict or set(value) != set(names.split()):
        raise CatalogError("invalid_fields")
    return value


def _text(value: object, *, maximum: int = 160) -> str:
    if (type(value) is not str or not value or len(value) > maximum
            or value != value.strip() or any(ord(c) < 32 or ord(c) > 126 for c in value)):
        raise CatalogError("invalid_text")
    return value


def _digest(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise CatalogError("invalid_digest")
    return value


def _number(value: object, maximum: int, *, minimum: int = 1) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise CatalogError("invalid_size")
    return value


def _version(value: object) -> str:
    value = _text(value)
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+:-]*", value)
            or value.lower() in {"latest", "main", "master", "stable", "nightly", "unknown"}):
        raise CatalogError("unfixed_version")
    return value


def _path(value: object) -> str:
    value = _text(value, maximum=512)
    if (value.startswith("/") or any(c in value for c in "\\:%?#")
            or any(p in {"", ".", ".."} or p.endswith((" ", ".")) for p in value.split("/"))):
        raise CatalogError("unsafe_path")
    return value


def _url(value: object, prefixes: tuple[str, ...]) -> str:
    value = _text(value, maximum=2048)
    # Exact ASCII origins/prefixes, no credentials, queries, fragments or escapes.
    # The downloader separately enforces its bounded asset-hop policy and TLS.
    try:
        parts = urlsplit(value)
    except ValueError:
        raise CatalogError("untrusted_url") from None
    if (parts.scheme != "https" or parts.username or parts.password
            or parts.query or parts.fragment or "%" in value or "\\" in value
            or any(p.lower() in {".", "..", "latest", "nightly"} for p in parts.path.split("/"))
            or not any(value.startswith(prefix) and len(value) > len(prefix) for prefix in prefixes)):
        raise CatalogError("untrusted_url")
    return value


def _file(value: object) -> FileSpec:
    names = "path sha256 size_bytes role executable"
    row = _keys(value, names + (" archive_path" if type(value) is dict and "archive_path" in value else ""))
    path = _path(row["path"])
    if type(row["role"]) is not str or row["role"] not in ROLES or type(row["executable"]) is not bool:
        raise CatalogError("invalid_file_contract")
    if row["executable"] and row["role"] != "engine":
        raise CatalogError("unexpected_executable")
    return FileSpec(path, _digest(row["sha256"]),
                    _number(row["size_bytes"], MAX_INSTALLED_BYTES, minimum=0),
                    row["role"], row["executable"],
                    _path(row["archive_path"]) if "archive_path" in row else None)


# This additive contract covers the three already identified Debian source
# packages only. It does not widen the original primary-source URL policy or
# claim source completeness for arbitrary vendor/dependency packages.
DEBIAN_SOURCE_PACKAGES = {
    "prusaslicer": {"slic3r-prusa": "https://deb.debian.org/debian/pool/main/s/slic3r-prusa/"},
    "curaengine": {"cura-engine": "https://deb.debian.org/debian/pool/main/c/cura-engine/",
                   "cura": "https://deb.debian.org/debian/pool/main/c/cura/"},
}


def _source_components(value: object, engine: str, files: tuple[FileSpec, ...]) -> tuple[SourceComponent, ...]:
    if type(value) is not list or len(value) > 16:
        raise CatalogError("invalid_source_components")
    if not value:
        return ()
    known = {f.path: f for f in files}
    covered, identifiers, result = set(), set(), []
    source_bytes = 0
    for item in value:
        row = _keys(item, "id package component_version license source_revision archives files notices")
        ident = _text(row["id"])
        if re.fullmatch(r"[a-z][a-z0-9_-]*", ident) is None or ident in identifiers:
            raise CatalogError("invalid_source_component_id")
        identifiers.add(ident)
        package = _text(row["package"])
        origin = DEBIAN_SOURCE_PACKAGES.get(engine, {}).get(package)
        if origin is None:
            raise CatalogError("unsupported_source_package")
        version = _version(row["component_version"])
        epoch_parts = version.split(":")
        if len(epoch_parts) > 2 or (len(epoch_parts) == 2 and not epoch_parts[0].isdigit()):
            raise CatalogError("invalid_source_version")
        filename_version = epoch_parts[-1]
        upstream_version, separator, debian_revision = filename_version.rpartition("-")
        if (not separator or not upstream_version or not debian_revision
                or not upstream_version[0].isdigit()):
            raise CatalogError("invalid_source_version")
        archives = row["archives"]
        if type(archives) is not list or len(archives) != 3:
            raise CatalogError("invalid_source_archives")
        parsed_archives, kinds, urls = [], set(), set()
        for raw in archives:
            archive = _keys(raw, "kind url sha256 size_bytes")
            kind = archive["kind"]
            if type(kind) is not str or kind not in {"descriptor", "upstream", "debian_patches"} or kind in kinds:
                raise CatalogError("invalid_source_archives")
            kinds.add(kind)
            url = _url(archive["url"], (origin,))
            filename = urlsplit(url).path.rsplit("/", 1)[-1]
            expected_names = {
                "descriptor": {package + "_" + filename_version + ".dsc"},
                "upstream": {package + "_" + upstream_version + ".orig.tar." + suffix for suffix in ("gz", "xz")},
                "debian_patches": {package + "_" + filename_version + ".debian.tar." + suffix for suffix in ("gz", "xz")},
            }
            if filename not in expected_names[kind]:
                raise CatalogError("source_archive_version_mismatch")
            if url != origin + filename:
                raise CatalogError("invalid_source_archive_path")
            if url in urls:
                raise CatalogError("invalid_source_archive_name")
            urls.add(url)
            sha256 = _digest(archive["sha256"])
            if sha256 == "0" * 64:
                raise CatalogError("invalid_digest")
            size = _number(archive["size_bytes"], MAX_ARTIFACT_BYTES)
            source_bytes += size
            if source_bytes > MAX_INSTALLED_BYTES:
                raise CatalogError("source_size_limit")
            parsed_archives.append(SourceArchive(kind, url, sha256, size))
        revision = _digest(row["source_revision"])
        if revision != next(a.sha256 for a in parsed_archives if a.kind == "descriptor"):
            raise CatalogError("source_descriptor_mismatch")
        paths = row["files"]
        if type(paths) is not list or not 1 <= len(paths) <= len(known):
            raise CatalogError("source_file_coverage")
        parsed_paths = tuple(_path(p) for p in paths)
        if len(set(parsed_paths)) != len(parsed_paths) or any(p not in known or p in covered for p in parsed_paths):
            raise CatalogError("source_file_coverage")
        covered.update(parsed_paths)
        notices = row["notices"]
        if type(notices) is not list or not 1 <= len(notices) <= len(known):
            raise CatalogError("invalid_source_notices")
        parsed_notices = tuple(_path(p) for p in notices)
        if len(set(parsed_notices)) != len(parsed_notices) or any(
                p not in known or known[p].role != "license" or not known[p].size_bytes for p in parsed_notices):
            raise CatalogError("invalid_source_notices")
        result.append(SourceComponent(ident, package, version,
            _text(row["license"]), revision, tuple(parsed_archives), parsed_paths, parsed_notices))
    if covered != set(known):
        raise CatalogError("source_file_coverage")
    return tuple(result)


def _artifact(value: object, engine: str) -> Artifact:
    names = "id component_version url sha256 size_bytes format license source_url source_revision files"
    row = _keys(value, names + (" source_components" if type(value) is dict and "source_components" in value else ""))
    ident = _text(row["id"])
    if re.fullmatch(r"[a-z][a-z0-9_-]*", ident) is None:
        raise CatalogError("invalid_artifact_id")
    if type(row["format"]) is not str or row["format"] not in {"tar", "tar.gz", "tar.xz", "zip", "deb"}:
        raise CatalogError("unsupported_archive")
    files = row["files"]
    if type(files) is not list or not 1 <= len(files) <= MAX_FILES:
        raise CatalogError("invalid_file_list")
    parsed = tuple(_file(f) for f in files)
    if len({f.path.casefold() for f in parsed}) != len(parsed):
        raise CatalogError("conflicting_paths")
    if len({(f.archive_path or f.path).casefold() for f in parsed}) != len(parsed):
        raise CatalogError("conflicting_archive_paths")
    if not any(f.role == "license" and f.size_bytes > 0 for f in parsed):
        raise CatalogError("missing_license_file")
    revision = _text(row["source_revision"])
    if re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", revision) is None:
        raise CatalogError("unfixed_source")
    return Artifact(
        ident, _version(row["component_version"]), _url(row["url"], DOWNLOAD_PREFIXES),
        _digest(row["sha256"]), _number(row["size_bytes"], MAX_ARTIFACT_BYTES),
        row["format"], _text(row["license"]),
        _url(row["source_url"], (UPSTREAMS[engine],)), revision, parsed,
        _source_components(row.get("source_components", []), engine, parsed),
    )


def _release(value: object) -> Release:
    row = _keys(value, "engine version system architecture artifacts")
    engine = row["engine"]
    if type(engine) is not str or engine not in ENTRYPOINTS:
        raise CatalogError("unknown_engine")
    if row["system"] != "linux" or row["architecture"] != "amd64":
        raise CatalogError("unsupported_platform")
    if type(row["artifacts"]) is not list or not 1 <= len(row["artifacts"]) <= 16:
        raise CatalogError("invalid_artifacts")
    artifacts = tuple(_artifact(a, engine) for a in row["artifacts"])
    if len({a.id for a in artifacts}) != len(artifacts):
        raise CatalogError("duplicate_artifact")
    files = tuple(f for a in artifacts for f in a.files)
    if len(files) > MAX_FILES or sum(f.size_bytes for f in files) > MAX_INSTALLED_BYTES:
        raise CatalogError("installed_limit")
    paths = {f.path for f in files}
    if len({f.path.casefold() for f in files}) != len(files):
        raise CatalogError("conflicting_paths")
    for path in paths:
        parts = path.split("/")
        if any("/".join(parts[:n]) in paths for n in range(1, len(parts))):
            raise CatalogError("conflicting_paths")
    entries = [f for f in files if f.role == "engine"]
    if (len(entries) != 1 or entries[0].path != ENTRYPOINTS[engine]
            or not entries[0].executable or not entries[0].size_bytes):
        raise CatalogError("invalid_entrypoint")
    if not any(f.role == "resources" and f.size_bytes and f.path.startswith("resources/") for f in files):
        raise CatalogError("missing_resources")
    profiles = [f for f in files if f.role == "profiles" and f.size_bytes]
    if engine == "bambu_studio":
        good = any(f.path.startswith("resources/profiles/") and f.path.endswith(".json") for f in profiles)
    elif engine == "prusaslicer":
        good = (any(f.path.startswith("resources/") and f.path.endswith(".ini") for f in profiles)
                and any(f.role == "runtime" and f.size_bytes
                        and f.path.endswith("/OCCTWrapper.so") for f in files))
    else:
        good = any(f.path.startswith("resources/definitions/") and f.path.endswith(".def.json") for f in profiles)
    if not good:
        raise CatalogError("missing_profile_contract")
    return Release(engine, _version(row["version"]), row["architecture"], artifacts)


def _unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError("duplicate_json_key")
        result[key] = value
    return result


def load_catalog_bytes(data: bytes) -> Catalog:
    """Validate a trusted catalog; declarations are not evidence of acceptance."""
    if type(data) is not bytes or len(data) > MAX_CATALOG_BYTES:
        raise CatalogError("catalog_size")
    try:
        root = json.loads(data, object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, CatalogError):
            raise
        raise CatalogError("invalid_json") from None
    row = _keys(root, "schema releases pending")
    if type(row["schema"]) is not int or row["schema"] != 1:
        raise CatalogError("unsupported_schema")
    if type(row["releases"]) is not list or len(row["releases"]) > len(ENTRYPOINTS):
        raise CatalogError("invalid_releases")
    releases = tuple(_release(r) for r in row["releases"])
    approved = [r.engine for r in releases]
    if len(set(approved)) != len(approved):
        raise CatalogError("duplicate_release")
    pending = row["pending"]
    if (type(pending) is not list or any(type(p) is not str or p not in ENTRYPOINTS for p in pending)
            or len(set(pending)) != len(pending)
            or set(approved) & set(pending)
            or set(approved) | set(pending) != set(ENTRYPOINTS)):
        raise CatalogError("incomplete_catalog")
    return Catalog(releases, tuple(pending))


def load_catalog(path: Path | None = None) -> Catalog:
    path = path if path is not None else Path(__file__).with_name("engine_catalog.json")
    with path.open("rb") as stream:
        data = stream.read(MAX_CATALOG_BYTES + 1)
    return load_catalog_bytes(data)


def verify_artifact(stream: BinaryIO, artifact: Artifact) -> None:
    """Check a bounded byte stream. No filesystem mutation or engine execution.

    The future downloader must enforce network timeouts/redirect policy and the
    extractor must check every FileSpec before activation. A digest is not a signature.
    """
    if type(artifact) is not Artifact:
        raise CatalogError("invalid_artifact")
    _number(artifact.size_bytes, MAX_ARTIFACT_BYTES)
    _digest(artifact.sha256)
    digest = hashlib.sha256()
    remaining = artifact.size_bytes
    while remaining:
        chunk = stream.read(min(65536, remaining))
        if type(chunk) is not bytes or not chunk or len(chunk) > remaining:
            raise CatalogError("artifact_size_mismatch")
        digest.update(chunk)
        remaining -= len(chunk)
    if stream.read(1) != b"":
        raise CatalogError("artifact_size_mismatch")
    if digest.hexdigest() != artifact.sha256:
        raise CatalogError("artifact_digest_mismatch")

