"""Build a private HACS integration preview; no public push or live HA write."""
from __future__ import annotations
import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil

INTEGRATION = "ultimate_3d_studio"
PRODUCT = "Ultimate 3D Studio"
ASSETS = ("ultimate-3d-studio.js", "ultimate-3d-studio.css", "ultimate-3d-studio-build.json")
ACCEPTED_EXTENSIONS = frozenset({".py", ".json", ".yaml", ".yml"})
IGNORED_EXTENSIONS = frozenset({".pyc", ".pyo", ".bak", ".tmp", ".log", ".sh"})
PUBLIC_DOCUMENTATION = "https://github.com/Taracraft/3D-Ultimate-Center"


class HacsPreviewError(RuntimeError):
    pass


def file_hash(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise HacsPreviewError("missing or linked HACS source file")
    return sha256(path.read_bytes()).hexdigest()


def _is_noop_module(path: Path) -> bool:
    """Exclude docstring-only Python stubs that have no executable behavior."""
    if path.suffix != ".py" or path.name == "__init__.py":
        return False
    try:
        syntax = ast.parse(path.read_text(encoding="utf-8-sig"))
    except (UnicodeError, SyntaxError):
        raise HacsPreviewError("integration Python source cannot be parsed") from None
    return (
        len(syntax.body) == 1
        and isinstance(syntax.body[0], ast.Expr)
        and isinstance(syntax.body[0].value, ast.Constant)
        and isinstance(syntax.body[0].value.value, str)
    )


def validate_import_closure(sources: list[tuple[Path, Path]]) -> int:
    """Reject a HACS package with missing relative module imports before writes."""
    included = {relative.as_posix() for _path, relative in sources}
    count = 0
    for source, relative in sources:
        if source.suffix != ".py":
            continue
        try:
            syntax = ast.parse(source.read_text(encoding="utf-8-sig"))
        except (SyntaxError, UnicodeError):
            raise HacsPreviewError("integration Python source cannot be parsed") from None
        for node in ast.walk(syntax):
            if not isinstance(node, ast.ImportFrom) or node.level == 0:
                continue
            count += 1
            parents = relative.parent.parts
            if node.level > len(parents) + 1:
                raise HacsPreviewError("relative import escapes HA integration")
            base = Path(*parents[: len(parents) - (node.level - 1)])
            names = (
                [base.joinpath(*node.module.split("."))]
                if node.module else
                [base / alias.name for alias in node.names]
            )
            for name in names:
                if (
                    name.with_suffix(".py").as_posix() not in included
                    and (name / "__init__.py").as_posix() not in included
                ):
                    raise HacsPreviewError("missing relative Python module in HACS package")
    return count


def build(root: Path, target: Path) -> dict:
    root = root.resolve(strict=True)
    source = root / "deploy" / "homeassistant" / "custom_components" / INTEGRATION
    frontend = root / "deploy" / "homeassistant" / "www" / "3d-studio"
    reviewed = {path: file_hash(path) for path in (
        root / "package.json", source / "manifest.json",
        *(frontend / name for name in ASSETS),
    )}
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    original_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    built = json.loads((frontend / ASSETS[2]).read_text(encoding="utf-8"))
    version = package.get("version")
    if (
        not isinstance(version, str)
        or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?", version)
        or original_manifest.get("domain") != INTEGRATION
        or original_manifest.get("version") != version
        or built.get("version") != version
        or not isinstance(built.get("build_id"), str)
        or not re.fullmatch(r"[a-f0-9]{10}", built["build_id"])
    ):
        raise HacsPreviewError("HA and frontend release metadata do not match")
    if (
        built.get("sha256") != reviewed[frontend / ASSETS[0]]
        or built.get("size_bytes") != (frontend / ASSETS[0]).stat().st_size
        or (built.get("css") or {}).get("sha256") != reviewed[frontend / ASSETS[1]]
        or (built.get("css") or {}).get("size_bytes") != (frontend / ASSETS[1]).stat().st_size
    ):
        raise HacsPreviewError("frontend assets differ from reviewed buildmanifest")

    if not source.is_dir() or source.is_symlink():
        raise HacsPreviewError("canonical HA integration source missing")
    selected = []
    omitted_noop = 0
    for item in sorted(source.rglob("*")):
        relative = item.relative_to(source)
        if "__pycache__" in relative.parts:
            continue
        if item.is_symlink():
            raise HacsPreviewError("linked HA source not allowed")
        if item.is_dir():
            continue
        if item.name.startswith(".") or item.suffix in IGNORED_EXTENSIONS:
            continue
        if item.suffix == ".png":
            expected_size = {"icon.png": 256, "icon@2x.png": 512, "dark_icon.png": 256, "dark_icon@2x.png": 512}.get(item.name)
            raw = item.read_bytes()
            if (relative.parent.as_posix() != "brand" or expected_size is None
                    or not 33 <= len(raw) <= 256 * 1024
                    or raw[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                    or int.from_bytes(raw[16:20], "big") != expected_size
                    or int.from_bytes(raw[20:24], "big") != expected_size):
                raise HacsPreviewError("invalid integration brand asset")
        elif item.suffix not in ACCEPTED_EXTENSIONS:
            raise HacsPreviewError("unknown integration source file type")
        reviewed.setdefault(item, file_hash(item))
        if _is_noop_module(item):
            omitted_noop += 1
            continue
        selected.append((item, relative))
    if not any(rel.as_posix() == "__init__.py" for _, rel in selected):
        raise HacsPreviewError("HA integration entry missing")
    if any(rel.parts[0] == "assets" for _, rel in selected):
        raise HacsPreviewError("frontend assets must come from verified build")
    resolved_imports = validate_import_closure(selected)
    for path, expected in reviewed.items():
        if file_hash(path) != expected:
            raise HacsPreviewError("HACS input changed during review")

    if target.exists() or target.is_symlink():
        raise FileExistsError("existing private HACS preview will never be overwritten")
    # Claim a new output root before entering cleanup; never remove a raced target.
    target.mkdir(parents=True, exist_ok=False)
    try:
        dest = target / "custom_components" / INTEGRATION
        dest.mkdir(parents=True)
        for path, relative in selected:
            output = dest / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            payload = path.read_bytes()
            if sha256(payload).hexdigest() != reviewed[path]:
                raise HacsPreviewError("HACS source changed during copy")
            output.write_bytes(payload)
        manifest = {
            **original_manifest,
            "documentation": PUBLIC_DOCUMENTATION,
            "issue_tracker": PUBLIC_DOCUMENTATION + "/issues",
            "version": version,
        }
        (dest / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        assets = dest / "assets"
        assets.mkdir()
        for name in ASSETS:
            payload = (frontend / name).read_bytes()
            if sha256(payload).hexdigest() != reviewed[frontend / name]:
                raise HacsPreviewError("HACS asset changed during copy")
            (assets / name).write_bytes(payload)
        (target / "hacs.json").write_text(
            json.dumps({"name": PRODUCT, "render_readme": True}, indent=2) + "\n",
            encoding="utf-8",
        )
        (target / "README.md").write_text(
            "# Ultimate 3D Studio\n\n"
            "Als HACS-Custom-Integration installieren. Die komplette Frontend-Oberflaeche "
            "ist enthalten; der Linux-Slicer ist ein separates Paket.\n\n"
            "Lovelace-JavaScript-Ressource: /ultimate-3d-studio/assets/ultimate-3d-studio.js\n"
            "Lovelace-Kartentyp: custom:ultimate-3d-studio-card\n\n"
            "Slicer-Adresse und API-Secret unter Home Assistant, Einstellungen, "
            "Geraete und Dienste, Ultimate 3D Studio, Konfigurieren eintragen.\n\n"
            "Privater Vorab-Build ohne oeffentliche Release-Freigabe.\n",
            encoding="utf-8",
        )
        for path, expected in reviewed.items():
            if file_hash(path) != expected:
                raise HacsPreviewError("HACS input changed before completion")
        identities = {
            item.relative_to(target).as_posix(): file_hash(item)
            for item in sorted(target.rglob("*")) if item.is_file()
        }
        if not identities.get("hacs.json") or not identities.get("README.md"):
            raise HacsPreviewError("HACS metadata missing")
        return {
            "root": str(target), "integration": INTEGRATION,
            "version": version, "build_id": built["build_id"],
            "files": len(identities), "integration_sources": len(selected),
            "noop_modules_excluded": omitted_noop,
            "relative_imports_verified": resolved_imports,
            "frontend_assets": len(ASSETS),
            "native_slicer_bundled": False, "publication_approved": False,
            "security_review_complete": False, "fresh_HA_install_verified": False,
            "file_sha256": identities,
            "source_snapshot_verified": True,
            "source_sha256": {path.relative_to(root).as_posix(): digest
                              for path, digest in reviewed.items()},
        }
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError("HACS report already exists")
    result = build(args.source_root, args.output_root)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "file_sha256"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

