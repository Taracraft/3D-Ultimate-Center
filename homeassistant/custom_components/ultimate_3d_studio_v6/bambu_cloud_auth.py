"""Direct Bambu account authorization for Ultimate 3D Studio V6.

The account password and verification code are used only for the active Home
Assistant options flow. They are never returned to the frontend and never stored.
Only the resulting account tokens and UID are persisted by the config entry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiohttp import ClientSession

from .const import REGION_CHINA, VERSION


class BambuCloudAuthError(RuntimeError):
    """Bambu account authorization failed."""


class VerificationCodeRequired(BambuCloudAuthError):
    """Bambu requires the email verification-code step."""


@dataclass(frozen=True)
class BambuCloudTokens:
    access_token: str
    refresh_token: str
    uid: str


class BambuCloudAuth:
    """Minimal account login client used only by the V6 options flow."""

    def __init__(self, session: ClientSession, region: str) -> None:
        self._session = session
        self._base = (
            "https://api.bambulab.cn"
            if region == REGION_CHINA
            else "https://api.bambulab.com"
        )

    async def async_login_password(
        self,
        email: str,
        password: str,
    ) -> BambuCloudTokens:
        data = await self._async_post(
            "/v1/user-service/user/login",
            {"account": email, "password": password},
        )
        if data.get("loginType") == "verifyCode" or not data.get("accessToken"):
            raise VerificationCodeRequired("E-Mail-Verifizierungscode erforderlich")
        return await self._async_tokens(data)

    async def async_login_code(
        self,
        email: str,
        code: str,
    ) -> BambuCloudTokens:
        data = await self._async_post(
            "/v1/user-service/user/login",
            {"account": email, "code": code},
        )
        if not data.get("accessToken"):
            raise BambuCloudAuthError(
                "Bambu Cloud hat kein Zugriffstoken zurückgegeben"
            )
        return await self._async_tokens(data)

    async def _async_tokens(self, data: dict[str, Any]) -> BambuCloudTokens:
        access_token = str(data.get("accessToken", "")).strip()
        refresh_token = str(data.get("refreshToken") or access_token).strip()
        if not access_token:
            raise BambuCloudAuthError("Bambu Cloud hat kein Zugriffstoken geliefert")
        uid = await self.async_get_uid(access_token)
        return BambuCloudTokens(access_token, refresh_token, uid)

    async def async_get_uid(self, access_token: str) -> str:
        data = await self._async_get(
            "/v1/design-user-service/my/preference",
            access_token,
        )
        uid = data.get("uid")
        if uid is None and isinstance(data.get("user"), dict):
            uid = data["user"].get("uid")
        if uid is None:
            raise BambuCloudAuthError("Bambu-Kontoprofil enthält keine UID")
        return str(uid)

    async def _async_get(
        self,
        path: str,
        access_token: str,
    ) -> dict[str, Any]:
        async with self._session.get(
            self._base + path,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "User-Agent": f"Ultimate-3D-Studio-V6/{VERSION}",
                "X-BBL-Client-Name": "Ultimate3DStudioV6",
                "X-BBL-Client-Type": "integration",
                "X-BBL-Client-Version": VERSION,
            },
            timeout=25,
        ) as response:
            payload = await response.json(content_type=None)
            if response.status >= 400:
                raise BambuCloudAuthError(
                    f"Bambu-Kontoprofil antwortete mit HTTP {response.status}"
                )
            if not isinstance(payload, dict):
                raise BambuCloudAuthError("Ungültige Bambu-Kontoprofil-Antwort")
            return payload

    async def _async_post(
        self,
        path: str,
        payload: dict[str, str],
    ) -> dict[str, Any]:
        async with self._session.post(
            self._base + path,
            json=payload,
            headers={
                "Accept": "application/json",
                "User-Agent": f"Ultimate-3D-Studio-V6/{VERSION}",
                "X-BBL-Client-Name": "Ultimate3DStudioV6",
                "X-BBL-Client-Type": "integration",
                "X-BBL-Client-Version": VERSION,
            },
            timeout=25,
        ) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                raise BambuCloudAuthError(
                    f"Bambu-Anmeldung antwortete mit HTTP {response.status}"
                )
            if not isinstance(data, dict):
                raise BambuCloudAuthError("Ungültige Bambu-Anmeldeantwort")
            return data