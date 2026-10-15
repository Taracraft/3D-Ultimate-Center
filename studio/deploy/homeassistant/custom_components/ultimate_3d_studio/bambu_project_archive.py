"""Build and enrich display-ready Bambu G-code 3MF artifacts."""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import math
from pathlib import Path, PurePosixPath
import re
import struct
from typing import Any, Iterator
import xml.etree.ElementTree as ET
import zipfile
import zlib

_COORD = re.compile(
    r"(?:^|\s)([XYE])(-?(?:\d+(?:\.\d*)?|\.\d+))",
    re.IGNORECASE,
)
_TOOL = re.compile(r"^T(\d+)$", re.IGNORECASE)
_M620 = re.compile(r"^M620\s+S(\d+)A", re.IGNORECASE)
_UUID_PREFIX = re.compile(r"^studio-[0-9a-f]{10,32}-", re.IGNORECASE)
_PLATE_PREFIX = re.compile(r"^plate[-_ ]*\d+[-_ ]+", re.IGNORECASE)
_GENERIC_NAME = re.compile(
    r"^(?:projekt|project|druckplatte|plate|build plate|druckauftrag|print job)\s*\d*$",
    re.IGNORECASE,
)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9ÄÖÜäöüß._ +()-]+")
_OBJECT_COMMENT = re.compile(
    r"^\s*;\s*(?:printing\s+object|object(?:\s+name)?|model(?:\s+name)?|source(?:\s+file)?)\s*[:=]\s*(.+?)\s*$",
    re.IGNORECASE,
)
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_MAX_RENDERED_SEGMENTS = 240_000
_MAX_NAME_SCAN_BYTES = 8 * 1024 * 1024
_MAX_NATIVE_ARCHIVE_FILES = 10_000
_MAX_NATIVE_UNCOMPRESSED_BYTES = 1_800_000_000
_MAX_EMBEDDED_GCODE_BYTES = 600_000_000
_CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
_CONTENT_TYPES_NS = (
    "http://schemas.openxmlformats.org/package/2006/content-types"
)
_PREVIEW_PATHS = (
    "Metadata/plate_1.png",
    "Metadata/plate_1_small.png",
    "Metadata/plate_no_light_1.png",
    "Metadata/pick_1.png",
)
_PALETTE = (
    (69, 224, 135, 255),
    (50, 214, 255, 255),
    (255, 209, 102, 255),
    (255, 112, 112, 255),
    (180, 139, 255, 255),
    (255, 179, 71, 255),
)


def safe_project_name(
    value: object,
    fallback: str = "Druckauftrag",
) -> str:
    """Return a short, human-readable and printer-safe project name."""
    raw = Path(str(value or fallback)).name.strip()
    lowered = raw.casefold()
    for suffix in (".gcode.3mf", ".3mf", ".gcode", ".stl"):
        if lowered.endswith(suffix):
            raw = raw[: -len(suffix)]
            break
    raw = _UUID_PREFIX.sub("", raw)
    raw = _PLATE_PREFIX.sub("", raw)
    raw = raw.replace("_", " ")
    raw = re.sub(r"\s+", " ", raw).strip(" .-_")
    raw = _SAFE_NAME.sub("_", raw).strip(" .-_")
    if not raw or re.fullmatch(r"studio-[0-9a-f]+", raw, re.IGNORECASE):
        raw = _SAFE_NAME.sub(
            "_",
            str(fallback or "Druckauftrag"),
        ).strip(" .-_")
    return (raw or "Druckauftrag")[:120]


def _useful_name(value: object, fallback: str = "") -> str:
    name = safe_project_name(value, fallback or "Druckauftrag")
    if _GENERIC_NAME.fullmatch(name):
        return ""
    return name


def project_name_from_3mf(data: bytes, fallback: str) -> str:
    """Resolve the model name from actual 3MF object metadata."""
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            root = ET.fromstring(archive.read("3D/3dmodel.model"))
    except (KeyError, OSError, zipfile.BadZipFile, ET.ParseError):
        return safe_project_name(fallback)

    namespace = {"m": _CORE_NS}
    names: list[str] = []
    for item in root.findall("m:resources/m:object", namespace):
        if item.find("m:mesh", namespace) is None:
            continue
        name = _useful_name(item.attrib.get("name"), "")
        if name and name not in names:
            names.append(name)

    if names:
        if len(names) == 1:
            return names[0]
        return safe_project_name(f"{names[0]} +{len(names) - 1} Teile")

    for metadata in root.findall("m:metadata", namespace):
        if str(metadata.attrib.get("name") or "").casefold() != "title":
            continue
        title = _useful_name(metadata.text, "")
        if title:
            return title
    return safe_project_name(fallback)


