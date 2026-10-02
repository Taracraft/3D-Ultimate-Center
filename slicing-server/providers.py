"""Provider-neutral slicer contracts."""

from dataclasses import dataclass
from typing import Protocol

from .slicing import SliceJobRecord


@dataclass(slots=True, frozen=True)
class ProviderHealth:
    provider_id: str
    available: bool
    version: str | None = None
    message: str | None = None


@dataclass(slots=True, frozen=True)
class ProviderCapabilities:
    provider_id: str
    input_formats: tuple[str, ...]
    output_formats: tuple[str, ...]
    supports_cancel: bool
    supports_layer_preview: bool
    max_parallel_jobs: int


class SlicerProvider(Protocol):
    async def health(self) -> ProviderHealth: ...
    async def capabilities(self) -> ProviderCapabilities: ...
    async def submit(self, job: SliceJobRecord) -> SliceJobRecord: ...
    async def inspect(self, job_id: str) -> SliceJobRecord: ...
    async def cancel(self, job_id: str) -> None: ...