from __future__ import annotations

from typing import Any
from uuid import uuid4

SUPPORTED_COMMANDS = frozenset({"pause", "resume", "retry", "stop", "speed"})
SPEED_LEVEL_PERCENT = {1: 50, 2: 100, 3: 125, 4: 166}


class PrinterCommandError(ValueError):
    pass


class PrinterCommandRequest:
    __slots__ = ("printer_id", "command", "confirm", "speed_level")

    def __init__(self, printer_id: str, command: str, confirm: bool, speed_level: int | None = None) -> None:
        self.printer_id = printer_id
        self.command = command
        self.confirm = confirm
        self.speed_level = speed_level

    @classmethod
    def from_payload(cls, payload: Any) -> "PrinterCommandRequest":
        if not isinstance(payload, dict):
            raise PrinterCommandError("Request body must be a JSON object")

        printer_id = str(payload.get("printer_id", "")).strip()
        command = str(payload.get("command", "")).strip().lower()
        confirm = payload.get("confirm", payload.get("confirmed"))

        if not printer_id:
            raise PrinterCommandError("printer_id is required")
        if command not in SUPPORTED_COMMANDS:
            raise PrinterCommandError("Unsupported command")
        if confirm is not True:
            raise PrinterCommandError("confirm must be true")

        speed_level = None
        if command == "speed":
            try:
                speed_level = int(payload.get("speed_level"))
            except (TypeError, ValueError) as error:
                raise PrinterCommandError("speed_level must be one of 1, 2, 3 or 4") from error
            if speed_level not in SPEED_LEVEL_PERCENT:
                raise PrinterCommandError("speed_level must be one of 1, 2, 3 or 4")

        return cls(printer_id=printer_id, command=command, confirm=True, speed_level=speed_level)


class PrinterCommandResult:
    __slots__ = (
        "printer_id",
        "provider",
        "command",
        "sequence_id",
        "accepted",
        "confirmed",
        "attempts",
        "final_state",
        "message",
    )

    def __init__(
        self,
        *,
        printer_id: str,
        provider: str,
        command: str,
        sequence_id: str,
        accepted: bool,
        confirmed: bool | None = None,
        attempts: int = 1,
        final_state: str | None = None,
        message: str | None = None,
    ) -> None:
        self.printer_id = printer_id
        self.provider = provider
        self.command = command
        self.sequence_id = sequence_id
        self.accepted = accepted
        self.confirmed = confirmed
        self.attempts = attempts
        self.final_state = final_state
        self.message = message

    def as_dict(self) -> dict[str, object]:
        return {
            "printer_id": self.printer_id,
            "provider": self.provider,
            "command": self.command,
            "sequence_id": self.sequence_id,
            "accepted": self.accepted,
            "confirmed": self.confirmed,
            "attempts": self.attempts,
            "final_state": self.final_state,
            "message": self.message,
        }


def create_sequence_id() -> str:
    return uuid4().hex[:16]


def build_bambu_print_command(command: str, sequence_id: str) -> dict[str, Any]:
    if command not in {"pause", "resume", "stop"}:
        raise PrinterCommandError("Unsupported print command")

    return {
        "print": {
            "sequence_id": sequence_id,
            "command": command,
        }
    }


def build_bambu_retry_command(sequence_id: str) -> dict[str, Any]:
    """Build Bambu Studio's AMS/toolhead retry command."""
    return {
        "print": {
            "sequence_id": sequence_id,
            "command": "ams_control",
            "param": "resume",
        }
    }


def build_bambu_speed_command(sequence_id: str, speed_level: int) -> dict[str, Any]:
    if speed_level not in SPEED_LEVEL_PERCENT:
        raise PrinterCommandError("speed_level must be one of 1, 2, 3 or 4")
    return {
        "print": {
            "sequence_id": sequence_id,
            "command": "print_speed",
            "param": str(speed_level),
        }
    }


def build_bambu_command(command: str, sequence_id: str, speed_level: int | None = None) -> dict[str, Any]:
    if command == "retry":
        return build_bambu_retry_command(sequence_id)
    if command == "speed":
        if speed_level is None:
            raise PrinterCommandError("speed_level must be one of 1, 2, 3 or 4")
        return build_bambu_speed_command(sequence_id, speed_level)
    return build_bambu_print_command(command, sequence_id)


def command_qos(command: str) -> int:
    if command not in SUPPORTED_COMMANDS:
        raise PrinterCommandError("Unsupported command")
    return 1


def command_capabilities() -> list[dict[str, object]]:
    return [
        {
            "command": "pause",
            "label": "Pausieren",
            "enabled": True,
            "destructive": False,
            "requires_confirmation": True,
        },
        {
            "command": "resume",
            "label": "Fortsetzen",
            "enabled": True,
            "destructive": False,
            "requires_confirmation": True,
        },
        {
            "command": "retry",
            "label": "Erneut versuchen",
            "enabled": True,
            "destructive": False,
            "requires_confirmation": True,
            "protocol_command": "ams_control",
            "protocol_param": "resume",
        },
        {
            "command": "stop",
            "label": "Abbrechen",
            "enabled": True,
            "destructive": True,
            "requires_confirmation": True,
            "printer_state_confirmation_required": True,
            "automatic_retry": True,
        },
        {
            "command": "light",
            "label": "Beleuchtung",
            "enabled": False,
            "destructive": False,
            "requires_confirmation": True,
        },
        {
            "command": "speed",
            "label": "Geschwindigkeit",
            "enabled": True,
            "destructive": False,
            "requires_confirmation": True,
            "protocol_command": "print_speed",
            "levels": [
                {"level": level, "percent": percent}
                for level, percent in SPEED_LEVEL_PERCENT.items()
            ],
        },
    ]