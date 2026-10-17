"""Safe editing of Bambu/Orca and standard 3MF material assignments."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import PurePosixPath
from typing import Any
import xml.etree.ElementTree as ET
import zipfile

_MODEL_SETTINGS = "Metadata/model_settings.config"
_PROJECT_SETTINGS = "Metadata/project_settings.config"
_STANDARD_MODEL = "3D/3dmodel.model"
_MAX_ENTRIES = 8192
_MAX_FILE_BYTES = 512_000_000


def _safe_member(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("3MF enthält einen unsicheren Pfad")


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1].casefold()


def _namespace(element: ET.Element) -> str:
    tag = str(element.tag)
    if tag.startswith("{") and "}" in tag:
        return tag[1:].split("}", 1)[0]
    return ""


def _qualified(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}" if namespace else name


def _metadata(element: ET.Element) -> list[ET.Element]:
    return [child for child in element if _local_name(child) == "metadata"]


def _metadata_value(element: ET.Element, key: str) -> str:
    key = key.casefold()
    for child in _metadata(element):
        child_key = str(child.attrib.get("key") or child.attrib.get("name") or "").casefold()
        if child_key == key:
            return str(child.attrib.get("value") or child.text or "")
    return ""


def _set_metadata(element: ET.Element, key: str, value: str) -> None:
    key_lower = key.casefold()
    for child in _metadata(element):
        child_key = str(child.attrib.get("key") or child.attrib.get("name") or "").casefold()
        if child_key == key_lower:
            child.attrib["key"] = key
            child.attrib["value"] = value
            child.text = None
            return
    child = ET.SubElement(element, "metadata")
    child.attrib["key"] = key
    child.attrib["value"] = value


def _element_id(element: ET.Element) -> str:
    return str(
        element.attrib.get("id")
        or element.attrib.get("object_id")
        or _metadata_value(element, "object_id")
        or _metadata_value(element, "id")
        or ""
    ).strip()


def _rewrite_model_settings(data: bytes, assignments: dict[str, int]) -> tuple[bytes, int]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError("Metadata/model_settings.config ist ungültig") from exc
    changed = 0
    for element in root.iter():
        local = _local_name(element)
        if local not in {"object", "part", "volume", "mesh", "component"}:
            continue
        element_id = _element_id(element)
        if not element_id or element_id not in assignments:
            continue
        extruder = int(assignments[element_id])
        if extruder < 1 or extruder > 32:
            raise ValueError(f"Ungültiger Filament-Slot für {element_id}: {extruder}")
        _set_metadata(element, "extruder", str(extruder))
        changed += 1
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), changed


def _normalise_color(value: Any) -> str:
    raw = str(value or "#FFFFFF").strip().upper()
    if not raw.startswith("#"):
        raw = f"#{raw}"
    if len(raw) == 7:
        raw += "FF"
    return raw if len(raw) == 9 else "#FFFFFFFF"


def _normalise_colors(filaments: list[dict[str, Any]]) -> list[str]:
    return [_normalise_color(item.get("color")) for item in filaments]


def _base_materials(root: ET.Element) -> tuple[ET.Element | None, list[str]]:
    for element in root.iter():
        if _local_name(element) != "basematerials":
            continue
        colors = [
            _normalise_color(child.attrib.get("displaycolor"))
            for child in element
            if _local_name(child) == "base"
        ]
        return element, colors
    return None, []


def _mesh_face_count(element: ET.Element) -> int:
    for child in element:
        if _local_name(child) != "mesh":
            continue
        for mesh_child in child:
            if _local_name(mesh_child) == "triangles":
                return sum(1 for triangle in mesh_child if _local_name(triangle) == "triangle")
    return 0


def _match_filament_index(color: str, filament_colors: list[str], fallback: int) -> int:
    comparable = _normalise_color(color)
    for index, filament_color in enumerate(filament_colors):
        if comparable[:7] == filament_color[:7]:
            return index
    return max(0, min(fallback, max(0, len(filament_colors) - 1)))


def _rewrite_standard_model(
    data: bytes,
    filaments: list[dict[str, Any]],
) -> tuple[bytes, list[dict[str, Any]]]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError("3D/3dmodel.model ist ungültig") from exc

    namespace = _namespace(root)
    material_element, original_colors = _base_materials(root)
    filament_colors = _normalise_colors(filaments)
    objects: list[dict[str, Any]] = []

    if filaments:
        if material_element is None:
            resources = next((item for item in root if _local_name(item) == "resources"), None)
            if resources is None:
                raise ValueError("Standard-3MF enthält keine Ressourcen")
            material_element = ET.Element(_qualified(namespace, "basematerials"), {"id": "1"})
            resources.insert(0, material_element)
        material_id = str(material_element.attrib.get("id") or "1")
        for child in list(material_element):
            if _local_name(child) == "base":
                material_element.remove(child)
        for index, item in enumerate(filaments):
            ET.SubElement(
                material_element,
                _qualified(namespace, "base"),
                {
                    "name": str(item.get("name") or f"Filament {index + 1}"),
                    "displaycolor": filament_colors[index],
                },
            )
    else:
        material_id = str(material_element.attrib.get("id") or "1") if material_element is not None else "1"

    object_order = 0
    for element in root.iter():
        if _local_name(element) != "object":
            continue
        if not any(_local_name(child) == "mesh" for child in element):
            continue
        object_id = str(element.attrib.get("id") or "").strip()
        if not object_id:
            continue
        original_pindex = int(str(element.attrib.get("pindex") or object_order) or object_order)
        source_color = original_colors[original_pindex] if 0 <= original_pindex < len(original_colors) else "#FFFFFFFF"
        filament_index = _match_filament_index(source_color, filament_colors, original_pindex) if filaments else original_pindex
        if filaments:
            element.attrib["pid"] = material_id
            element.attrib["pindex"] = str(filament_index)
        objects.append({
            "id": object_id,
            "name": str(element.attrib.get("name") or f"Objekt {object_id}"),
            "extruder": filament_index + 1,
            "face_count": _mesh_face_count(element),
        })
        object_order += 1

    return ET.tostring(root, encoding="utf-8", xml_declaration=True), objects



def _validate_standard_triangle_materials(data: bytes, filaments: list[dict[str, Any]]) -> None:
    """Reject malformed per-triangle base-material references before slicer handoff."""
    if not filaments:
        return
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError("3D/3dmodel.model ist ungültig") from exc
    material_element, _colors = _base_materials(root)
    material_id = str(material_element.attrib.get("id") or "1") if material_element is not None else "1"
    maximum = len(filaments) - 1
    for element in root.iter():
        if _local_name(element) != "triangle" or "p1" not in element.attrib:
            continue
        if str(element.attrib.get("pid") or "") != material_id:
            raise ValueError("Bemalte 3MF-Fläche verweist auf eine unbekannte Materialgruppe")
        for key in ("p1", "p2", "p3"):
            if key not in element.attrib:
                continue
            try:
                index = int(str(element.attrib[key]))
            except (TypeError, ValueError) as exc:
                raise ValueError("Bemalte 3MF-Fläche enthält einen ungültigen Materialindex") from exc
            if index < 0 or index > maximum:
                raise ValueError("Bemalte 3MF-Fläche verweist auf kein aktives Filament")


def _standard_model_settings(objects: list[dict[str, Any]]) -> bytes:
    root = ET.Element("config")
    plate = ET.SubElement(root, "plate")
    _set_metadata(plate, "plater_id", "1")
    _set_metadata(plate, "plater_name", "")
    _set_metadata(plate, "locked", "false")
    _set_metadata(plate, "filament_map_mode", "Auto For Flush")

    for index, item in enumerate(objects):
        object_id = str(item["id"])
        extruder = int(item["extruder"])
        face_count = int(item["face_count"])
        name = str(item["name"])

        object_element = ET.Element("object", {"id": object_id})
        _set_metadata(object_element, "name", name)
        _set_metadata(object_element, "extruder", str(extruder))
        ET.SubElement(object_element, "metadata", {"face_count": str(face_count)})

        part = ET.SubElement(object_element, "part", {"id": object_id, "subtype": "normal_part"})
        _set_metadata(part, "name", name)
        _set_metadata(part, "matrix", "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1")
        _set_metadata(part, "extruder", str(extruder))
        ET.SubElement(
            part,
            "mesh_stat",
            {
                "face_count": str(face_count),
                "edges_fixed": "0",
                "degenerate_facets": "0",
                "facets_removed": "0",
                "facets_reversed": "0",
                "backwards_edges": "0",
            },
        )
        root.insert(index, object_element)

        instance = ET.SubElement(plate, "model_instance")
        _set_metadata(instance, "object_id", object_id)
        _set_metadata(instance, "instance_id", "0")
        _set_metadata(instance, "identify_id", str(index + 1))

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _valid_standard_model(data: bytes) -> bool:
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return False
    object_ids = {
        str(element.attrib.get("id") or "")
        for element in root.iter()
        if _local_name(element) == "object"
        and any(_local_name(child) == "mesh" for child in element)
    }
    build_ids = {
        str(element.attrib.get("objectid") or "")
        for element in root.iter()
        if _local_name(element) == "item"
    }
    return bool(object_ids and object_ids.intersection(build_ids))


def _rewrite_project_settings(
    data: bytes | None,
    filaments: list[dict[str, Any]],
    purge: dict[str, Any],
) -> bytes:
    payload: dict[str, Any]
    if data:
        try:
            parsed = json.loads(data.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Metadata/project_settings.config ist ungültig") from exc
        payload = parsed if isinstance(parsed, dict) else {}
    else:
        payload = {}

    if filaments:
        payload["filament_colour"] = _normalise_colors(filaments)
        payload["filament_type"] = [str(item.get("material") or "PLA") for item in filaments]
        payload["filament_settings_id"] = [str(item.get("name") or f"Filament {index + 1}") for index, item in enumerate(filaments)]

    if purge:
        enabled = bool(purge.get("enabled"))
        payload["enable_prime_tower"] = "1" if enabled else "0"
        if purge.get("width_mm") is not None:
            payload["prime_tower_width"] = str(float(purge["width_mm"]))
        if purge.get("brim_width_mm") is not None:
            payload["prime_tower_brim_width"] = str(float(purge["brim_width_mm"]))
        if purge.get("position_x") is not None:
            payload["wipe_tower_x"] = str(float(purge["position_x"]))
        if purge.get("position_y") is not None:
            payload["wipe_tower_y"] = str(float(purge["position_y"]))
        if purge.get("flush_multiplier") is not None:
            payload["flush_multiplier"] = str(float(purge["flush_multiplier"]))
        if isinstance(purge.get("flush_volumes_matrix"), list):
            payload["flush_volumes_matrix"] = purge["flush_volumes_matrix"]
        if isinstance(purge.get("flush_volumes_vector"), list):
            payload["flush_volumes_vector"] = purge["flush_volumes_vector"]

    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def apply_material_plan(
    filename: str,
    data: bytes,
    plan: dict[str, Any] | None,
) -> tuple[str, bytes, dict[str, Any]]:
    """Return a rewritten project 3MF and a summary of applied changes."""
    if not plan or not filename.casefold().endswith(".3mf"):
        return filename, data, {"applied": False, "assignment_count": 0}

    raw_assignments = plan.get("assignments")
    assignments = {
        str(key): int(value)
        for key, value in raw_assignments.items()
        if str(key).strip()
    } if isinstance(raw_assignments, dict) else {}
    filaments = plan.get("filaments") if isinstance(plan.get("filaments"), list) else []
    purge = plan.get("purge_tower") if isinstance(plan.get("purge_tower"), dict) else {}

    source = BytesIO(data)
    output = BytesIO()
    changed = 0
    found_model_settings = False
    found_project_settings = False
    found_standard_model = False
    generated_model_settings: bytes | None = None
    standard_objects: list[dict[str, Any]] = []

    try:
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            if not infos or len(infos) > _MAX_ENTRIES:
                raise ValueError("3MF enthält eine ungültige Anzahl von Dateien")
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target:
                for info in infos:
                    _safe_member(info.filename)
                    if info.file_size > _MAX_FILE_BYTES:
                        raise ValueError(f"3MF-Datei ist zu groß: {info.filename}")
                    content = archive.read(info)
                    canonical = info.filename.replace("\\", "/")
                    if canonical.casefold() == _MODEL_SETTINGS.casefold():
                        found_model_settings = True
                        content, changed = _rewrite_model_settings(content, assignments)
                    elif canonical.casefold() == _STANDARD_MODEL.casefold():
                        found_standard_model = _valid_standard_model(content)
                        if found_standard_model and filaments:
                            content, standard_objects = _rewrite_standard_model(content, filaments)
                            _validate_standard_triangle_materials(content, filaments)
                            generated_model_settings = _standard_model_settings(standard_objects)
                            changed = len(standard_objects)
                    elif canonical.casefold() == _PROJECT_SETTINGS.casefold():
                        found_project_settings = True
                        content = _rewrite_project_settings(content, filaments, purge)
                    replacement = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                    replacement.compress_type = zipfile.ZIP_DEFLATED
                    replacement.external_attr = info.external_attr
                    replacement.comment = info.comment
                    target.writestr(replacement, content)
                if generated_model_settings is not None and not found_model_settings:
                    target.writestr(_MODEL_SETTINGS, generated_model_settings)
                if (filaments or purge) and not found_project_settings:
                    target.writestr(_PROJECT_SETTINGS, _rewrite_project_settings(None, filaments, purge))
    except zipfile.BadZipFile as exc:
        raise ValueError("Die 3MF-Datei ist kein gültiges Archiv") from exc

    if assignments:
        if found_model_settings:
            if changed == 0:
                raise ValueError("Keine der gewählten Objekt-/Teil-IDs wurde im Bambu-3MF gefunden")
        elif found_standard_model:
            if changed == 0:
                raise ValueError("Standard-3MF enthält keine zuweisbaren Modellobjekte")
        else:
            raise ValueError("Die 3MF enthält keine Bambu-Modellzuordnungen und kein gültiges Standard-3MF-Modell")

    stem = PurePosixPath(filename).stem
    rewritten_name = f"{stem}-studio-multimaterial.3mf"
    return rewritten_name, output.getvalue(), {
        "applied": True,
        "assignment_count": changed,
        "filament_count": len(filaments),
        "purge_tower_enabled": bool(purge.get("enabled")),
    }
