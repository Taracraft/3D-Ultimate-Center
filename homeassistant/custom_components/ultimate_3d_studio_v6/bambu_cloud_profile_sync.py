"""Read-only Bambu Cloud preset synchronization with persistent offline cache."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
import logging
import re
from typing import Any
from urllib.parse import quote

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_CLOUD_ACCESS_TOKEN,
    CONF_CLOUD_EMAIL,
    CONF_CLOUD_ENABLED,
    CONF_CLOUD_PROFILE_SYNC,
    CONF_CLOUD_REFRESH_TOKEN,
    CONF_CLOUD_REGION,
    CONF_CLOUD_UID,
    DATA_CLOUD_PROFILE_SYNC,
    DEFAULT_CLOUD_PROFILE_SYNC,
    DOMAIN,
    REGION_CHINA,
    REGION_GLOBAL,
    VERSION,
)
from .profile_runtime import get_profile_runtime

_LOGGER = logging.getLogger(__name__)
_LEGACY_DOMAIN = "printer_control_center"
_PRESET_ID = re.compile(r"^(PPUS|PFUS|PMUS)[A-Za-z0-9_-]+$")
_SYNC_INTERVAL = timedelta(hours=6)
_MAX_CONCURRENCY = 4
# The endpoint validates a four-part slicer-format version. This value describes
# protocol compatibility only and is not used to impersonate Bambu Studio.
_SLICER_VERSION = "1.0.0.0"
_PROFILE_GROUPS = ("print", "printer", "filament")
_SYSTEM_FILAMENT_RAW_BASE = (
    "https://raw.githubusercontent.com/bambulab/BambuStudio/master/"
    "resources/profiles/BBL/filament"
)
_INHERITANCE_METADATA_KEYS = {
    "name", "type", "from", "instantiation", "inherits", "include",
    "setting_id", "filament_id", "compatible_printers", "compatible_prints",
    "compatible_printers_condition", "compatible_prints_condition",
    "model_id", "dev_model_name",
}
_PROTECTED_FILAMENT_PROFILE_IDS = {"PFUS907bcf946d6bd6"}
_PROTECTED_FILAMENT_PROFILE_NAMES = {"eSUN PLA+ @BBL A1 PLA HS"}


class BambuCloudProfileError(RuntimeError):
    """Raised when the read-only preset synchronization fails."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _base_url(region: str) -> str:
    return "https://api.bambulab.cn" if region == REGION_CHINA else "https://api.bambulab.com"


def _append_preset_id(value: Any, result: list[str], seen: set[str]) -> None:
    if isinstance(value, str):
        candidate = value.strip()
        if _PRESET_ID.fullmatch(candidate) and candidate not in seen:
            seen.add(candidate)
            result.append(candidate)
        return
    if not isinstance(value, dict):
        return
    for key in ("setting_id", "settingId", "preset_id", "presetId", "id"):
        _append_preset_id(value.get(key), result, seen)


def _preset_ids(value: Any) -> list[str]:
    """Extract only private user-preset IDs from all known response shapes."""
    result: list[str] = []
    seen: set[str] = set()

    def collect_direct(item: Any) -> None:
        if isinstance(item, str):
            _append_preset_id(item, result, seen)
            return
        if isinstance(item, list):
            for child in item:
                collect_direct(child)
            return
        if isinstance(item, dict):
            _append_preset_id(item, result, seen)
            for key in ("list", "items", "settings", "presets", "setting_ids"):
                collect_direct(item.get(key))

    def walk(item: Any) -> None:
        if isinstance(item, list):
            collect_direct(item)
            return
        if not isinstance(item, dict):
            collect_direct(item)
            return

        grouped = False
        for group_name in _PROFILE_GROUPS:
            group = item.get(group_name)
            if not isinstance(group, dict):
                continue
            grouped = True
            collect_direct(group.get("private"))

        for wrapper in ("data", "result"):
            nested = item.get(wrapper)
            if isinstance(nested, (dict, list)):
                walk(nested)

        if not grouped:
            collect_direct(item)

    walk(value)
    return result


