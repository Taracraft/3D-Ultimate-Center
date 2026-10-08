"""Regression tests for the active Studio Bambu network result contract."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODELS_PATH = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio"
    / "network_plugin"
    / "models.py"
)

MODULE_NAME = "ultimate_3d_studio_network_models"
SPEC = importlib.util.spec_from_file_location(MODULE_NAME, MODELS_PATH)
assert SPEC is not None
assert SPEC.loader is not None
models = importlib.util.module_from_spec(SPEC)
sys.modules[MODULE_NAME] = models
SPEC.loader.exec_module(models)


def test_provider_diagnostic_aliases_are_present() -> None:
    result = models.NetworkCommandResult(
        section="print",
        command="project_file",
        sequence_id="42",
        submitted=True,
        mqtt_confirmed=True,
        response_received=True,
        printer_accepted=True,
        result="success",
        elapsed_seconds=0.25,
    )

    assert result.mqtt_puback_received is True
    assert result.transport_delivered is True
    assert result.elapsed_seconds == 0.25
    assert result.accepted is True


def test_transport_delivery_accepts_printer_response_without_puback() -> None:
    result = models.NetworkCommandResult(
        section="print",
        command="project_file",
        sequence_id="43",
        submitted=True,
        mqtt_confirmed=False,
        response_received=True,
        printer_accepted=True,
    )

    assert result.mqtt_puback_received is False
    assert result.transport_delivered is True
    assert result.accepted is True