def project_name_from_gcode(gcode: bytes, fallback: str) -> str:
    """Resolve a model name from bounded G-code object comments."""
    scanned = 0
    names: list[str] = []
    for raw_line in BytesIO(gcode):
        scanned += len(raw_line)
        if scanned > _MAX_NAME_SCAN_BYTES:
            break
        line = raw_line.decode("utf-8", errors="ignore")
        match = _OBJECT_COMMENT.match(line)
        if not match:
            continue
        value = match.group(1).split(" id:", 1)[0].strip()
        name = _useful_name(value, "")
        if name and name not in names:
            names.append(name)
        if len(names) >= 8:
            break
    if not names:
        return safe_project_name(fallback)
    if len(names) == 1:
        return names[0]
    return safe_project_name(f"{names[0]} +{len(names) - 1} Teile")


def project_name_from_server_payload(
    payload: dict[str, Any],
    fallback: str,
    gcode: bytes | None = None,
) -> str:
    """Resolve the display name from server data and rendered G-code."""
    job = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    target = (
        job.get("target_printer")
        if isinstance(job.get("target_printer"), dict)
        else {}
    )
    candidates = (
        job.get("project_name"),
        job.get("display_name"),
        target.get("project_name"),
        job.get("input_file"),
        job.get("studio_plate_name"),
        payload.get("download_name"),
    )
    for value in candidates:
        name = _useful_name(value, "")
        if name:
            return name
    if gcode:
        return project_name_from_gcode(gcode, fallback)
    return safe_project_name(fallback, "Druckauftrag")


def _extrusion_segments(
    gcode: bytes,
) -> Iterator[tuple[float, float, float, float, int]]:
    x = y = e = 0.0
    absolute_xyz = True
    absolute_e = True
    tool = 0

    for raw_line in BytesIO(gcode):
        line = (
            raw_line.decode("utf-8", errors="ignore")
            .split(";", 1)[0]
            .strip()
        )
        if not line:
            continue

        upper = line.upper()
        if upper == "G90":
            absolute_xyz = True
            continue
        if upper == "G91":
            absolute_xyz = False
            continue
        if upper == "M82":
            absolute_e = True
            continue
        if upper == "M83":
            absolute_e = False
            continue

        tool_match = _TOOL.match(upper) or _M620.match(upper)
        if tool_match:
            tool = max(0, int(tool_match.group(1)))
            continue

        values = {
            axis.upper(): float(value)
            for axis, value in _COORD.findall(line)
        }
        if upper.startswith("G92"):
            x = values.get("X", x)
            y = values.get("Y", y)
            e = values.get("E", e)
            continue

        command = upper.split(maxsplit=1)[0]
        if command not in {
            "G0",
            "G00",
            "G1",
            "G01",
            "G2",
            "G02",
            "G3",
            "G03",
        }:
            continue

        nx = values.get("X", x if absolute_xyz else 0.0)
        ny = values.get("Y", y if absolute_xyz else 0.0)
        raw_e = values.get("E", e if absolute_e else 0.0)
        if not absolute_xyz:
            nx += x
            ny += y
        ne = raw_e if absolute_e else e + raw_e
        extrusion = ne - e if absolute_e else raw_e

        if (
            extrusion > 0.000001
            and math.hypot(nx - x, ny - y) > 0.000001
        ):
            yield x, y, nx, ny, tool
        x, y, e = nx, ny, ne


def _set_pixel(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    color: tuple[int, int, int, int],
    radius: int,
) -> None:
    for yy in range(max(0, y - radius), min(height, y + radius + 1)):
        for xx in range(max(0, x - radius), min(width, x + radius + 1)):
            offset = (yy * width + xx) * 4
            pixels[offset : offset + 4] = bytes(color)


def _draw_line(
    pixels: bytearray,
    width: int,
    height: int,
    start: tuple[int, int],
    end: tuple[int, int],
    color: tuple[int, int, int, int],
    radius: int,
) -> None:
    x0, y0 = start
    x1, y1 = end
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for step in range(steps + 1):
        amount = step / steps
        x = round(x0 + (x1 - x0) * amount)
        y = round(y0 + (y1 - y0) * amount)
        _set_pixel(pixels, width, height, x, y, color, radius)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def _encode_png(
    width: int,
    height: int,
    pixels: bytearray,
) -> bytes:
    scanlines = bytearray()
    row_bytes = width * 4
    for row in range(height):
        scanlines.append(0)
        start = row * row_bytes
        scanlines.extend(pixels[start : start + row_bytes])
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        _PNG_SIGNATURE
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(scanlines), 9))
        + _png_chunk(b"IEND", b"")
    )