def _detail_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BambuCloudProfileError("Bambu Cloud returned an invalid preset response")
    for key in ("data", "result", "setting"):
        nested = value.get(key)
        if isinstance(nested, dict) and (
            "type" in nested or "name" in nested or "setting" in nested
        ):
            return nested
    return value


def _profile_kind(value: str, preset_id: str) -> str | None:
    normalized = value.strip().lower()
    if normalized in {"filament", "material"} or preset_id.startswith("PFUS"):
        return "filament"
    if normalized in {"print", "process"} or preset_id.startswith("PPUS"):
        return "process"
    if normalized in {"printer", "machine"} or preset_id.startswith("PMUS"):
        return "printer"
    return None


def _profile_record(preset_id: str, raw: dict[str, Any]) -> dict[str, Any] | None:
    detail = _detail_payload(raw)
    kind = _profile_kind(str(detail.get("type", "")), preset_id)
    name = str(detail.get("name") or detail.get("nickname") or preset_id).strip()
    setting = detail.get("setting", {})
    if kind is None or not name or not isinstance(setting, dict):
        return None
    updated = str(
        detail.get("update_time")
        or setting.get("updated_time")
        or _now()
    )
    payload = deepcopy(setting)
    payload["_bambu_cloud"] = {
        "preset_id": preset_id,
        "type": str(detail.get("type", "")),
        "base_id": detail.get("base_id"),
        "version": detail.get("version"),
        "public": bool(detail.get("public", False)),
        "filament_id": detail.get("filament_id"),
    }
    return {
        "id": f"cloud.{kind}.{preset_id.lower()}",
        "kind": kind,
        "name": name,
        "payload": payload,
        "cloud_id": preset_id,
        "cloud_type": str(detail.get("type", "")),
        "base_id": detail.get("base_id"),
        "version": detail.get("version"),
        "updated_at": updated,
    }


def _is_a1_system_filament_inheritance(name: str) -> bool:
    """Return whether a system-profile suffix targets the validated Bambu A1."""
    normalized = name.strip().casefold()
    if "@" not in normalized:
        return True
    target = normalized.rsplit("@", 1)[1]
    compact = "".join(character for character in target if character.isalnum())
    return compact in {"bbla1", "bambulaba1"}


def _mark_non_a1_filament_profile(
    profile: dict[str, Any],
    inherited: str,
) -> dict[str, Any]:
    result = deepcopy(profile)
    payload = deepcopy(_detail_payload(profile.get("payload", {})))
    payload["slicing_supported"] = False
    payload["bambu_a1_compatibility"] = "unsupported_printer_profile"
    payload["_v6_inheritance"] = {
        "resolved": False,
        "base_profile": inherited,
        "reason": "non_a1_base_profile",
    }
    result["payload"] = payload
    result["inheritance_resolved"] = False
    result["inheritance_base"] = inherited
    result["compatibility_status"] = "unsupported_target_printer"
    return result


