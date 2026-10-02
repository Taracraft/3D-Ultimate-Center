"""Provider-neutral data contracts for Ultimate 3D Studio V6."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class PrinterSnapshot:
    printer_id: str
    name: str
    provider: str
    model: str | None = None
    serial: str | None = None
    host: str | None = None
    connection_state: str = "disconnected"
    printer_state: str = "unknown"
    progress: float | None = None
    current_file: str | None = None
    nozzle_temperature: float | None = None
    nozzle_target_temperature: float | None = None
    bed_temperature: float | None = None
    bed_target_temperature: float | None = None
    remaining_time_minutes: int | None = None
    current_layer: int | None = None
    total_layers: int | None = None
    speed_level: int | None = None
    wifi_signal: int | None = None
    print_stage_code: int | None = None
    print_stage_key: str | None = None
    print_stage_label: str | None = None
    print_stage_detail: str | None = None
    print_stage_active: bool = False
    print_stage_history: list[dict[str, Any]] = field(default_factory=list)
    error_code: int | str | None = None
    error_message: str | None = None
    hms: list[dict[str, Any]] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    ams: dict[str, Any] = field(default_factory=dict)
    updated_at: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class PrinterProvider(Protocol):
    provider_id: str

    async def async_start(self) -> None: ...

    async def async_stop(self) -> None: ...

    async def async_printers(self) -> tuple[PrinterSnapshot, ...]: ...