def render_gcode_thumbnail(
    gcode: bytes,
    width: int,
    height: int,
) -> bytes:
    """Render a bounded top view directly from positive-extrusion moves."""
    minimum_x = minimum_y = math.inf
    maximum_x = maximum_y = -math.inf
    segment_count = 0

    for x1, y1, x2, y2, _tool in _extrusion_segments(gcode):
        minimum_x = min(minimum_x, x1, x2)
        minimum_y = min(minimum_y, y1, y2)
        maximum_x = max(maximum_x, x1, x2)
        maximum_y = max(maximum_y, y1, y2)
        segment_count += 1

    pixels = bytearray(width * height * 4)
    if segment_count <= 0 or not all(
        math.isfinite(value)
        for value in (minimum_x, minimum_y, maximum_x, maximum_y)
    ):
        center = (width // 2, height // 2)
        _draw_line(
            pixels,
            width,
            height,
            (center[0] - 8, center[1]),
            (center[0] + 8, center[1]),
            _PALETTE[0],
            1,
        )
        _draw_line(
            pixels,
            width,
            height,
            (center[0], center[1] - 8),
            (center[0], center[1] + 8),
            _PALETTE[0],
            1,
        )
        return _encode_png(width, height, pixels)

    span_x = max(0.001, maximum_x - minimum_x)
    span_y = max(0.001, maximum_y - minimum_y)
    margin = max(4, round(min(width, height) * 0.08))
    drawable_width = max(1, width - margin * 2)
    drawable_height = max(1, height - margin * 2)
    scale = min(drawable_width / span_x, drawable_height / span_y)
    offset_x = (width - span_x * scale) / 2 - minimum_x * scale
    offset_y = (height - span_y * scale) / 2 + maximum_y * scale
    stride = max(
        1,
        math.ceil(segment_count / _MAX_RENDERED_SEGMENTS),
    )
    radius = 1 if min(width, height) >= 256 else 0

    for index, (x1, y1, x2, y2, tool) in enumerate(
        _extrusion_segments(gcode)
    ):
        if index % stride:
            continue
        start = (
            round(x1 * scale + offset_x),
            round(offset_y - y1 * scale),
        )
        end = (
            round(x2 * scale + offset_x),
            round(offset_y - y2 * scale),
        )
        _draw_line(
            pixels,
            width,
            height,
            start,
            end,
            _PALETTE[tool % len(_PALETTE)],
            radius,
        )
    return _encode_png(width, height, pixels)


def _write_entry(
    archive: zipfile.ZipFile,
    name: str,
    data: bytes,
) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data)


def _validated_native_entries(
    archive: zipfile.ZipFile,
) -> tuple[list[zipfile.ZipInfo], zipfile.ZipInfo]:
    infos = archive.infolist()
    if not infos or len(infos) > _MAX_NATIVE_ARCHIVE_FILES:
        raise ValueError("Das native Bambu-Archiv enthält eine ungültige Dateianzahl.")

    total = 0
    gcode_entries: list[zipfile.ZipInfo] = []
    for info in infos:
        normalized = info.filename.replace("\\", "/")
        pure = PurePosixPath(normalized)
        if pure.is_absolute() or ".." in pure.parts:
            raise ValueError(f"Unsicherer Pfad im nativen Bambu-Archiv: {info.filename}")
        total += int(info.file_size)
        if total > _MAX_NATIVE_UNCOMPRESSED_BYTES:
            raise ValueError("Das native Bambu-Archiv ist entpackt unerwartet groß.")
        lowered = normalized.casefold()
        if (
            lowered.startswith("metadata/plate_")
            and lowered.endswith(".gcode")
        ):
            gcode_entries.append(info)

    if len(gcode_entries) != 1:
        raise ValueError(
            "Das native Bambu-Archiv muss genau eine Metadata/plate_*.gcode-Datei enthalten."
        )
    gcode_info = gcode_entries[0]
    if (
        gcode_info.file_size <= 0
        or gcode_info.file_size > _MAX_EMBEDDED_GCODE_BYTES
    ):
        raise ValueError("Der eingebettete native G-Code hat eine ungültige Größe.")
    return infos, gcode_info


def gcode_from_bambu_project_artifact(data: bytes) -> bytes:
    """Return raw G-code from either a native G-code 3MF or legacy G-code."""
    if not data:
        raise ValueError("Der native Slicer lieferte kein Artefakt.")
    if not zipfile.is_zipfile(BytesIO(data)):
        return data
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            _infos, gcode_info = _validated_native_entries(archive)
            return archive.read(gcode_info)
    except zipfile.BadZipFile as exc:
        raise ValueError("Das native Bambu-Artefakt ist kein gültiges ZIP/3MF.") from exc


