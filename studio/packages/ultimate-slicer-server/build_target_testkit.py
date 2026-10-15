"""Create a portable, private, non-installing Linux test handoff archive.

The work server is not accessed by this builder. The native inner bundle
retains its explicit NOT APPROVED FOR INSTALLATION release gate.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import zipfile

PACKAGE = "ultimate-slicer-server"
UNITS = (
    "ultimate-slicer-server.service",
    "ultimate-slicer-dispatch.service",
    "ultimate-slicer-dispatch.timer",
    "ultimate-slicer-refresh.service",
    "ultimate-slicer-refresh.timer",
)


def _digest(content: bytes) -> str:
    return sha256(content).hexdigest()


def _load_native_builder(path: Path):
    spec = importlib.util.spec_from_file_location("isolated_native_bundle_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("native source builder unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_file(source: Path, base: Path) -> bytes:
    if not source.is_file() or source.is_symlink():
        raise ValueError("testkit source missing, linked or not a regular file")
    if not source.resolve(strict=True).is_relative_to(base.resolve(strict=True)):
        raise ValueError("testkit source is outside the canonical PC root")
    return source.read_bytes()


def build(root: Path, destination: Path) -> dict:
    root = root.resolve(strict=True)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("a prior testkit may not be overwritten")
    package = root / "packages" / PACKAGE
    native_builder = _load_native_builder(package / "build_native_package.py")
    sources = {
        "README.md": package / "WORK_SERVER_TEST_GUIDE.md",
        "check_target_host.sh": package / "check_target_host.sh",
        "run_isolated_test.sh": package / "run_isolated_test.sh",
        f"packages/{PACKAGE}/install_native.py": package / "install_native.py",
        "tests/native_linux_install_sandbox.py": root / "tests/native_linux_install_sandbox.py",
    }
    for name in UNITS:
        sources["units/" + name] = package / "systemd" / name

    contents = {name: _read_file(path, root) for name, path in sources.items()}
    with tempfile.TemporaryDirectory(prefix="studio-native-testkit-build-") as work:
        inner = Path(work) / "native-source.tar.gz"
        native_record = native_builder.build(root, inner)
        if native_record.get("native_deploy_ready") is not False:
            raise ValueError("work-server test kit must never contain approved installer")
        contents["native-source.tar.gz"] = inner.read_bytes()

    checksums = "".join(
        _digest(blob) + "  " + name + "\n"
        for name, blob in sorted(contents.items())
    )
    contents["SHA256SUMS"] = checksums.encode("utf-8")
    if any(
        str(name).startswith("/") or ".." in Path(name).parts or "\\" in name
        for name in contents
    ):
        raise ValueError("unexpected archive destination path")

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("xb") as stream, zipfile.ZipFile(
            stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as zipped:
            for name in sorted(contents):
                mode = 0o755 if name.endswith(".sh") else 0o644
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o100000 | mode) << 16
                zipped.writestr(info, contents[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

        with zipfile.ZipFile(destination, "r") as archive:
            if set(archive.namelist()) != set(contents):
                raise ValueError("work-server archive member mismatch")
            for name, blob in contents.items():
                if archive.read(name) != blob:
                    raise ValueError("work-server archive content mismatch")
        return {
            "archive": str(destination),
            "sha256": _digest(destination.read_bytes()),
            "file_count": len(contents),
            "native_source_sha256": _digest(contents["native-source.tar.gz"]),
            "native_deploy_ready": False,
            "installation_performed": False,
            "remote_server_accessed": False,
            "private_publication_approved": False,
        }
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError("private testkit report already exists")
    report = build(args.source_root, args.output)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
