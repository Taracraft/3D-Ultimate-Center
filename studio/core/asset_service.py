"""Asset Core service functions."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .assets import AssetFormat, AssetKind, AssetRecord
from .common import new_id, utc_now
from .repositories import AssetRepository


class AssetService:
    def __init__(self, repository: AssetRepository, blob_root: str | Path) -> None:
        self._repository = repository
        self._blob_root = Path(blob_root)

    @staticmethod
    def digest_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as source:
            while chunk := source.read(chunk_size):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def storage_key(digest: str) -> str:
        normalized = digest.lower()
        if len(normalized) != 64:
            raise ValueError("digest must contain 64 hexadecimal characters")
        return f"sha256/{normalized[:2]}/{normalized}"

    def find_duplicate(self, digest: str) -> AssetRecord | None:
        return self._repository.find_by_digest(digest.lower())

    def get(self, asset_id: str) -> AssetRecord:
        asset = self._repository.get(asset_id)
        if asset is None:
            raise KeyError(asset_id)
        return asset

    def resolve_path(self, asset: AssetRecord | str) -> Path:
        record = self.get(asset) if isinstance(asset, str) else asset
        path = (self._blob_root / record.storage_key).resolve()
        root = self._blob_root.resolve()
        if path != root and root not in path.parents:
            raise ValueError("asset storage path escapes the blob root")
        return path

    def register_file(
        self,
        *,
        source_path: str | Path,
        original_name: str,
        kind: AssetKind,
        format: AssetFormat,
    ) -> tuple[AssetRecord, bool]:
        source = Path(source_path)
        digest = self.digest_file(source)
        duplicate = self.find_duplicate(digest)
        if duplicate is not None:
            return duplicate, True

        key = self.storage_key(digest)
        target = self._blob_root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)

        asset = AssetRecord(
            id=new_id("asset"),
            kind=kind,
            format=format,
            digest=digest,
            size_bytes=target.stat().st_size,
            original_name=Path(original_name).name,
            storage_key=key,
            created_at=utc_now(),
        )
        try:
            self._repository.add(asset)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return asset, False