def _content_types_with_png(data: bytes) -> bytes:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError("[Content_Types].xml des nativen Archivs ist ungültig.") from exc

    namespace = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""
    tag = f"{{{namespace}}}Default" if namespace else "Default"
    for child in root.findall(tag):
        if str(child.attrib.get("Extension") or "").casefold() == "png":
            return data
    ET.SubElement(
        root,
        tag,
        {"Extension": "png", "ContentType": "image/png"},
    )
    if namespace:
        ET.register_namespace("", namespace)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def enrich_bambu_project_archive(
    project_name: str,
    native_project: bytes,
    fallback_name: str,
) -> tuple[bytes, str, str]:
    """Preserve native Bambu metadata and add display preview PNG files."""
    if not zipfile.is_zipfile(BytesIO(native_project)):
        raise ValueError("Das native Bambu-Projekt ist kein gültiges ZIP/3MF.")

    display_name = safe_project_name(project_name, fallback_name)
    source_buffer = BytesIO(native_project)
    output = BytesIO()

    try:
        with zipfile.ZipFile(source_buffer) as source:
            infos, gcode_info = _validated_native_entries(source)
            gcode = source.read(gcode_info)
            large_preview = render_gcode_thumbnail(gcode, 512, 512)
            small_preview = render_gcode_thumbnail(gcode, 128, 128)
            preview_names = {item.casefold() for item in _PREVIEW_PATHS}
            content_types_seen = False

            with zipfile.ZipFile(
                output,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as target:
                for info in infos:
                    normalized = info.filename.replace("\\", "/")
                    if normalized.casefold() in preview_names:
                        continue
                    payload = source.read(info)
                    if normalized == "[Content_Types].xml":
                        payload = _content_types_with_png(payload)
                        content_types_seen = True
                    copied = zipfile.ZipInfo(
                        normalized,
                        date_time=info.date_time,
                    )
                    copied.compress_type = info.compress_type
                    copied.comment = info.comment
                    copied.extra = info.extra
                    copied.internal_attr = info.internal_attr
                    copied.external_attr = info.external_attr
                    copied.create_system = info.create_system
                    copied.flag_bits = info.flag_bits
                    target.writestr(copied, payload)

                if not content_types_seen:
                    raise ValueError(
                        "Das native Bambu-Archiv enthält keine [Content_Types].xml."
                    )
                _write_entry(target, "Metadata/plate_1.png", large_preview)
                _write_entry(
                    target,
                    "Metadata/plate_1_small.png",
                    small_preview,
                )
                _write_entry(
                    target,
                    "Metadata/plate_no_light_1.png",
                    large_preview,
                )
                _write_entry(target, "Metadata/pick_1.png", large_preview)
    except zipfile.BadZipFile as exc:
        raise ValueError("Das native Bambu-Projekt ist beschädigt.") from exc

    content = output.getvalue()
    filename = f"{display_name}.gcode.3mf"
    return content, filename, sha256(content).hexdigest()


def build_bambu_project_archive(
    project_name: str,
    gcode: bytes,
    fallback_name: str,
) -> tuple[bytes, str, str]:
    """Return a deterministic display-ready legacy project archive."""
    if not gcode:
        raise ValueError("Der native Slicer lieferte keinen G-Code.")

    display_name = safe_project_name(project_name, fallback_name)
    large_preview = render_gcode_thumbnail(gcode, 512, 512)
    small_preview = render_gcode_thumbnail(gcode, 128, 128)
    output = BytesIO()

    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        _write_entry(archive, "Metadata/plate_1.gcode", gcode)
        _write_entry(archive, "Metadata/plate_1.png", large_preview)
        _write_entry(
            archive,
            "Metadata/plate_1_small.png",
            small_preview,
        )
        _write_entry(
            archive,
            "Metadata/plate_no_light_1.png",
            large_preview,
        )
        _write_entry(archive, "Metadata/pick_1.png", large_preview)

    content = output.getvalue()
    filename = f"{display_name}.gcode.3mf"
    return content, filename, sha256(content).hexdigest()


def prepare_bambu_project_artifact(
    project_name: str,
    artifact: bytes,
    fallback_name: str,
) -> tuple[bytes, str, str]:
    """Enrich native 3MF output or package legacy raw G-code."""
    if zipfile.is_zipfile(BytesIO(artifact)):
        return enrich_bambu_project_archive(
            project_name,
            artifact,
            fallback_name,
        )
    return build_bambu_project_archive(
        project_name,
        artifact,
        fallback_name,
    )
