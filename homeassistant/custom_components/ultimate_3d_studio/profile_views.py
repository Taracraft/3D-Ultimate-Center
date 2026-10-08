"""Authenticated profile API views for Ultimate 3D Studio."""
from __future__ import annotations

from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .bambu_cloud_profile_sync import get_cloud_profile_sync
from .const import API_BASE, DOMAIN, VERSION
from .profile_runtime import StudioProfileRuntime, get_profile_runtime

_DATA_PROFILE_VIEWS = "profile_views_registered"


def _success(data: Any, **meta: Any) -> web.Response:
    return web.json_response({
        "data": data,
        "error": None,
        "meta": {
            "api_version": "v1",
            "component_version": VERSION,
            **meta,
        },
    })


def _error(status: int, code: str, message: str) -> web.Response:
    return web.json_response({
        "data": None,
        "error": {"code": code, "message": message},
        "meta": {"api_version": "v1", "component_version": VERSION},
    }, status=status)


def _admin_error(request: web.Request) -> web.Response | None:
    user = request.get("hass_user")
    if user is None or not user.is_admin:
        return _error(403, "admin_required", "Administrator access is required")
    return None


async def _confirmed_payload(request: web.Request) -> tuple[dict[str, Any] | None, web.Response | None]:
    try:
        payload = await request.json()
    except Exception:
        return None, _error(400, "invalid_json", "Request body must contain valid JSON")
    if not isinstance(payload, dict):
        return None, _error(400, "invalid_json", "Request body must contain a JSON object")
    if payload.get("confirmed") is not True:
        return None, _error(409, "confirmation_required", "Explicit confirmation is required")
    return payload, None


async def _remove_persisted_profile(
    runtime: StudioProfileRuntime,
    profile_id: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Remove a profile from any category/source in the local Studio catalog."""
    removed = await runtime.async_remove_any(profile_id)
    if removed is None:
        return None, None
    scope = str(removed.pop("_removal_scope", "removed_profile"))
    return removed, scope


class ProfilesView(HomeAssistantView):
    url = f"{API_BASE}/profiles"
    name = "api:ultimate_3d_studio:profiles"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        catalog = await get_profile_runtime(request.app["hass"]).async_catalog()
        return _success(catalog, count=len(catalog["profiles"]))

    async def post(self, request: web.Request) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        payload, payload_error = await _confirmed_payload(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None
        try:
            profile = await get_profile_runtime(request.app["hass"]).async_upsert(payload)
        except ValueError as exc:
            return _error(400, "invalid_profile", str(exc))
        return _success(profile, saved=True)


class ProfileSelectionView(HomeAssistantView):
    url = f"{API_BASE}/profiles/selection"
    name = "api:ultimate_3d_studio:profiles:selection"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        payload, payload_error = await _confirmed_payload(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None
        try:
            selection = await get_profile_runtime(request.app["hass"]).async_set_selection(payload)
        except ValueError as exc:
            return _error(400, "invalid_profile_selection", str(exc))
        return _success(selection, saved=True)


class ProfileRemoveView(HomeAssistantView):
    url = f"{API_BASE}/profiles/{{profile_id}}/remove"
    name = "api:ultimate_3d_studio:profiles:remove"
    requires_auth = True

    async def post(self, request: web.Request, profile_id: str) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        _payload, payload_error = await _confirmed_payload(request)
        if payload_error is not None:
            return payload_error
        removed, removal_scope = await _remove_persisted_profile(
            get_profile_runtime(request.app["hass"]),
            profile_id,
        )
        if removed is None:
            return _error(
                404,
                "profile_not_found",
                "Profile was not found in the local Studio catalog",
            )
        return _success(
            removed,
            removed=True,
            removal_scope=removal_scope,
        )


class ProfileCloudSyncView(HomeAssistantView):
    url = f"{API_BASE}/profiles/cloud/sync"
    name = "api:ultimate_3d_studio:profiles:cloud:sync"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        _payload, payload_error = await _confirmed_payload(request)
        if payload_error is not None:
            return payload_error
        runtime = get_cloud_profile_sync(request.app["hass"])
        if runtime is None:
            return _error(409, "cloud_sync_not_ready", "Bambu Cloud profile sync is not initialized")
        status = await runtime.async_sync(reason="manual")
        catalog = await get_profile_runtime(request.app["hass"]).async_catalog()
        return _success({
            "status": status,
            "profile_count": catalog["source_counts"]["bambu_cloud"],
            "available_offline": catalog["cloud_sync"]["available_offline"],
        }, synchronized=status.get("last_error") is None)


def async_register_profile_views(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_DATA_PROFILE_VIEWS):
        return
    hass.http.register_view(ProfilesView())
    hass.http.register_view(ProfileSelectionView())
    hass.http.register_view(ProfileRemoveView())
    hass.http.register_view(ProfileCloudSyncView())
    domain_data[_DATA_PROFILE_VIEWS] = True