class BambuCloudProfileSync:
    """Synchronize user presets read-only and retain the last good local copy."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._cancel_interval = None
        self._lock = asyncio.Lock()

    async def async_start(self) -> None:
        """Prepare Cloud access without synchronizing until the user requests it."""
        await self._async_migrate_legacy_credentials()
        runtime = get_profile_runtime(self.hass)
        config = self._config()
        credential = str(config.get(CONF_CLOUD_ACCESS_TOKEN, "")).strip()
        await runtime.async_set_cloud_status({
            "configured": bool(credential),
            "syncing": False,
            "last_error": None if credential else "Kein Bambu-Cloud-Zugang in V6 verfügbar",
            "credential_source": "v6" if credential else None,
            "reason": "manual_only",
        })

    async def async_stop(self) -> None:
        if self._cancel_interval is not None:
            self._cancel_interval()
            self._cancel_interval = None

    async def _async_interval(self, _now_value) -> None:
        await self.async_sync(reason="scheduled")

    def _config(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    async def _async_migrate_legacy_credentials(self) -> bool:
        config = self._config()
        if str(config.get(CONF_CLOUD_ACCESS_TOKEN, "")).strip():
            return False

        for legacy in self.hass.config_entries.async_entries(_LEGACY_DOMAIN):
            legacy_config = {**legacy.data, **legacy.options}
            credential = str(legacy_config.get("access_token", "")).strip()
            if not credential:
                continue
            options = {
                **self.entry.options,
                CONF_CLOUD_ENABLED: True,
                CONF_CLOUD_PROFILE_SYNC: True,
                CONF_CLOUD_REGION: str(legacy_config.get("region", REGION_GLOBAL)),
                CONF_CLOUD_EMAIL: str(legacy_config.get("email", "")),
                CONF_CLOUD_ACCESS_TOKEN: credential,
                CONF_CLOUD_REFRESH_TOKEN: str(legacy_config.get("refresh_token", "")),
                CONF_CLOUD_UID: str(legacy_config.get("cloud_uid", "")),
            }
            self.hass.config_entries.async_update_entry(self.entry, options=options)
            _LOGGER.info("Migrated an existing Bambu Cloud authorization to V6 profile sync")
            return True
        return False

    async def async_sync(self, reason: str = "manual") -> dict[str, Any]:
        async with self._lock:
            runtime = get_profile_runtime(self.hass)
            config = self._config()
            enabled = bool(config.get(CONF_CLOUD_PROFILE_SYNC, DEFAULT_CLOUD_PROFILE_SYNC))
            credential = str(config.get(CONF_CLOUD_ACCESS_TOKEN, "")).strip()
            region = str(config.get(CONF_CLOUD_REGION, REGION_GLOBAL)).strip() or REGION_GLOBAL
            if not enabled or not credential:
                return await runtime.async_set_cloud_status({
                    "configured": bool(credential),
                    "syncing": False,
                    "last_attempt_at": _now(),
                    "last_error": None if credential else "Kein Bambu-Cloud-Zugang in V6 verfügbar",
                    "credential_source": "v6" if credential else None,
                    "reason": reason,
                })

            started = _now()
            await runtime.async_set_cloud_status({
                "configured": True,
                "syncing": True,
                "last_attempt_at": started,
                "last_error": None,
                "credential_source": "v6",
                "reason": reason,
            })
            try:
                ids = await self._async_fetch_ids(credential, region)
                catalog = await runtime.async_catalog()
                cached = {
                    str(item.get("cloud_id", "")): item
                    for item in catalog["profiles"]
                    if item.get("source") == "bambu_cloud"
                }
                profiles, failed = await self._async_fetch_profiles(ids, credential, region, cached)
                status = {
                    "configured": True,
                    "syncing": False,
                    "last_sync_at": _now(),
                    "last_attempt_at": started,
                    "last_error": (
                        f"{failed} Cloud-Profile konnten nicht aktualisiert werden; lokaler Stand wurde beibehalten"
                        if failed else None
                    ),
                    "credential_source": "v6",
                    "reason": reason,
                    "remote_profile_count": len(ids),
                    "partial_failures": failed,
                }
                return await runtime.async_replace_cloud_profiles(profiles, status)
            except Exception as exc:
                message = str(exc) or exc.__class__.__name__
                _LOGGER.warning("Bambu Cloud profile sync failed: %s", message)
                return await runtime.async_set_cloud_status({
                    "configured": True,
                    "syncing": False,
                    "last_attempt_at": started,
                    "last_error": message[:500],
                    "credential_source": "v6",
                    "reason": reason,
                })

    async def _async_fetch_ids(self, credential: str, region: str) -> list[str]:
        session = async_get_clientsession(self.hass)
        url = f"{_base_url(region)}/v1/iot-service/api/slicer/setting"
        async with session.get(
            url,
            params={"version": _SLICER_VERSION, "public": "false"},
            headers=self._headers(credential),
            timeout=30,
        ) as response:
            payload = await response.json(content_type=None)
            if response.status >= 400:
                raise BambuCloudProfileError(
                    f"Cloud-Profilliste: HTTP {response.status}"
                )
        ids = _preset_ids(payload)
        if not ids and isinstance(payload, dict) and payload.get("error"):
            raise BambuCloudProfileError(str(payload.get("error")))
        return ids

    async def _async_fetch_system_filament(self, name: str) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)
        safe_name = quote(name.strip(), safe="")
        url = f"{_SYSTEM_FILAMENT_RAW_BASE}/{safe_name}.json"
        async with session.get(url, timeout=30) as response:
            if response.status == 404:
                raise BambuCloudProfileError(
                    f"Bambu-Basisprofil '{name}' wurde nicht gefunden"
                )
            if response.status >= 400:
                raise BambuCloudProfileError(
                    f"Bambu-Basisprofil '{name}': HTTP {response.status}"
                )
            payload = await response.json(content_type=None)
        if not isinstance(payload, dict):
            raise BambuCloudProfileError(
                f"Bambu-Basisprofil '{name}' ist ungültig"
            )
        return payload

    async def _async_resolve_system_filament(
        self,
        name: str,
        active: set[str] | None = None,
    ) -> dict[str, Any]:
        chain = set() if active is None else set(active)
        normalized = name.strip()
        if not normalized:
            return {}
        if normalized in chain:
            raise BambuCloudProfileError(
                f"Zyklische Bambu-Profilvererbung bei '{normalized}'"
            )
        chain.add(normalized)
        payload = await self._async_fetch_system_filament(normalized)
        merged: dict[str, Any] = {}
        parent = str(payload.get("inherits") or "").strip().strip('"')
        if parent:
            merged.update(
                await self._async_resolve_system_filament(parent, chain)
            )
        includes = payload.get("include")
        if isinstance(includes, list):
            for item in includes:
                include_name = str(item or "").strip().strip('"')
                if not include_name:
                    continue
                include_payload = await self._async_fetch_system_filament(
                    include_name
                )
                for key, value in include_payload.items():
                    if key not in _INHERITANCE_METADATA_KEYS:
                        merged[key] = deepcopy(value)
        for key, value in payload.items():
            if key not in {"inherits", "include"}:
                merged[key] = deepcopy(value)
        return merged

    async def _async_expand_filament_profile(
        self,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        cloud_id = str(profile.get("cloud_id") or "")
        name = str(profile.get("name") or "")
        if (
            cloud_id in _PROTECTED_FILAMENT_PROFILE_IDS
            or name in _PROTECTED_FILAMENT_PROFILE_NAMES
        ):
            return profile
        payload = profile.get("payload")
        if not isinstance(payload, dict):
            return profile
        inherited = str(payload.get("inherits") or "").strip().strip('"')
        if not inherited:
            return profile
        if not _is_a1_system_filament_inheritance(inherited):
            return _mark_non_a1_filament_profile(profile, inherited)
        raw_payload = deepcopy(payload)
        try:
            resolved = await self._async_resolve_system_filament(inherited)
        except Exception as exc:
            _LOGGER.warning(
                "Could not expand Bambu filament inheritance for %s: %s",
                name or cloud_id,
                exc,
            )
            return profile
        cloud_meta = deepcopy(raw_payload.get("_bambu_cloud", {}))
        merged = deepcopy(resolved)
        for key, value in raw_payload.items():
            if key == "_bambu_cloud":
                continue
            merged[key] = deepcopy(value)
        merged["_bambu_cloud"] = cloud_meta
        merged["_v6_inheritance"] = {
            "resolved": True,
            "base_profile": inherited,
            "raw_override": {
                key: deepcopy(value)
                for key, value in raw_payload.items()
                if key != "_bambu_cloud"
            },
        }
        result = deepcopy(profile)
        result["payload"] = merged
        result["inheritance_resolved"] = True
        result["inheritance_base"] = inherited
        return result

    async def _async_fetch_profiles(
        self,
        ids: list[str],
        credential: str,
        region: str,
        cached: dict[str, dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], int]:
        semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)

        async def fetch(preset_id: str) -> tuple[str, dict[str, Any] | None, bool]:
            async with semaphore:
                try:
                    raw = await self._async_fetch_detail(preset_id, credential, region)
                    profile = _profile_record(preset_id, raw)
                    if profile is not None and profile.get("kind") == "filament":
                        profile = await self._async_expand_filament_profile(profile)
                    return preset_id, profile, False
                except Exception:
                    _LOGGER.debug("Cloud preset detail refresh failed for %s", preset_id, exc_info=True)
                    return preset_id, None, True

        results = await asyncio.gather(*(fetch(preset_id) for preset_id in ids))
        profiles: list[dict[str, Any]] = []
        failed = 0
        for preset_id, profile, did_fail in results:
            if profile is not None:
                profiles.append(profile)
                continue
            cached_profile = cached.get(preset_id)
            if cached_profile is not None:
                profiles.append({
                    "id": cached_profile.get("id"),
                    "kind": cached_profile.get("kind"),
                    "name": cached_profile.get("name"),
                    "payload": cached_profile.get("payload", {}),
                    "cloud_id": cached_profile.get("cloud_id"),
                    "cloud_type": cached_profile.get("cloud_type"),
                    "base_id": cached_profile.get("base_id"),
                    "version": cached_profile.get("version"),
                    "created_at": cached_profile.get("created_at"),
                    "updated_at": cached_profile.get("updated_at"),
                })
            if did_fail:
                failed += 1
        return profiles, failed

    async def _async_fetch_detail(self, preset_id: str, credential: str, region: str) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)
        url = f"{_base_url(region)}/v1/iot-service/api/slicer/setting/{preset_id}"
        async with session.get(
            url,
            params={"version": _SLICER_VERSION},
            headers=self._headers(credential),
            timeout=30,
        ) as response:
            payload = await response.json(content_type=None)
            if response.status >= 400:
                raise BambuCloudProfileError(
                    f"Cloud-Profil {preset_id}: HTTP {response.status}"
                )
        if not isinstance(payload, dict):
            raise BambuCloudProfileError(f"Cloud-Profil {preset_id}: ungültige Antwort")
        return payload

    @staticmethod
    def _headers(credential: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {credential}",
            "Accept": "application/json",
            "X-BBL-Client-Name": "Ultimate3DStudioV6",
            "X-BBL-Client-Type": "integration",
            "User-Agent": (
                f"Ultimate-3D-Studio-V6/{VERSION} "
                "(+https://github.com/Taracraft/3D-Printer-Control-Center)"
            ),
        }


def get_cloud_profile_sync(hass: HomeAssistant) -> BambuCloudProfileSync | None:
    value = hass.data.get(DOMAIN, {}).get(DATA_CLOUD_PROFILE_SYNC)
    return value if isinstance(value, BambuCloudProfileSync) else None


async def async_start_cloud_profile_sync(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> BambuCloudProfileSync:
    data = hass.data.setdefault(DOMAIN, {})
    existing = data.get(DATA_CLOUD_PROFILE_SYNC)
    if isinstance(existing, BambuCloudProfileSync):
        return existing
    runtime = BambuCloudProfileSync(hass, entry)
    data[DATA_CLOUD_PROFILE_SYNC] = runtime
    await runtime.async_start()
    return runtime


async def async_stop_cloud_profile_sync(hass: HomeAssistant) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    runtime = data.pop(DATA_CLOUD_PROFILE_SYNC, None)
    if isinstance(runtime, BambuCloudProfileSync):
        await runtime.async_stop()