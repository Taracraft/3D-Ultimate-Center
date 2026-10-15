"""Safe asynchronous subprocess execution for local providers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class ProcessResult:
    return_code: int
    stdout: str
    stderr: str


class ProcessRunner:
    async def run(
        self,
        command: tuple[str, ...],
        *,
        cwd: str | Path | None = None,
        timeout_seconds: float = 900.0,
    ) -> ProcessResult:
        if not command:
            raise ValueError("command must not be empty")
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd) if cwd is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=10.0)
            except TimeoutError:
                process.kill()
                await process.wait()
            raise TimeoutError(
                f"process timed out after {timeout_seconds} seconds"
            )
        return ProcessResult(
            return_code=int(process.returncode or 0),
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
        )
