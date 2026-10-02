"""Preview renderer backed by an external command-line tool."""

from __future__ import annotations

from pathlib import Path

from .asset_service import AssetService
from .assets import AssetFormat, AssetKind
from .process_runner import ProcessRunner


class CommandPreviewRenderer:
    def __init__(
        self,
        *,
        assets: AssetService,
        workspace_root: str | Path,
        command_builder,
        runner: ProcessRunner | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._assets = assets
        self._workspace_root = Path(workspace_root)
        self._command_builder = command_builder
        self._runner = runner or ProcessRunner()
        self._timeout_seconds = timeout_seconds

    async def render(self, asset_id: str, job_id: str) -> str:
        source_asset = self._assets.get(asset_id)
        source_path = self._assets.resolve_path(source_asset)
        workspace = self._workspace_root / job_id
        workspace.mkdir(parents=True, exist_ok=True)
        output_path = workspace / "preview.png"
        command = tuple(self._command_builder(source_path, output_path))
        result = await self._runner.run(
            command,
            cwd=workspace,
            timeout_seconds=self._timeout_seconds,
        )
        if result.return_code != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        if not output_path.is_file():
            raise RuntimeError("preview renderer did not create preview.png")
        preview_asset, _ = self._assets.register_file(
            source_path=output_path,
            original_name=f"{source_asset.id}-preview.png",
            kind=AssetKind.PREVIEW,
            format=AssetFormat.PNG,
        )
        return preview_asset.id