#!/usr/bin/env python3
"""Capture and verify a fail-closed Debian target-image package/SBOM record.

This module never runs Docker, downloads packages, or approves production use.
It consumes an inventory exported inside a separately built image and hashes the
corresponding Debian copyright files from an explicitly supplied root.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any, Iterable

MAX_JSON_BYTES = 8 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
IMMUTABLE_IMAGE_RE = re.compile(r"^.+@sha256:[0-9a-f]{64}$")


class EvidenceError(ValueError):
    """Raised when target-image evidence is incomplete or ambiguous."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    data = _read_regular_file(path, MAX_JSON_BYTES)
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise EvidenceError("JSON root must be an object")
    return value


def _read_regular_file(path: Path, maximum: int) -> bytes:
    try:
        st = path.lstat()
    except FileNotFoundError as exc:
        raise EvidenceError(f"missing file: {path}") from exc
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise EvidenceError(f"not a regular non-link file: {path}")
    if st.st_nlink != 1:
        raise EvidenceError(f"file must have exactly one hard link: {path}")
    if st.st_size > maximum:
        raise EvidenceError(f"file exceeds {maximum} bytes: {path}")
    data = path.read_bytes()
    if len(data) != st.st_size:
        raise EvidenceError(f"file changed while reading: {path}")
    return data


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _base_package(name: str) -> str:
    base = name.split(":", 1)[0]
    if not base or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789+.-" for ch in base):
        raise EvidenceError(f"invalid Debian package name: {name!r}")
    return base


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise EvidenceError(f"{field} must be a lowercase SHA-256")
    return value


def _reference_packages(reference: dict[str, Any]) -> list[str]:
    if reference.get("schema") != 1:
        raise EvidenceError("unsupported reference schema")
    if reference.get("production_approved") is not False:
        raise EvidenceError("reference must not approve production")
    packages = reference.get("required_packages")
    if not isinstance(packages, list) or not packages:
        raise EvidenceError("required_packages must be a non-empty array")
    if any(not isinstance(item, str) for item in packages):
        raise EvidenceError("required package names must be strings")
    normalized = [_base_package(item) for item in packages]
    if normalized != sorted(normalized) or len(normalized) != len(set(normalized)):
        raise EvidenceError("required_packages must be sorted and unique")
    _require_sha256(reference.get("dockerfile_sha256"), "dockerfile_sha256")
    _require_sha256(reference.get("host_reference_sha256"), "host_reference_sha256")
    return normalized


def parse_packages_tsv(path: Path) -> list[dict[str, str]]:
    data = _read_regular_file(path, MAX_JSON_BYTES)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceError("package inventory is not UTF-8") from exc
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), 1):
        fields = line.split("\t")
        if len(fields) != 5 or any(not field for field in fields[:3]):
            raise EvidenceError(f"invalid package inventory row {line_number}")
        binary, version, architecture, source, source_version = fields
        base = _base_package(binary)
        if base in seen:
            raise EvidenceError(f"duplicate binary package: {base}")
        seen.add(base)
        if architecture not in {"amd64", "all"}:
            raise EvidenceError(f"unexpected architecture for {base}: {architecture}")
        records.append(
            {
                "binary_package": base,
                "version": version,
                "architecture": architecture,
                "source_package": source or base,
                "source_version": source_version or version,
            }
        )
    if not records:
        raise EvidenceError("package inventory is empty")
    return sorted(records, key=lambda item: item["binary_package"])


