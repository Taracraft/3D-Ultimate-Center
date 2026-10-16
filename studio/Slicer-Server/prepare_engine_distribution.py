"""Assemble a complete offline three-engine distribution from a pinned catalog.

Uses the existing catalog, bounded extractor and generation verifier. No network,
engine execution, active-store switch, Docker or Supervisor action. A complete
file package is not a runtime, license or product-release approval.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tarfile
import zlib

import engine_catalog as catalog
import package_activation as activation
import package_staging as staging

ARCHIVE = "engine-store.tar.gz"
CATALOG = "CATALOG.json"
DESCRIPTION = "DISTRIBUTION.json"
READY = "READY.json"
CHUNK = 65536
MAX_RECEIPT = 16384


class DistributionError(ValueError):
    """Fixed diagnostic codes, not local input paths or archive contents."""


def require(value, code):
    if not value:
        raise DistributionError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def pinned(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None
            and value != "0" * 64, "invalid_expected_digest")
    return value


def safe_path(value):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "absolute_path_required")
    for current in (path, *path.parents):
        require(not current.is_symlink() and not getattr(current, "is_junction", lambda: False)(),
                "linked_path")
    return path


def identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


@contextmanager
def regular(path):
    path = safe_path(path)
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "regular_unlinked_file_required")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        require(os.path.samestat(before, opened), "input_changed")
        yield stream
        require(identity(opened) == identity(os.fstat(stream.fileno())), "input_changed")
    require(identity(before) == identity(path.stat()), "input_changed")
    safe_path(path)


def read_bounded(path, maximum):
    with regular(path) as stream:
        require(os.fstat(stream.fileno()).st_size <= maximum, "metadata_too_large")
        raw = stream.read(maximum + 1)
    require(len(raw) <= maximum, "metadata_too_large")
    return raw


def check_file(path, size, expected, guard):
    digest = hashlib.sha256()
    with regular(path) as stream:
        require(os.fstat(stream.fileno()).st_size == size, "file_size_mismatch")
        left = size
        while left:
            guard.check()
            raw = stream.read(min(CHUNK, left))
            require(bool(raw), "file_size_mismatch")
            digest.update(raw)
            left -= len(raw)
        require(not stream.read(1), "file_size_mismatch")
    guard.check()
    require(digest.hexdigest() == expected, "file_digest_mismatch")


def load_inputs(raw, expected_digest):
    require(sha(raw) == pinned(expected_digest), "catalog_digest_mismatch")
    parsed = catalog.load_catalog_bytes(raw)
    require(not parsed.pending and {r.engine for r in parsed.releases} == set(catalog.ENTRYPOINTS),
            "complete_engine_catalog_required")
    releases = {r.engine: r for r in parsed.releases}
    files = [f for r in releases.values() for a in r.artifacts for f in a.files]
    require(len(files) <= catalog.MAX_FILES and
            sum(f.size_bytes for f in files) <= catalog.MAX_INSTALLED_BYTES and
            sum(r.download_bytes for r in releases.values()) <= catalog.MAX_INSTALLED_BYTES,
            "distribution_limit")
    for release in releases.values():
        staging._target_contract(tuple(f for a in release.artifacts for f in a.files))
        for artifact in release.artifacts:
            pinned(artifact.sha256)
            for file in artifact.files:
                pinned(file.sha256)
    return releases


def description(releases, catalog_digest):
    return {
        "schema": 1, "kind": "ultimate-slicer-engine-distribution",
        "catalog_sha256": catalog_digest,
        "generation_id": activation._generation_document(releases)["generation_id"],
        "system": "linux", "architecture": "amd64",
        "engines": [{"engine": name, "version": release.version,
                     "files": sum(len(a.files) for a in release.artifacts),
                     "installed_bytes": release.installed_bytes,
                     "archive_count": len(release.artifacts)}
                    for name, release in sorted(releases.items())],
        "engine_executed": False, "active_store_changed": False,
        "runtime_approved": False, "license_review_complete": False,
        "product_release_complete": False,
    }


def members(releases, raw_catalog):
    """Exact archive members and Unix modes; never OS-default permission guesses."""
    metadata = {
        CATALOG: raw_catalog,
        DESCRIPTION: canonical(description(releases, sha(raw_catalog))),
        "engine/GENERATION.json": canonical(activation._generation_document(releases)),
    }
    rows = {name: (len(raw), sha(raw), 0o644) for name, raw in metadata.items()}
    for name, release in releases.items():
        for artifact in release.artifacts:
            for spec in artifact.files:
                rows["engine/" + name + "/" + spec.path] = (
                    spec.size_bytes, spec.sha256, 0o755 if spec.executable else 0o644)
    return metadata, rows


class HashSink:
    def __init__(self):
        self.digest = hashlib.sha256()
        self.size = 0
    def write(self, raw):
        self.digest.update(raw)
        self.size += len(raw)
        return len(raw)
    def flush(self):
        pass


class CheckedReader:
    def __init__(self, stream, guard):
        self.stream, self.guard = stream, guard
        self.digest = hashlib.sha256()
        self.size = 0
    def read(self, count):
        self.guard.check()
        raw = self.stream.read(count)
        self.digest.update(raw)
        self.size += len(raw)
        return raw


def write_tar(sink, root, rows, guard):
    with tarfile.open(fileobj=sink, mode="w|", format=tarfile.GNU_FORMAT) as archive:
        for name, (size, expected, mode) in sorted(rows.items()):
            guard.check()
            item = tarfile.TarInfo(name)
            item.size, item.mode, item.mtime = size, mode, 0
            item.uid = item.gid = 0
            item.uname = item.gname = ""
            with regular(root / name) as stream:
                require(os.fstat(stream.fileno()).st_size == size, "file_size_mismatch")
                reader = CheckedReader(stream, guard)
                archive.addfile(item, reader)
                require(reader.size == size and not stream.read(1)
                        and reader.digest.hexdigest() == expected, "archive_source_changed")
    guard.check()


def write_archive(sink, root, rows, guard):
    # Fixed metadata yields reproducible archives for the pinned build toolchain.
    # Verification below does not require the recipient's compressor to emit the
    # same compressed bytes: it verifies the exact canonical uncompressed stream.
    with gzip.GzipFile(filename="", fileobj=sink, mode="wb", mtime=0, compresslevel=9) as compressed:
        write_tar(compressed, root, rows, guard)


def archive_identity(path, expected_tar, guard):
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    content = HashSink()
    compressed = HashSink()
    with regular(path) as stream:
        require(os.fstat(stream.fileno()).st_size <= max(1024**2, expected_tar.size * 2),
                "archive_size_limit")
        while raw := stream.read(CHUNK):
            guard.check()
            require(not decoder.eof, "trailing_archive_stream")
            compressed.write(raw)
            pending = raw
            while pending:
                guard.check()
                try:
                    data = decoder.decompress(pending, CHUNK)
                except zlib.error:
                    raise DistributionError("archive_encoding_invalid") from None
                content.write(data)
                require(content.size <= expected_tar.size, "archive_expansion_limit")
                pending = decoder.unconsumed_tail
                if decoder.eof:
                    require(not decoder.unused_data and not pending, "trailing_archive_stream")
                    break
    require(decoder.eof and content.size == expected_tar.size
            and content.digest.digest() == expected_tar.digest.digest(), "archive_content_mismatch")
    return compressed.size, compressed.digest.hexdigest()


def exact_tree(root, rows, *, ready):
    expected = set(rows) | ({ARCHIVE, READY} if ready else set())
    directories = {"engine"}
    for name in expected:
        parent = Path(name).parent
        while str(parent) != ".":
            directories.add(parent.as_posix())
            parent = parent.parent
    found_files, found_dirs = set(), set()
    for path in root.rglob("*"):
        safe_path(path)
        name = path.relative_to(root).as_posix()
        if path.is_dir():
            found_dirs.add(name)
        elif path.is_file():
            require(path.stat().st_nlink == 1, "regular_unlinked_file_required")
            found_files.add(name)
        else:
            raise DistributionError("unexpected_output_member")
    require(found_files == expected and found_dirs == directories, "output_member_mismatch")


def verify(output, expected_catalog_sha256, *, cancelled=None):
    root = safe_path(output)
    staging._private_parent(root)
    guard = staging._Guard(cancelled)
    raw = read_bounded(root / CATALOG, catalog.MAX_CATALOG_BYTES)
    releases = load_inputs(raw, expected_catalog_sha256)
    metadata, rows = members(releases, raw)
    exact_tree(root, rows, ready=True)
    for name, expected in metadata.items():
        require(read_bounded(root / name, max(catalog.MAX_CATALOG_BYTES * 2, MAX_RECEIPT)) == expected,
                "metadata_mismatch")
    for engine, release in releases.items():
        guard.check()
        activation._validate_tree(root / "engine" / engine, release)
    # Derive exact canonical TAR bytes from verified inputs, then boundedly hash
    # decompressed bytes without interpreting archive paths/headers. A changed
    # archive plus changed self-declared digest cannot smuggle another payload.
    sink = HashSink()
    write_tar(sink, root, rows, guard)
    archive_bytes, archive_hash = archive_identity(root / ARCHIVE, sink, guard)
    receipt = {"schema": 1, "state": "assembled", "catalog_sha256": sha(raw),
               "distribution_sha256": sha(metadata[DESCRIPTION]),
               "archive_sha256": archive_hash, "archive_bytes": archive_bytes,
               "archive_members": len(rows), "engine_executed": False,
               "active_store_changed": False, "product_release_complete": False}
    require(read_bounded(root / READY, MAX_RECEIPT) == canonical(receipt), "receipt_mismatch")
    return {**receipt, "verified": True, "engine_count": len(releases),
            "engine_files": sum(len(a.files) for r in releases.values() for a in r.artifacts),
            "generation_id": activation._generation_document(releases)["generation_id"]}


def assemble(catalog_path, expected_catalog_sha256, archive_root, output, *, cancelled=None):
    """Prepare all engines or no ready output; never touch an active store.

    Input cache paths are fixed engine/artifact-ID.archive. The caller must own
    the stable private parent. Hard termination may leave an incomplete directory;
    consumers must verify READY and all bytes, not interpret directory existence.
    """
    source, cache, root = map(safe_path, (catalog_path, archive_root, output))
    staging._private_parent(root.parent)
    require(cache.is_dir(), "cache_root_missing")
    code_root = Path(__file__).resolve().parents[1]
    require(root != code_root and code_root not in root.parents, "output_inside_source")
    require(not root.exists() and not os.path.lexists(root), "output_exists")
    require(root != cache and root not in cache.parents and cache not in root.parents
            and root != source and root not in source.parents, "input_output_overlap")
    guard = staging._Guard(cancelled)
    raw = read_bounded(source, catalog.MAX_CATALOG_BYTES)
    releases = load_inputs(raw, expected_catalog_sha256)
    archives = {}
    for engine, release in sorted(releases.items()):
        archives[engine] = {}
        for artifact in release.artifacts:
            path = safe_path(cache / engine / (artifact.id + ".archive"))
            check_file(path, artifact.size_bytes, artifact.sha256, guard)
            archives[engine][artifact.id] = path
    guard.check()
    require(read_bounded(source, catalog.MAX_CATALOG_BYTES) == raw, "catalog_changed")
    root.mkdir(mode=0o700)
    owner = root.stat()
    complete = False
    try:
        work = root / ".staging"
        work.mkdir(mode=0o700)
        store = root / "engine"
        store.mkdir(mode=0o755)
        for engine, release in sorted(releases.items()):
            guard.check()
            staged = staging.prepare_release(release, work, archives=archives[engine], cancelled=cancelled)
            require(activation._candidate(staged) == release, "staged_release_mismatch")
            (staged / "payload" / engine).rename(store / engine)
            shutil.rmtree(staged)
        work.rmdir()
        metadata, rows = members(releases, raw)
        for name, content in metadata.items():
            with (root / name).open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            (root / name).chmod(0o644)
        exact_tree(root, rows, ready=False)
        for engine, release in releases.items():
            guard.check()
            activation._validate_tree(store / engine, release)
        with (root / ARCHIVE).open("xb") as stream:
            write_archive(stream, root, rows, guard)
            stream.flush()
            os.fsync(stream.fileno())
        sink = HashSink()
        write_tar(sink, root, rows, guard)
        archive_bytes, archive_hash = archive_identity(root / ARCHIVE, sink, guard)
        # Reconfirm all inputs after staging, not merely the initially parsed data.
        require(read_bounded(source, catalog.MAX_CATALOG_BYTES) == raw, "catalog_changed")
        for engine, release in releases.items():
            for artifact in release.artifacts:
                check_file(archives[engine][artifact.id], artifact.size_bytes, artifact.sha256, guard)
        receipt = {"schema": 1, "state": "assembled", "catalog_sha256": sha(raw),
                   "distribution_sha256": sha(metadata[DESCRIPTION]),
                   "archive_sha256": archive_hash, "archive_bytes": archive_bytes,
                   "archive_members": len(rows), "engine_executed": False,
                   "active_store_changed": False, "product_release_complete": False}
        with (root / READY).open("xb") as stream:
            stream.write(canonical(receipt))
            stream.flush()
            os.fsync(stream.fileno())
        activation._fsync_directory(root)
        result = verify(root, expected_catalog_sha256, cancelled=cancelled)
        complete = True
        return result
    finally:
        if not complete:
            # Only our newly reserved private output. Never an input, old output,
            # symbolic link or replaced directory from another operation.
            safe_path(root)
            require(os.path.samestat(owner, root.stat()), "output_identity_changed")
            shutil.rmtree(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--expected-catalog-sha256", required=True)
    parser.add_argument("--archive-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    if not ((args.verify and not any((args.catalog, args.archive_root, args.output)))
            or (not args.verify and all((args.catalog, args.archive_root, args.output)))):
        parser.error("use --verify DIRECTORY or --catalog FILE --archive-root DIRECTORY --output NEW_DIRECTORY")
    try:
        result = (verify(args.verify, args.expected_catalog_sha256) if args.verify else
                  assemble(args.catalog, args.expected_catalog_sha256, args.archive_root, args.output))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError):
        print(json.dumps({"ok": False, "error": "engine_distribution_rejected"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
