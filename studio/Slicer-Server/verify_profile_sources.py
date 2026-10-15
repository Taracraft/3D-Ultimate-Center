"""Read-only offline verification of selected upstream profile sources."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat

BUNDLE_NAME = "PROFILE_SOURCE_BUNDLE.json"
BUNDLE_SHA256 = "b7ecec0be50f76e4bb4ed85df68f88f28bc34ff34f42a754a3cbdddf9796fa1f"
UPSTREAM_COMMIT = "42d319c6692fa8e64790fddf0cdaafd2a4254bcc"
LICENSE_SHA256 = "57c8ff33c9c0cfc3ef00e650a1cc910d7ee479a8bc509f6c9209a7c2a11399d6"
MAX_BYTES = 2 * 1024 * 1024
COMPONENT = "deploy/homeassistant/custom_components/ultimate_3d_studio"

class ProfileSourceError(ValueError):
    pass

def require(condition, code):
    if not condition:
        raise ProfileSourceError(code)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def _objects(bundle):
    require(isinstance(bundle, dict), "invalid_source_bundle")
    require(bundle.get("schema") == 1 and bundle.get("commit") == UPSTREAM_COMMIT,
            "invalid_source_revision")
    require(bundle.get("publication_approved") is False
            and bundle.get("engine_included") is False, "source_release_flag_rejected")
    require(bundle.get("license_sha256") == LICENSE_SHA256, "source_license_mismatch")
    rows = bundle.get("files")
    require(isinstance(rows, list) and len(rows) == 118, "source_file_set_mismatch")
    objects = {}
    for row in rows:
        require(isinstance(row, dict), "invalid_source_row")
        name = row.get("path")
        require(isinstance(name, str) and "\\" not in name, "unsafe_source_path")
        path = PurePosixPath(name)
        require(not path.is_absolute() and ".." not in path.parts
                and path.as_posix() == name
                and name.startswith("resources/profiles/BBL/")
                and path.suffix == ".json", "unsafe_source_path")
        require(name not in objects, "duplicate_source_path")
        text = row.get("content")
        require(isinstance(text, str), "invalid_source_content")
        data = text.encode("utf-8")
        require(len(data) <= MAX_BYTES and type(row.get("bytes")) is int
                and len(data) == row["bytes"]
                and digest(data) == row.get("sha256"), "upstream_source_digest_mismatch")
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        require(blob == row.get("git_blob"), "upstream_git_blob_mismatch")
        value = json.loads(text)
        require(isinstance(value, dict), "invalid_profile_object")
        objects[name] = value
    return objects

def load_bundle(data):
    require(len(data) <= MAX_BYTES and digest(data) == BUNDLE_SHA256,
            "profile_source_bundle_digest_mismatch")
    bundle = json.loads(data.decode("utf-8"))
    objects = _objects(bundle)
    specs = bundle.get("profiles")
    require(isinstance(specs, list) and len(specs) == 54, "profile_selection_mismatch")
    require(len({(s["section"], s["name"]) for s in specs}) == 54,
            "profile_selection_mismatch")
    require(all(s["path"] in objects for s in specs), "missing_selected_source")
    return bundle, objects

def _find(objects, directory, name):
    require(isinstance(name, str) and name and "/" not in name and "\\" not in name
            and name not in {".", ".."}, "invalid_inherited_profile_name")
    direct = directory + "/" + name + ".json"
    if direct in objects:
        return direct
    matches = [p for p in objects if p.startswith(directory + "/")
               and PurePosixPath(p).name == name + ".json"]
    require(len(matches) == 1, "inherited_source_missing_or_ambiguous")
    return matches[0]

def resolve(objects, path, metadata, includes_after_own=False, active=()):
    require(path in objects, "inherited_source_missing_or_ambiguous")
    require(path not in active and len(active) < 64, "cyclic_or_deep_profile_inheritance")
    value = objects[path]
    directory = str(PurePosixPath(path).parent)
    result = {}
    parent = value.get("inherits") or ""
    require(isinstance(parent, str), "invalid_inherited_profile_name")
    if parent.strip():
        result.update(resolve(objects, _find(objects, directory, parent.strip()),
                              metadata, includes_after_own, active + (path,)))
    includes = value.get("include", [])
    require(isinstance(includes, list), "invalid_profile_include")
    own = {k: v for k, v in value.items() if k not in {"inherits", "include"}}
    if includes_after_own:
        result.update(own)
    for name in includes:
        included = objects[_find(objects, directory, name)]
        result.update({k: v for k, v in included.items() if k not in metadata})
    if not includes_after_own:
        result.update(own)
    return result

def number(value):
    require(not isinstance(value, bool), "selected_value_mismatch")
    result = float(value)
    require(math.isfinite(result), "selected_value_mismatch")
    return result

def verify_bundle(data, a1, h2s):
    bundle, objects = load_bundle(data)
    sections = {"a1_filaments": a1["profiles"], "h2s_filaments": h2s["filaments"],
                "h2s_machines": h2s["machines"], "h2s_processes": h2s["processes"]}
    metadata = bundle["resolver_metadata"]
    resolved = {}
    projections = 0
    for spec in bundle["profiles"]:
        machine = spec["section"] == "h2s_machines"
        value = resolve(objects, spec["path"], set(metadata["machine" if machine else "other"]),
                        includes_after_own=machine)
        fingerprint = digest(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                        separators=(",", ":")).encode("utf-8"))
        require(fingerprint == spec["resolved_sha256"], "resolved_profile_digest_mismatch")
        local = sections[spec["section"]][spec["name"]]
        if "filaments" in spec["section"]:
            require(all(value.get(k) == v for k, v in local["settings"].items()),
                    "selected_value_mismatch")
            require(local.get("compatible_printers", value.get("compatible_printers"))
                    == value.get("compatible_printers"), "selected_value_mismatch")
        elif machine:
            for local_key, native_key in [("min_layer", "min_layer_height"),
                                          ("max_layer", "max_layer_height")]:
                native = value[native_key]
                values = native if isinstance(native, list) else [native]
                require(bool(values) and all(number(local[local_key]) == number(v) for v in values),
                        "selected_value_mismatch")
        else:
            for key in ["layer_height", "outer_wall_speed", "inner_wall_speed"]:
                native = value[key]
                if isinstance(native, list):
                    require(bool(native), "selected_value_mismatch")
                    native = native[0]
                require(number(local[key]) == number(native), "selected_value_mismatch")
                projections += 1
        resolved[spec["path"]] = value
    roundtrips = 0
    for part, field, marker, sound in [
        ("gcode_1", "machine_start_gcode", ";@U3D_START_SOUND@", "start_sound"),
        ("gcode_2", "machine_end_gcode", ";@U3D_END_SOUND@", "end_sound"),
    ]:
        text = h2s["parts"][part]
        require(text.count(marker + "\n") == 1, "sound_marker_mismatch")
        reconstructed = text.replace(marker + "\n", h2s["parts"][sound])
        for path, value in resolved.items():
            if "/machine/" in path:
                require(reconstructed == value[field], "sound_roundtrip_mismatch")
                roundtrips += 1
    require(projections == 12 and roundtrips == 8, "profile_selection_mismatch")
    return {"source_files": len(objects), "verified_profiles": len(bundle["profiles"]),
            "process_projections": projections, "gcode_sound_roundtrips": roundtrips,
            "source_bundle_sha256": digest(data), "upstream_commit": UPSTREAM_COMMIT,
            "engine_executed": False, "worker_started": False, "publication_approved": False}

def read_regular(root, relative):
    root = Path(root).absolute()
    path = root
    for parent in [root, *root.parents]:
        require(not parent.is_symlink() and not getattr(parent, "is_junction", lambda: False)(),
                "linked_profile_source")
    for part in PurePosixPath(relative).parts:
        path = path / part
        require(not path.is_symlink() and not getattr(path, "is_junction", lambda: False)(),
                "linked_profile_source")
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
            "invalid_profile_source_file")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require(os.path.samestat(before, opened), "profile_source_changed")
        data = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    final = path.stat()
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    require(len(data) == before.st_size and identity(before) == identity(final)
            and identity(opened) == identity(after), "profile_source_changed")
    return data

def verify(root, source_tree=False):
    bundle_prefix = "Slicer-Server/" if source_tree else ""
    defaults_prefix = COMPONENT + "/" if source_tree else "payload/"
    data = read_regular(root, bundle_prefix + BUNDLE_NAME)
    license_data = read_regular(root, bundle_prefix + "licenses/AGPL-BambuStudio.txt")
    require(digest(license_data) == LICENSE_SHA256, "source_license_mismatch")
    a1 = json.loads(read_regular(root, defaults_prefix + "native_filament_defaults.json").decode("utf-8-sig"))
    h2s = json.loads(read_regular(root, defaults_prefix + "h2s_native_defaults.json").decode("utf-8-sig"))
    return verify_bundle(data, a1, h2s)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--source-root", type=Path)
    group.add_argument("--context-root", type=Path)
    args = parser.parse_args(argv)
    try:
        root = args.source_root or args.context_root or Path(__file__).resolve().parent
        print(json.dumps(verify(root, source_tree=args.source_root is not None), sort_keys=True))
        return 0
    except (ProfileSourceError, OSError, ValueError, KeyError, TypeError) as exc:
        code = str(exc) if isinstance(exc, ProfileSourceError) else type(exc).__name__
        parser.exit(1, "Offline profile source verification rejected: " + code + "\n")

if __name__ == "__main__":
    raise SystemExit(main())
