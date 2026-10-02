"""Minimal Bambu Cloud HTTP client.

The Cloud endpoints are reverse-engineered and not an official public API.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiohttp import ClientSession, ClientResponseError

from .const import REGION_CHINA


class CloudApiError(Exception):
    """Cloud API error."""


class VerificationCodeRequired(CloudApiError):
    """Email verification code is required."""


@dataclass
class CloudTokens:
    access_token: str
    refresh_token: str
    uid: str = ""


class BambuCloudApi:
    def __init__(self, session: ClientSession, region: str) -> None:
        self._session = session
        self._region = region
        self._base = (
            "https://api.bambulab.cn"
            if region == REGION_CHINA
            else "https://api.bambulab.com"
        )

    async def login_password(self, email: str, password: str) -> CloudTokens:
        payload = {"account": email, "password": password}
        data = await self._post("/v1/user-service/user/login", payload)
        if data.get("loginType") == "verifyCode" or not data.get("accessToken"):
            raise VerificationCodeRequired("Email verification code required")
        tokens = CloudTokens(
            access_token=str(data["accessToken"]),
            refresh_token=str(data.get("refreshToken", data["accessToken"])),
        )
        tokens.uid = await self.get_uid(tokens.access_token)
        return tokens

    async def login_code(self, email: str, code: str) -> CloudTokens:
        payload = {"account": email, "code": code}
        data = await self._post("/v1/user-service/user/login", payload)
        if not data.get("accessToken"):
            raise CloudApiError("Cloud login did not return an access token")
        tokens = CloudTokens(
            access_token=str(data["accessToken"]),
            refresh_token=str(data.get("refreshToken", data["accessToken"])),
        )
        tokens.uid = await self.get_uid(tokens.access_token)
        return tokens

    async def get_uid(self, token: str) -> str:
        data = await self._get(
            "/v1/design-user-service/my/preference",
            token=token,
        )
        uid = data.get("uid")
        if uid is None and isinstance(data.get("user"), dict):
            uid = data["user"].get("uid")
        if uid is None:
            raise CloudApiError("Cloud profile did not contain uid")
        return str(uid)

    async def get_devices(self, token: str) -> list[dict[str, Any]]:
        data = await self._get("/v1/iot-service/api/user/bind", token=token)
        devices = data.get("devices", [])
        if not isinstance(devices, list):
            raise CloudApiError("Cloud device response is invalid")
        return [x for x in devices if isinstance(x, dict)]

    async def _get(self, path: str, token: str | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        async with self._session.get(
            self._base + path,
            headers=headers,
            timeout=20,
        ) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                raise CloudApiError(f"GET {path}: HTTP {response.status}: {data}")
            if not isinstance(data, dict):
                raise CloudApiError(f"GET {path}: invalid JSON response")
            return data

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._session.post(
            self._base + path,
            json=payload,
            timeout=20,
        ) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                raise CloudApiError(f"POST {path}: HTTP {response.status}: {data}")
            if not isinstance(data, dict):
                raise CloudApiError(f"POST {path}: invalid JSON response")
            return data