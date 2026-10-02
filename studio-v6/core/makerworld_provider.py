"""Provider contract for MakerWorld catalog and user-authorized downloads."""

from __future__ import annotations

from typing import Protocol

from .makerworld import MakerWorldDownload, MakerWorldModel, MakerWorldSearchResult


class MakerWorldProvider(Protocol):
    async def search(
        self,
        query: str,
        *,
        cursor: str | None = None,
        limit: int = 24,
    ) -> MakerWorldSearchResult: ...

    async def get_model(self, model_id_or_url: str) -> MakerWorldModel: ...

    async def download(
        self,
        model_id: str,
        *,
        profile_id: str | None,
        license_acknowledged: bool,
    ) -> MakerWorldDownload: ...


class MakerWorldAuthenticationRequired(RuntimeError):
    def __init__(self, authorization_url: str, message: str = "MakerWorld authentication required") -> None:
        super().__init__(message)
        self.authorization_url = authorization_url