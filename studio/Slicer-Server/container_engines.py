"""Read-only engine lookup and explicit build-time image resource layout.

The installer owns the engine store. Runtime mounts it read-only and must stop
workers before replacement. Image links expose the selected engine generation
at paths required by reviewed upstream builds; they do not approve or run it.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import stat

STORE = Path("/engine")
ENGINES = {
    "bambu_studio": ("Bambu Studio", "bin/bambu-studio"),
    "prusaslicer": ("PrusaSlicer", "bin/prusa-slicer"),
    "curaengine": ("CuraEngine", "bin/CuraEngine"),
}

class EnginePathError(ValueError):
    pass


def resolve_engine(engine, store=STORE):
    if engine not in ENGINES:
        raise EnginePathError("unknown_engine")
    store = Path(store).absolute()
    root = store / engine
    binary = root / ENGINES[engine][1]
    # Fixed paths only. No fallback to PATH, another engine or a host binary.
    for path in (store, root, root / "bin", binary):
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise EnginePathError("linked_engine_path")
    try:
        resolved_store = store.resolve(strict=True)
        resolved_root = root.resolve(strict=True)
        resolved_binary = binary.resolve(strict=True)
        if (resolved_root.parent != resolved_store
                or resolved_binary.parent != resolved_root / "bin"):
            raise EnginePathError("engine_path_escape")
        if not root.is_dir() or not stat.S_ISREG(binary.stat().st_mode):
            raise EnginePathError("engine_not_regular")
        if not os.access(binary, os.X_OK):
            raise EnginePathError("engine_not_executable")
        if any(ord(c) < 32 or ord(c) == 127 for c in str(resolved_root)):
            raise EnginePathError("invalid_engine_path")
    except (OSError, RuntimeError) as exc:
        raise EnginePathError("engine_path_unavailable") from exc
    return {"root": str(resolved_root), "binary": str(resolved_binary)}


def available_engines(store=STORE):
    result = []
    for engine, (name, _) in ENGINES.items():
        try:
            paths = resolve_engine(engine, store)
        except EnginePathError:
            continue
        result.append({"id": engine, "name": name, "type": engine,
                       "path": paths["binary"], "version": "unknown",
                       "available": True})
    return result


def image_link_plan():
    """Return the fixed Linux/amd64 image routes, not caller-controlled paths.

    Debian Prusa 2.9.2 uses compiled FHS resources and OCCT paths. Only the
    fonts subdirectory is an image overlay; actual font files are installed
    by their Debian packages, never copied from an operator's machine.
    """
    paths = {"usr/share/PrusaSlicer/" + name: "engine/prusaslicer/resources/" + name
             for name in ("data", "icons", "localization", "profiles", "shaders", "shapes", "web")}
    paths.update({
        "usr/share/PrusaSlicer/fonts/README.txt": "engine/prusaslicer/resources/fonts/README.txt",
        "usr/share/PrusaSlicer/fonts/NotoSans-Regular.ttf": "usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "usr/share/PrusaSlicer/fonts/NotoSansCJK-Regular.ttc": "usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "usr/lib/x86_64-linux-gnu/PrusaSlicer/OCCTWrapper.so": "engine/prusaslicer/lib/PrusaSlicer/OCCTWrapper.so",
        "usr/share/cura/resources": "engine/curaengine/resources",
    })
    return paths


def _image_root(root):
    root = Path(root)
    if not root.is_absolute() or ".." in root.parts:
        raise EnginePathError("invalid_image_root")
    if not root.is_dir():
        raise EnginePathError("invalid_image_root")
    for p in (root, *root.parents):
        if p.is_symlink() or getattr(p, "is_junction", lambda: False)():
            raise EnginePathError("linked_image_root")
    return root


def _image_parents(root, relative):
    path = root
    for part in Path(relative).parts[:-1]:
        path /= part
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise EnginePathError("linked_image_parent")
        if path.exists() and not path.is_dir():
            raise EnginePathError("invalid_image_parent")
    return path


def _link_target(root, name, target):
    return os.path.relpath(root / target, start=(root / name).parent)


def verify_image_layout(root=Path("/")):
    """Check only image-side routes; targets may be absent before engine install.

    This is not target-image ABI, real plugin loading, or engine readiness.
    The generation store is verified separately by the installer/runtime.
    """
    root = _image_root(root)
    paths = image_link_plan()
    for name, target in paths.items():
        _image_parents(root, name)
        path = root / name
        if not path.is_symlink() or os.readlink(path) != _link_target(root, name, target):
            raise EnginePathError("image_resource_link_mismatch")
    return {"image_resource_links": "verified", "links_verified": len(paths),
            "engine_executed": False, "engine_readiness_verified": False}


def prepare_image_layout(root=Path("/")):
    """Explicit Docker build step. Never called on import or by runtime lookup.

    All existing endpoints are checked before creating anything. Files,
    directories and different links are never replaced. An interrupted build
    can only reuse matching links; the Docker layer must still finish its check.
    The optional root parameter is for isolated temporary filesystem tests.
    """
    root = _image_root(root)
    paths = image_link_plan()
    for name, target in paths.items():
        _image_parents(root, name)
        path = root / name
        if os.path.lexists(path) and (
                not path.is_symlink() or os.readlink(path) != _link_target(root, name, target)):
            raise EnginePathError("image_resource_path_occupied")
    for name, target in paths.items():
        parent = _image_parents(root, name)
        parent.mkdir(parents=True, exist_ok=True)
        path = root / name
        if not os.path.lexists(path):
            # No force option: a concurrently created path makes this build fail.
            os.symlink(_link_target(root, name, target), path,
                       target_is_directory=name.rsplit("/", 1)[-1] in
                       {"data", "icons", "localization", "profiles", "shaders", "shapes", "web", "resources"})
    return verify_image_layout(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["root", "list", "prepare-image", "verify-image"])
    parser.add_argument("engine", nargs="?")
    args = parser.parse_args()
    try:
        if args.command == "root":
            print(resolve_engine(args.engine)["root"])
        elif args.command == "list":
            if args.engine is not None:
                raise EnginePathError("unexpected_engine")
            print(json.dumps(available_engines()))
        else:
            if args.engine is not None:
                raise EnginePathError("unexpected_engine")
            result = prepare_image_layout() if args.command == "prepare-image" else verify_image_layout()
            print(json.dumps(result, sort_keys=True))
    except (EnginePathError, OSError) as exc:
        code = str(exc) if isinstance(exc, EnginePathError) else "image_layout_unavailable"
        parser.exit(1, "Container engine rejected: " + code + "\n")


if __name__ == "__main__":
    main()
