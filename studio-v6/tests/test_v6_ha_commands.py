"""Unit tests for the fail-closed V6 Home Assistant command contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


COMMANDS_PATH = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio_v6"
    / "commands.py"
)

SPEC = importlib.util.spec_from_file_location("ultimate_3d_studio_v6_commands", COMMANDS_PATH)
assert SPEC is not None
assert SPEC.loader is not None
commands = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(commands)


def test_command_request_requires_confirmation() -> None:
    with pytest.raises(commands.PrinterCommandError, match="confirm must be true"):
        commands.PrinterCommandRequest.from_payload(
            {"printer_id": "SERIAL", "command": "pause", "confirm": False}
        )


def test_command_request_rejects_unknown_command() -> None:
    with pytest.raises(commands.PrinterCommandError, match="Unsupported command"):
        commands.PrinterCommandRequest.from_payload(
            {"printer_id": "SERIAL", "command": "start", "confirm": True}
        )


def test_command_request_normalizes_command() -> None:
    request = commands.PrinterCommandRequest.from_payload(
        {"printer_id": " SERIAL ", "command": " Resume ", "confirm": True}
    )
    assert request.printer_id == "SERIAL"
    assert request.command == "resume"
    assert request.confirm is True


def test_retry_command_request_is_supported() -> None:
    request = commands.PrinterCommandRequest.from_payload(
        {"printer_id": "SERIAL", "command": " RETRY ", "confirmed": True}
    )
    assert request.command == "retry"
    assert request.confirm is True


def test_build_bambu_print_command() -> None:
    payload = commands.build_bambu_print_command("pause", "sequence-1")
    assert payload == {
        "print": {
            "sequence_id": "sequence-1",
            "command": "pause",
        }
    }


def test_build_bambu_retry_command_matches_bambu_studio_protocol() -> None:
    payload = commands.build_bambu_retry_command("sequence-retry")
    assert payload == {
        "print": {
            "sequence_id": "sequence-retry",
            "command": "ams_control",
            "param": "resume",
        }
    }
    assert commands.build_bambu_command("retry", "sequence-retry") == payload


def test_retry_is_not_accepted_as_plain_print_command() -> None:
    with pytest.raises(commands.PrinterCommandError, match="Unsupported print command"):
        commands.build_bambu_print_command("retry", "sequence-retry")


def test_capabilities_keep_unverified_commands_disabled() -> None:
    capabilities = {
        item["command"]: item
        for item in commands.command_capabilities()
    }
    assert capabilities["pause"]["enabled"] is True
    assert capabilities["resume"]["enabled"] is True
    assert capabilities["retry"]["enabled"] is True
    assert capabilities["retry"]["protocol_command"] == "ams_control"
    assert capabilities["retry"]["protocol_param"] == "resume"
    assert capabilities["stop"]["enabled"] is True
    assert capabilities["light"]["enabled"] is False
    assert capabilities["speed"]["enabled"] is True
    assert capabilities["stop"]["destructive"] is True


def test_speed_command_is_fixed_to_four_bambu_levels() -> None:
    for level, percent in ((1, 50), (2, 100), (3, 125), (4, 166)):
        request = commands.PrinterCommandRequest.from_payload({"printer_id": "SERIAL", "command": "speed", "speed_level": level, "confirmed": True})
        assert request.speed_level == level
        assert commands.SPEED_LEVEL_PERCENT[level] == percent
    with pytest.raises(commands.PrinterCommandError, match="speed_level"):
        commands.PrinterCommandRequest.from_payload({"printer_id": "SERIAL", "command": "speed", "speed_level": 5, "confirmed": True})

def test_speed_capability_is_enabled_and_exposes_fixed_levels() -> None:
    speed = next(item for item in commands.command_capabilities() if item["command"] == "speed")
    assert speed["enabled"] is True
    assert speed["protocol_command"] == "print_speed"
    assert speed["levels"] == [{"level": 1, "percent": 50}, {"level": 2, "percent": 100}, {"level": 3, "percent": 125}, {"level": 4, "percent": 166}]


def test_speed_provider_waits_for_telemetry_confirmation() -> None:
    provider_source = (
        COMMANDS_PATH.parent / "provider_bambu_lan_v2.py"
    ).read_text(encoding="utf-8")
    assert "async def _async_wait_for_speed_level" in provider_source
    assert "self.telemetry.speed_level == expected" in provider_source
    assert "confirmed = await self._async_wait_for_speed_level(speed_level)" in provider_source
    assert "Telemetriebestätigung steht noch aus" in provider_source
