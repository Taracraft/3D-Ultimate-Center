"""Standalone Bambu Lab foundation for 3D-Printer Control Center.

No dependency on external Bambu Home Assistant integrations.
External integrations are used only as public technical references for model
capabilities, MQTT field names, AMS structure, camera modes and future v5
Studio/Slicer work.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class BambuPrinterFamily(str, Enum):
    X1 = "x1"
    P1 = "p1"
    A1 = "a1"
    H2 = "h2"
    UNKNOWN = "unknown"


class BambuCameraKind(str, Enum):
    NONE = "none"
    RTSPS = "rtsps"
    RTSP = "rtsp"
    SNAPSHOT_IMAGE = "snapshot_image"
    CLOUD_TUNNEL = "cloud_tunnel"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BambuCameraProfile:
    family: BambuPrinterFamily
    supported_kinds: tuple[BambuCameraKind, ...]
    default_port: int | None
    default_path: str | None
    username: str
    requires_access_code: bool
    requires_lan_liveview: bool
    requires_developer_lan_mode: bool
    preferred_snapshot_fallback: bool
    notes: str


@dataclass(frozen=True)
class BambuModelCapabilities:
    family: BambuPrinterFamily
    model_keys: tuple[str, ...]
    supports_ams: bool
    supports_ams_lite: bool
    supports_ams_2_pro: bool
    supports_ams_ht: bool
    supports_chamber_temperature: bool
    supports_chamber_fan: bool
    supports_aux_fan: bool
    supports_dual_nozzle: bool
    supports_hotend_rack: bool
    supports_sdcard_legacy_url: bool
    camera_profile: BambuCameraProfile


CAMERA_PROFILES: dict[BambuPrinterFamily, BambuCameraProfile] = {
    BambuPrinterFamily.X1: BambuCameraProfile(
        family=BambuPrinterFamily.X1,
        supported_kinds=(BambuCameraKind.RTSPS, BambuCameraKind.RTSP, BambuCameraKind.SNAPSHOT_IMAGE, BambuCameraKind.CLOUD_TUNNEL),
        default_port=322,
        default_path="/streaming/live/1",
        username="bblp",
        requires_access_code=True,
        requires_lan_liveview=True,
        requires_developer_lan_mode=False,
        preferred_snapshot_fallback=True,
        notes="X1/X1C/X1E: chamber stream normally uses RTSP/RTSPS with bblp access-code auth; configured host should override wrong host in returned URL.",
    ),
    BambuPrinterFamily.P1: BambuCameraProfile(
        family=BambuPrinterFamily.P1,
        supported_kinds=(BambuCameraKind.RTSPS, BambuCameraKind.RTSP, BambuCameraKind.SNAPSHOT_IMAGE, BambuCameraKind.CLOUD_TUNNEL),
        default_port=322,
        default_path="/streaming/live/1",
        username="bblp",
        requires_access_code=True,
        requires_lan_liveview=True,
        requires_developer_lan_mode=False,
        preferred_snapshot_fallback=True,
        notes="P1P/P1S/P2S: camera behavior differs by firmware and model; runtime feature detection decides stream versus image fallback.",
    ),
    BambuPrinterFamily.A1: BambuCameraProfile(
        family=BambuPrinterFamily.A1,
        supported_kinds=(BambuCameraKind.SNAPSHOT_IMAGE, BambuCameraKind.CLOUD_TUNNEL, BambuCameraKind.UNKNOWN),
        default_port=None,
        default_path=None,
        username="bblp",
        requires_access_code=True,
        requires_lan_liveview=False,
        requires_developer_lan_mode=False,
        preferred_snapshot_fallback=True,
        notes="A1/A1 mini: do not assume X/P-style RTSP stream; prefer runtime detected image/snapshot path and cloud/local capability flags.",
    ),
    BambuPrinterFamily.H2: BambuCameraProfile(
        family=BambuPrinterFamily.H2,
        supported_kinds=(BambuCameraKind.RTSPS, BambuCameraKind.RTSP, BambuCameraKind.SNAPSHOT_IMAGE, BambuCameraKind.CLOUD_TUNNEL, BambuCameraKind.UNKNOWN),
        default_port=322,
        default_path="/streaming/live/1",
        username="bblp",
        requires_access_code=True,
        requires_lan_liveview=True,
        requires_developer_lan_mode=False,
        preferred_snapshot_fallback=True,
        notes="H2/H2D/H2S/H2C: keep camera and AMS behavior runtime-driven because firmware and hardware variants evolve.",
    ),
    BambuPrinterFamily.UNKNOWN: BambuCameraProfile(
        family=BambuPrinterFamily.UNKNOWN,
        supported_kinds=(BambuCameraKind.UNKNOWN,),
        default_port=None,
        default_path=None,
        username="bblp",
        requires_access_code=True,
        requires_lan_liveview=False,
        requires_developer_lan_mode=False,
        preferred_snapshot_fallback=True,
        notes="Unknown model: expose no hard assumption; detect stream/image support from printer data first.",
    ),
}


MODEL_CAPABILITIES: dict[BambuPrinterFamily, BambuModelCapabilities] = {
    BambuPrinterFamily.X1: BambuModelCapabilities(
        family=BambuPrinterFamily.X1,
        model_keys=("x1", "x1c", "x1 carbon", "x1e", "x2d"),
        supports_ams=True,
        supports_ams_lite=False,
        supports_ams_2_pro=True,
        supports_ams_ht=True,
        supports_chamber_temperature=True,
        supports_chamber_fan=True,
        supports_aux_fan=True,
        supports_dual_nozzle=False,
        supports_hotend_rack=False,
        supports_sdcard_legacy_url=True,
        camera_profile=CAMERA_PROFILES[BambuPrinterFamily.X1],
    ),
    BambuPrinterFamily.P1: BambuModelCapabilities(
        family=BambuPrinterFamily.P1,
        model_keys=("p1", "p1p", "p1s", "p2s"),
        supports_ams=True,
        supports_ams_lite=False,
        supports_ams_2_pro=True,
        supports_ams_ht=True,
        supports_chamber_temperature=False,
        supports_chamber_fan=True,
        supports_aux_fan=True,
        supports_dual_nozzle=False,
        supports_hotend_rack=False,
        supports_sdcard_legacy_url=True,
        camera_profile=CAMERA_PROFILES[BambuPrinterFamily.P1],
    ),
    BambuPrinterFamily.A1: BambuModelCapabilities(
        family=BambuPrinterFamily.A1,
        model_keys=("a1", "a1 mini", "a1mini"),
        supports_ams=True,
        supports_ams_lite=True,
        supports_ams_2_pro=False,
        supports_ams_ht=False,
        supports_chamber_temperature=False,
        supports_chamber_fan=False,
        supports_aux_fan=False,
        supports_dual_nozzle=False,
        supports_hotend_rack=False,
        supports_sdcard_legacy_url=True,
        camera_profile=CAMERA_PROFILES[BambuPrinterFamily.A1],
    ),
    BambuPrinterFamily.H2: BambuModelCapabilities(
        family=BambuPrinterFamily.H2,
        model_keys=("h2", "h2d", "h2d pro", "h2dpro", "h2s", "h2c"),
        supports_ams=True,
        supports_ams_lite=False,
        supports_ams_2_pro=True,
        supports_ams_ht=True,
        supports_chamber_temperature=True,
        supports_chamber_fan=True,
        supports_aux_fan=True,
        supports_dual_nozzle=True,
        supports_hotend_rack=True,
        supports_sdcard_legacy_url=False,
        camera_profile=CAMERA_PROFILES[BambuPrinterFamily.H2],
    ),
    BambuPrinterFamily.UNKNOWN: BambuModelCapabilities(
        family=BambuPrinterFamily.UNKNOWN,
        model_keys=(),
        supports_ams=True,
        supports_ams_lite=True,
        supports_ams_2_pro=True,
        supports_ams_ht=True,
        supports_chamber_temperature=True,
        supports_chamber_fan=True,
        supports_aux_fan=True,
        supports_dual_nozzle=True,
        supports_hotend_rack=True,
        supports_sdcard_legacy_url=False,
        camera_profile=CAMERA_PROFILES[BambuPrinterFamily.UNKNOWN],
    ),
}


PRINT_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "printer_model": ("printer_type", "printer_model", "model", "dev_model_name", "machine_model"),
    "serial": ("serial", "sn", "dev_id", "device_id"),
    "firmware": ("firmware_version", "sw_ver", "ota_version", "get_version.module", "module.version"),
    "hardware": ("hw_ver", "hardware_version", "get_version.module"),
    "wifi_signal": ("wifi_signal", "wifi_signal_raw", "wifi", "wifi_rssi"),
    "online": ("online", "online.ahb", "online.ext"),
    "print_status": ("gcode_state", "print_status", "state"),
    "current_stage": ("stg_cur", "mc_print_stage", "current_stage"),
    "task_name": ("subtask_name", "gcode_file", "task_name", "file", "project_file"),
    "nozzle_temperature": ("nozzle_temper", "nozzle_temp", "hotend_temper"),
    "nozzle_target_temperature": ("nozzle_target_temper", "nozzle_target_temp", "hotend_target_temper"),
    "nozzle_diameter": ("nozzle_diameter", "nozzle.diameter"),
    "nozzle_type": ("nozzle_type", "nozzle.type"),
    "bed_temperature": ("bed_temper", "bed_temp"),
    "bed_target_temperature": ("bed_target_temper", "bed_target_temp"),
    "chamber_temperature": ("chamber_temper", "chamber_temp"),
    "chamber_target_temperature": ("chamber_target_temper", "chamber_target_temp"),
    "progress_percent": ("mc_percent", "print_percent", "progress", "percent"),
    "remaining_time_minutes": ("mc_remaining_time", "remaining_time", "remain_time"),
    "current_layer": ("layer_num", "current_layer"),
    "total_layers": ("total_layer_num", "total_layers"),
    "speed_level": ("spd_lvl", "speed_level"),
    "sdcard_state": ("sdcard", "sdcard_state"),
    "camera_rtsp_url": ("camera.rtsp_url", "rtsp_url", "camera_url"),
    "home_flag": ("home_flag",),
    "print_fun": ("fun", "print_fun"),
}


AMS_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "ams_root": ("ams", "ams.ams", "ams_list", "ams.data"),
    "ams_units": ("ams", "ams.ams", "ams_list", "ams.data"),
    "tray_root": ("tray", "tray_info", "slots", "tray_info_idx"),
    "tray_id": ("id", "tray_id", "slot_id", "tray_info_idx"),
    "tray_type": ("tray_type", "type", "filament_type"),
    "tray_sub_brand": ("tray_sub_brands", "sub_brand", "filament_sub_brand"),
    "tray_color": ("tray_color", "color", "filament_color"),
    "tray_weight": ("tray_weight", "weight", "remain_weight"),
    "tray_diameter": ("tray_diameter", "diameter"),
    "tray_nozzle_temp_min": ("nozzle_temp_min", "nozzle_temp_min_c"),
    "tray_nozzle_temp_max": ("nozzle_temp_max", "nozzle_temp_max_c"),
    "tray_bed_temp": ("bed_temp", "bed_temperature"),
    "tray_drying_temp": ("drying_temp", "drying_temperature"),
    "tray_drying_time": ("drying_time", "drying_duration"),
    "active_tray": ("tray_now", "ams_tray_now", "active_tray"),
    "humidity": ("humidity", "ams_humidity"),
    "ams_temperature": ("temp", "temperature", "ams_temp"),
}


GCODE_STATE_OPTIONS = (
    "failed",
    "finish",
    "idle",
    "init",
    "offline",
    "pause",
    "prepare",
    "running",
    "slicing",
    "unknown",
)


SPEED_PROFILE = {
    1: "silent",
    2: "standard",
    3: "sport",
    4: "ludicrous",
}


SDCARD_STATUS = ("missing", "normal", "abnormal")


AMS_MODELS = ("AMS", "AMS Lite", "AMS 2 Pro", "AMS HT", "External Spool")


def normalize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get("print"), dict):
        return payload["print"]
    return payload


def detect_family(model_text: str | None) -> BambuPrinterFamily:
    normalized = (model_text or "").strip().lower()
    for family, capabilities in MODEL_CAPABILITIES.items():
        if family == BambuPrinterFamily.UNKNOWN:
            continue
        if any(key in normalized for key in capabilities.model_keys):
            return family
    return BambuPrinterFamily.UNKNOWN


def get_model_capabilities(model_text: str | None) -> BambuModelCapabilities:
    return MODEL_CAPABILITIES[detect_family(model_text)]


def get_camera_profile(model_text: str | None) -> BambuCameraProfile:
    return get_model_capabilities(model_text).camera_profile


def nested_get(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def recursive_find_key(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = recursive_find_key(value, key)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = recursive_find_key(value, key)
            if found is not None:
                return found
    return None


def first_value(payload: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    data = normalize_payload(payload)
    for alias in aliases:
        value = nested_get(data, alias)
        if value is not None:
            return value
        value = recursive_find_key(data, alias)
        if value is not None:
            return value
    return None


def extract_print_value(payload: dict[str, Any], key: str) -> Any:
    aliases = PRINT_FIELD_ALIASES.get(key)
    if not aliases:
        return None
    return first_value(payload, aliases)


def build_rtsp_url(host: str | None, access_code: str | None, model_text: str | None, raw_url: str | None = None) -> str | None:
    profile = get_camera_profile(model_text)
    if raw_url and access_code:
        return raw_url
    if not host or not access_code or not profile.default_port or not profile.default_path:
        return None
    return f"rtsps://{profile.username}:{access_code}@{host}:{profile.default_port}{profile.default_path}"


def extract_camera_candidates(payload: dict[str, Any], host: str | None, access_code: str | None) -> dict[str, Any]:
    data = normalize_payload(payload)
    model = extract_print_value(data, "printer_model")
    raw_url = extract_print_value(data, "camera_rtsp_url")
    profile = get_camera_profile(str(model or ""))

    return {
        "family": profile.family.value,
        "supported_kinds": [kind.value for kind in profile.supported_kinds],
        "raw_url": raw_url,
        "stream_url": build_rtsp_url(host, access_code, str(model or ""), str(raw_url) if raw_url else None),
        "snapshot_supported": BambuCameraKind.SNAPSHOT_IMAGE in profile.supported_kinds,
        "requires_access_code": profile.requires_access_code,
        "requires_lan_liveview": profile.requires_lan_liveview,
        "requires_developer_lan_mode": profile.requires_developer_lan_mode,
        "notes": profile.notes,
    }


def extract_ams_root(payload: dict[str, Any]) -> Any:
    data = normalize_payload(payload)
    for alias in AMS_FIELD_ALIASES["ams_root"]:
        value = nested_get(data, alias)
        if value is not None:
            return value
        value = recursive_find_key(data, alias)
        if value is not None:
            return value
    return None


def extract_ams_summary(payload: dict[str, Any]) -> dict[str, Any]:
    root = extract_ams_root(payload)
    units: list[dict[str, Any]] = []

    if isinstance(root, dict):
        iterable = root.values()
    elif isinstance(root, list):
        iterable = root
    else:
        iterable = []

    for index, unit in enumerate(iterable):
        if not isinstance(unit, dict):
            continue
        trays = unit.get("tray") or unit.get("trays") or unit.get("tray_info") or unit.get("slots") or []
        if isinstance(trays, dict):
            tray_iterable = trays.values()
        elif isinstance(trays, list):
            tray_iterable = trays
        else:
            tray_iterable = []

        normalized_trays = []
        for tray_index, tray in enumerate(tray_iterable):
            if not isinstance(tray, dict):
                continue
            normalized_trays.append(
                {
                    "index": tray_index,
                    "id": first_value(tray, AMS_FIELD_ALIASES["tray_id"]),
                    "type": first_value(tray, AMS_FIELD_ALIASES["tray_type"]),
                    "sub_brand": first_value(tray, AMS_FIELD_ALIASES["tray_sub_brand"]),
                    "color": first_value(tray, AMS_FIELD_ALIASES["tray_color"]),
                    "weight": first_value(tray, AMS_FIELD_ALIASES["tray_weight"]),
                    "diameter": first_value(tray, AMS_FIELD_ALIASES["tray_diameter"]),
                    "nozzle_temp_min": first_value(tray, AMS_FIELD_ALIASES["tray_nozzle_temp_min"]),
                    "nozzle_temp_max": first_value(tray, AMS_FIELD_ALIASES["tray_nozzle_temp_max"]),
                    "bed_temp": first_value(tray, AMS_FIELD_ALIASES["tray_bed_temp"]),
                    "drying_temp": first_value(tray, AMS_FIELD_ALIASES["tray_drying_temp"]),
                    "drying_time": first_value(tray, AMS_FIELD_ALIASES["tray_drying_time"]),
                }
            )

        units.append(
            {
                "index": index,
                "serial": unit.get("serial") or unit.get("sn"),
                "model": unit.get("model") or unit.get("type"),
                "humidity": first_value(unit, AMS_FIELD_ALIASES["humidity"]),
                "temperature": first_value(unit, AMS_FIELD_ALIASES["ams_temperature"]),
                "trays": normalized_trays,
            }
        )

    return {
        "has_ams": bool(units),
        "unit_count": len(units),
        "units": units,
    }