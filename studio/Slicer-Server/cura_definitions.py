"""Read-only Cura definition dependency checks for the installer.

No settings expressions, G-code, plugins or engines are evaluated. See
RESOURCE_VALIDATION.md and LICENSE. This checks structure, not slicing results.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import stat

MAX_FILES = 4096
MAX_FILE_BYTES = 2 * 1024**2
MAX_TOTAL_BYTES = 32 * 1024**2
MAX_CHAIN = 64
_ID = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.+ -]{0,127}\Z")


class DefinitionError(ValueError):
    """Stable diagnostic code without paths or untrusted document content."""


@dataclass(frozen=True)
class Definition:
    id: str
    kind: str
    relative_path: str
    sha256: str
    size_bytes: int
    parent: str | None
    trains: tuple[str, ...]


@dataclass(frozen=True)
class DefinitionSet:
    files: tuple[Definition, ...]

    def summary(self) -> dict:
        return {
            "definitions": sum(f.kind == "definitions" for f in self.files),
            "extruders": sum(f.kind == "extruders" for f in self.files),
            "parent_edges": sum(f.parent is not None for f in self.files),
            "train_references": sum(len(f.trains) for f in self.files),
            "total_bytes": sum(f.size_bytes for f in self.files),
        }

    def dependencies(self, printer: str) -> tuple[Definition, ...]:
        """Conservative closure: includes declarations along all parent chains.

        Does not merge settings or emulate Cura's effective metadata semantics.
        """
        index = {f.id: f for f in self.files}
        if (type(printer) is not str or printer not in index
                or index[printer].kind != "definitions" or printer == "fdmextruder"):
            raise DefinitionError("unknown_printer")
        pending = [printer]
        selected = set()
        while pending:
            ident = pending.pop()
            if ident in selected:
                continue
            selected.add(ident)
            definition = index[ident]
            if definition.parent:
                pending.append(definition.parent)
            pending.extend(definition.trains)
        return tuple(index[ident] for ident in sorted(selected))


def _id(value: object) -> str:
    if (type(value) is not str or not _ID.fullmatch(value)
            or value.endswith((" ", "."))):
        raise DefinitionError("invalid_definition_id")
    return value


def _linked(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def _object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise DefinitionError("duplicate_json_key")
        result[key] = value
    return result


def _constant(value: str):
    raise DefinitionError("invalid_json_constant")


def _document(data: bytes) -> dict:
    try:
        doc = json.loads(data, object_pairs_hook=_object, parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, DefinitionError):
            raise
        raise DefinitionError("invalid_json") from None
    if type(doc) is not dict:
        raise DefinitionError("invalid_definition")
    if type(doc.get("version")) is not int or doc["version"] != 2:
        raise DefinitionError("unsupported_definition_schema")
    if type(doc.get("metadata", {})) is not dict:
        raise DefinitionError("invalid_metadata")
    # Expressions are opaque data, deliberately never evaluated.
    for field in ("settings", "overrides"):
        if field in doc and type(doc[field]) is not dict:
            raise DefinitionError("invalid_settings")
    return doc


def inspect_definitions(resources: Path) -> DefinitionSet:
    """Read the two flat definition directories from a private, stable staging tree.

    Caller owns the tree and prevents concurrent mutation. A later activation
    must recheck all returned SHA-256 values against the trusted file manifest.
    """
    try:
        return _inspect(resources)
    except (OSError, RuntimeError):
        raise DefinitionError("unavailable_definition_path") from None


def _inspect(resources: Path) -> DefinitionSet:
    if _linked(resources) or not resources.is_dir():
        raise DefinitionError("unsafe_resource_root")
    root = resources.resolve(strict=True)
    files = []
    seen = set()
    total = 0
    for kind in ("definitions", "extruders"):
        directory = resources / kind
        if _linked(directory) or not directory.is_dir():
            raise DefinitionError("unsafe_definition_directory")
        if directory.resolve(strict=True).parent != root:
            raise DefinitionError("unsafe_definition_directory")
        # Bound the inventory before sorting to avoid loading an unbounded list.
        paths = []
        for path in directory.iterdir():
            if len(paths) + len(files) >= MAX_FILES:
                raise DefinitionError("definition_count_limit")
            paths.append(path)
        for path in sorted(paths):
            if _linked(path) or not stat.S_ISREG(path.stat().st_mode):
                raise DefinitionError("unsafe_definition_file")
            if not path.name.endswith(".def.json"):
                raise DefinitionError("unexpected_definition_file")
            ident = _id(path.name[:-9])
            if ident.casefold() in seen:
                raise DefinitionError("duplicate_definition_id")
            seen.add(ident.casefold())
            with path.open("rb") as stream:
                data = stream.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise DefinitionError("definition_size_limit")
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise DefinitionError("definition_total_limit")
            doc = _document(data)
            parent = _id(doc["inherits"]) if "inherits" in doc else None
            metadata = doc.get("metadata", {})
            trains = metadata.get("machine_extruder_trains", {})
            if type(trains) is not dict:
                raise DefinitionError("invalid_extruder_trains")
            if trains and kind != "definitions":
                raise DefinitionError("invalid_extruder_owner")
            if any(not re.fullmatch(r"0|[1-9][0-9]{0,2}", key) for key in trains):
                raise DefinitionError("invalid_extruder_index")
            refs = tuple(_id(value) for value in trains.values())
            files.append(Definition(ident, kind, kind + "/" + path.name,
                                    hashlib.sha256(data).hexdigest(), len(data), parent, refs))
    index = {file.id: file for file in files}
    for base in ("fdmprinter", "fdmextruder"):
        if (base not in index or index[base].kind != "definitions"
                or index[base].parent is not None):
            raise DefinitionError("missing_base_definition")
    for definition in files:
        current = definition
        chain = set()
        while True:
            if current.id in chain:
                raise DefinitionError("inheritance_cycle")
            chain.add(current.id)
            if len(chain) > MAX_CHAIN:
                raise DefinitionError("inheritance_depth_limit")
            if current.parent is None:
                break
            if current.parent not in index:
                raise DefinitionError("missing_parent")
            current = index[current.parent]
        expected = ("fdmextruder" if definition.kind == "extruders"
                    or definition.id == "fdmextruder" else "fdmprinter")
        if current.id != expected:
            raise DefinitionError("wrong_base_definition")
        for train in definition.trains:
            if train not in index or (index[train].kind != "extruders" and train != "fdmextruder"):
                raise DefinitionError("missing_extruder")
    return DefinitionSet(tuple(files))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resources", type=Path)
    parser.add_argument("--printer")
    args = parser.parse_args()
    try:
        result = inspect_definitions(args.resources)
        output = result.summary()
        if args.printer is not None:
            output["dependency_files"] = [file.relative_path for file in result.dependencies(args.printer)]
        output["engine_executed"] = False
        output["slicing_accepted"] = False
        print(json.dumps(output, sort_keys=True))
    except DefinitionError as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
