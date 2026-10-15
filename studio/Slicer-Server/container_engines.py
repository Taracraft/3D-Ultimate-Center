"""Read-only container engine path contract; never starts an engine.

The installer owns the store. Runtime mounts it read-only and must stop workers
before replacement. Path checks are not provenance or slicing acceptance.
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

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["root", "list"])
    parser.add_argument("engine", nargs="?")
    args = parser.parse_args()
    try:
        if args.command == "root":
            print(resolve_engine(args.engine)["root"])
        else:
            if args.engine is not None:
                raise EnginePathError("unexpected_engine")
            print(json.dumps(available_engines()))
    except EnginePathError as exc:
        parser.exit(1, "Container engine rejected: " + str(exc) + "\n")

if __name__ == "__main__":
    main()
