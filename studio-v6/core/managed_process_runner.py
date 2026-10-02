"""Managed asynchronous subprocesses with real per-job cancellation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class ManagedProcessResult:
    return_code: int
    stdout: str
    stderr: str
    cancelled: bool = False


class ManagedProcessRunner:
    def __init__(self) -> None:
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._cancelled: set[str] = set()
        self._lock = asyncio.Lock()

    async def run(
        self,
        job_id: str,
        command: tuple[str, ...],
        *,
        cwd: str | Path | None = None,
        timeout_seconds: float = 900.0,
    ) -> ManagedProcessResult:
        if not command:
            raise ValueError("command must not be empty")
        async with self._lock:
            if job_id in self._processes:
                raise ValueError(f"process already running for job: {job_id}")
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(cwd) if cwd is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._processes[job_id] = process
            self._cancelled.discard(job_id)

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            await self._stop_process(process)
            raise TimeoutError(f"process timed out after {timeout_seconds} seconds")
        finally:
            async with self._lock:
                self._processes.pop(job_id, None)

        cancelled = job_id in self._cancelled
        self._cancelled.discard(job_id)
        return ManagedProcessResult(
            return_code=int(process.returncode or 0),
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            cancelled=cancelled,
        )

    async def cancel(self, job_id: str) -> bool:
        async with self._lock:
            process = self._processes.get(job_id)
            if process is None:
                return False
            self._cancelled.add(job_id)
        await self._stop_process(process)
        return True

    async def close(self) -> None:
        async with self._lock:
            processes = tuple(self._processes.items())
            self._cancelled.update(job_id for job_id, _ in processes)
        for _, process in processes:
            await self._stop_process(process)

    @staticmethod
    async def _stop_process(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=10.0)
        except TimeoutError:
            process.kill()
            await process.wait()