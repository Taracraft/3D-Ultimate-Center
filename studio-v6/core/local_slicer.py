"""Local CLI slicer runtime with real process cancellation."""

from __future__ import annotations

import shutil
from dataclasses import replace

from .managed_process_runner import ManagedProcessRunner
from .providers import ProviderCapabilities, ProviderHealth
from .slicer_config import LocalSlicerConfig
from .slicing import SliceJobRecord, SliceJobStatus


class LocalCliSlicer:
    def __init__(
        self,
        config: LocalSlicerConfig,
        runner: ManagedProcessRunner | None = None,
    ) -> None:
        self.config = config
        self.runner = runner or ManagedProcessRunner()
        self._commands: dict[str, tuple[str, ...]] = {}
        self._jobs: dict[str, SliceJobRecord] = {}

    async def health(self) -> ProviderHealth:
        available = shutil.which(self.config.executable) is not None
        return ProviderHealth(
            provider_id=self.config.provider_id,
            available=available,
            message=None if available else f"executable not found: {self.config.executable}",
        )

    async def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.config.provider_id,
            input_formats=("stl", "3mf", "obj"),
            output_formats=("3mf", "gcode", "bgcode"),
            supports_cancel=True,
            supports_layer_preview=True,
            max_parallel_jobs=self.config.max_parallel_jobs,
        )

    def prepare(self, job_id: str, command: tuple[str, ...]) -> None:
        if not command:
            raise ValueError("slicer command must not be empty")
        self._commands[job_id] = command

    async def submit(self, job: SliceJobRecord) -> SliceJobRecord:
        command = self._commands.get(job.id)
        if command is None:
            raise ValueError(f"no command prepared for {job.id}")
        workspace = self.config.workspace_root / job.id
        workspace.mkdir(parents=True, exist_ok=True)
        running = replace(job, status=SliceJobStatus.RUNNING, progress=5.0)
        self._jobs[job.id] = running

        result = await self.runner.run(
            job.id,
            command,
            cwd=workspace,
            timeout_seconds=self.config.timeout_seconds,
        )
        if result.cancelled:
            completed = replace(
                running,
                status=SliceJobStatus.CANCELLED,
                progress=0.0,
                error_code=None,
                error_message=None,
            )
        elif result.return_code != 0:
            completed = replace(
                running,
                status=SliceJobStatus.FAILED,
                error_code="slicer_failed",
                error_message=result.stderr.strip() or result.stdout.strip(),
            )
        else:
            completed = replace(
                running,
                status=SliceJobStatus.SUCCEEDED,
                progress=100.0,
            )
        self._jobs[job.id] = completed
        return completed

    async def inspect(self, job_id: str) -> SliceJobRecord:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    async def cancel(self, job_id: str) -> None:
        await self.runner.cancel(job_id)
        self._commands.pop(job_id, None)
        job = self._jobs.get(job_id)
        if job is not None:
            self._jobs[job_id] = replace(
                job,
                status=SliceJobStatus.CANCELLING,
            )

    async def close(self) -> None:
        await self.runner.close()