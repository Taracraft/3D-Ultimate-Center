"""Finalize an upload into the content-addressed Asset Core."""

from __future__ import annotations

from .asset_service import AssetService
from .file_formats import resolve_format
from .upload_service import UploadService


class UploadFinalizer:
    def __init__(
        self,
        upload_service: UploadService,
        asset_service: AssetService,
    ) -> None:
        self._uploads = upload_service
        self._assets = asset_service

    def finalize(self, upload_id: str):
        session = self._uploads.mark_verifying(upload_id)
        source_path = self._uploads.partial_path(upload_id)

        try:
            digest = self._assets.digest_file(source_path)
            if session.expected_digest and digest != session.expected_digest:
                raise ValueError("uploaded file digest does not match expected digest")

            asset_format, asset_kind = resolve_format(session.original_name)
            asset, duplicate = self._assets.register_file(
                source_path=source_path,
                original_name=session.original_name,
                kind=asset_kind,
                format=asset_format,
            )
            if duplicate:
                source_path.unlink(missing_ok=True)

            completed = self._uploads.mark_completed(upload_id, asset.id)
            return completed, asset, duplicate
        except Exception as error:
            self._uploads.mark_failed(
                upload_id,
                error.__class__.__name__,
                str(error),
            )
            raise