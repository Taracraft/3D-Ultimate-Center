"""Local slicer provider configuration."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class LocalSlicerConfig:
    provider_id: str
    executable: str
    workspace_root: Path
    timeout_seconds: float = 900.0
    max_parallel_jobs: int = 1