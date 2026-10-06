from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class NetworkCommand:
    section: str
    command: str
    sequence_id: str
    payload: dict[str, Any]
    qos: int = 1


@dataclass(frozen=True, slots=True)
class NetworkCommandResult:
    """Normalized result returned by the active Bambu network package.

    The package historically exposed ``mqtt_confirmed`` while the V6 provider
    contract uses the more explicit ``mqtt_puback_received`` and
    ``transport_delivered`` names.  The aliases below keep one canonical result
    object and prevent the provider, health endpoint and sensors from diverging.
    """

    section: str
    command: str
    sequence_id: str
    submitted: bool
    mqtt_confirmed: bool
    response_received: bool
    printer_accepted: bool
    result: str | None = None
    reason: str | None = None
    error_code: int | str | None = None
    response: dict[str, Any] = field(default_factory=dict)
    elapsed_seconds: float = 0.0

    @property
    def mqtt_puback_received(self) -> bool:
        return self.mqtt_confirmed

    @property
    def transport_delivered(self) -> bool:
        return self.submitted and (
            self.mqtt_confirmed or self.response_received
        )

    @property
    def accepted(self) -> bool:
        return self.submitted and self.printer_accepted