def capture(
    *,
    reference_path: Path,
    packages_tsv: Path,
    copyright_root: Path,
    base_image: str,
    image_id: str,
) -> dict[str, Any]:
    if not IMMUTABLE_IMAGE_RE.fullmatch(base_image):
        raise EvidenceError("base image must be pinned as name@sha256:<64 lowercase hex>")
    if not IMAGE_ID_RE.fullmatch(image_id):
        raise EvidenceError("image_id must be sha256:<64 lowercase hex>")

    reference_bytes = _read_regular_file(reference_path, MAX_JSON_BYTES)
    reference = json.loads(reference_bytes.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    if not isinstance(reference, dict):
        raise EvidenceError("reference root must be an object")
    required = _reference_packages(reference)
    packages = parse_packages_tsv(packages_tsv)
    actual = {item["binary_package"] for item in packages}
    missing = sorted(set(required) - actual)
    if missing:
        raise EvidenceError("missing required packages: " + ", ".join(missing))

    captured: list[dict[str, str]] = []
    for record in packages:
        package = record["binary_package"]
        path = copyright_root / package / "copyright"
        copyright_bytes = _read_regular_file(path, 4 * 1024 * 1024)
        captured.append(
            {
                **record,
                "copyright_path": f"/usr/share/doc/{package}/copyright",
                "copyright_sha256": _sha256_bytes(copyright_bytes),
            }
        )

    return {
        "schema": 1,
        "kind": "ultimate-slicer-target-image-package-evidence",
        "base_image": base_image,
        "image_id": image_id,
        "reference_sha256": _sha256_bytes(reference_bytes),
        "required_packages": required,
        "package_count": len(captured),
        "packages": captured,
        "target_inventory_complete": True,
        "production_approved": False,
        "runtime_approved": False,
        "limitations": [
            "This record proves only the supplied immutable image inventory and copyright bytes.",
            "Engine binaries, plugins, TLS, lifecycle, persistence, restore and runtime acceptance remain separate.",
        ],
    }


def verify(evidence: dict[str, Any], reference_path: Path) -> None:
    if evidence.get("schema") != 1 or evidence.get("kind") != "ultimate-slicer-target-image-package-evidence":
        raise EvidenceError("unsupported evidence schema or kind")
    if evidence.get("production_approved") is not False or evidence.get("runtime_approved") is not False:
        raise EvidenceError("evidence must not approve production or runtime")
    if evidence.get("target_inventory_complete") is not True:
        raise EvidenceError("target inventory is not marked complete")
    base_image = evidence.get("base_image")
    image_id = evidence.get("image_id")
    if not isinstance(base_image, str) or not IMMUTABLE_IMAGE_RE.fullmatch(base_image):
        raise EvidenceError("invalid immutable base image")
    if not isinstance(image_id, str) or not IMAGE_ID_RE.fullmatch(image_id):
        raise EvidenceError("invalid image id")

    reference_bytes = _read_regular_file(reference_path, MAX_JSON_BYTES)
    if evidence.get("reference_sha256") != _sha256_bytes(reference_bytes):
        raise EvidenceError("reference hash mismatch")
    reference = json.loads(reference_bytes.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    required = _reference_packages(reference)
    if evidence.get("required_packages") != required:
        raise EvidenceError("required package set mismatch")

    packages = evidence.get("packages")
    if not isinstance(packages, list) or evidence.get("package_count") != len(packages):
        raise EvidenceError("package count mismatch")
    names: list[str] = []
    for record in packages:
        if not isinstance(record, dict):
            raise EvidenceError("package record must be an object")
        expected_fields = {
            "binary_package", "version", "architecture", "source_package",
            "source_version", "copyright_path", "copyright_sha256",
        }
        if set(record) != expected_fields:
            raise EvidenceError("package record fields mismatch")
        name = _base_package(record["binary_package"])
        names.append(name)
        if record["architecture"] not in {"amd64", "all"}:
            raise EvidenceError(f"invalid architecture for {name}")
        expected_path = f"/usr/share/doc/{name}/copyright"
        if record["copyright_path"] != expected_path:
            raise EvidenceError(f"invalid copyright path for {name}")
        _require_sha256(record["copyright_sha256"], f"copyright_sha256 for {name}")
        for field in ("version", "source_package", "source_version"):
            if not isinstance(record[field], str) or not record[field]:
                raise EvidenceError(f"missing {field} for {name}")
    if names != sorted(names) or len(names) != len(set(names)):
        raise EvidenceError("package records must be sorted and unique")
    missing = sorted(set(required) - set(names))
    if missing:
        raise EvidenceError("required package records missing: " + ", ".join(missing))


def _write_new_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise EvidenceError(f"refusing to overwrite output: {path}")
    data = (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, data)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("--reference", type=Path, required=True)
    capture_parser.add_argument("--packages-tsv", type=Path, required=True)
    capture_parser.add_argument("--copyright-root", type=Path, required=True)
    capture_parser.add_argument("--base-image", required=True)
    capture_parser.add_argument("--image-id", required=True)
    capture_parser.add_argument("--output-new", type=Path, required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--reference", type=Path, required=True)
    verify_parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.command == "capture":
        result = capture(
            reference_path=args.reference,
            packages_tsv=args.packages_tsv,
            copyright_root=args.copyright_root,
            base_image=args.base_image,
            image_id=args.image_id,
        )
        verify(result, args.reference)
        _write_new_json(args.output_new, result)
    else:
        verify(load_json(args.evidence), args.reference)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
