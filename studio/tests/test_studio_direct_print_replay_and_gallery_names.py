"""Regression tests for gallery-derived SD names and non-replayable MQTT commands."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

import pytest


COMPONENT = (
    Path(__file__).resolve().parents[1]
    / "deploy/homeassistant/custom_components/ultimate_3d_studio"
)
PACKAGE = "_u3d_studio_direct_print_safety"

package = ModuleType(PACKAGE)
package.__path__ = [str(COMPONENT)]
sys.modules[PACKAGE] = package
network_package = ModuleType(f"{PACKAGE}.network_plugin")
network_package.__path__ = [str(COMPONENT / "network_plugin")]
sys.modules[network_package.__name__] = network_package

direct_print = importlib.import_module(f"{PACKAGE}.bambu_direct_print")
commands = importlib.import_module(f"{PACKAGE}.commands")
network_commands = importlib.import_module(
    f"{PACKAGE}.network_plugin.commands"
)
mqtt_transport = importlib.import_module(f"{PACKAGE}.mqtt_transport")


def test_gallery_project_name_and_plate_form_exact_sd_filename() -> None:
    assert direct_print.build_remote_3mf_filename(
        "IKEA LACK.3mf",
        0,
    ) == "IKEA_LACK_Druckplatte1.3mf"
    assert direct_print.build_remote_3mf_filename(
        "Brause Quadrat 25.3mf",
        1,
    ) == "Brause_Quadrat_25_Druckplatte2.3mf"


def test_existing_plate_suffix_is_not_duplicated() -> None:
    assert direct_print.build_remote_3mf_filename(
        "IKEA LACK_Druckplatte2.3mf",
        1,
    ) == "IKEA_LACK_Druckplatte2.3mf"


@pytest.mark.parametrize(
    "placeholder",
    [
        "",
        "Projekt.3mf",
        "Project.3mf",
        "Druckplatte 1.3mf",
        "Plate 2.3mf",
        "Druckauftrag.3mf",
    ],
)
def test_placeholder_project_names_are_rejected(
    placeholder: str,
) -> None:
    with pytest.raises(
        direct_print.DirectPrintError,
        match="echter Projektname",
    ):
        direct_print.build_remote_3mf_filename(placeholder, 0)


def test_non_replayable_command_builders_always_use_qos_zero() -> None:
    assert network_commands.build_project_file(file="x.3mf").qos == 0
    assert network_commands.build_print_control("resume").qos == 0
    assert network_commands.build_print_control("pause").qos == 1
    assert network_commands.build_print_control("stop").qos == 1
    assert commands.command_qos("resume") == 0
    assert commands.command_qos("retry") == 0
    assert commands.command_qos("pause") == 1
    assert commands.command_qos("stop") == 1


class _PublishReceipt:
    rc = 0
    mid = 42

    @staticmethod
    def wait_for_publish(timeout: float) -> None:
        del timeout

    @staticmethod
    def is_published() -> bool:
        return True


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def publish(
        self,
        topic: str,
        message: str,
        *,
        qos: int,
        retain: bool,
    ) -> _PublishReceipt:
        self.calls.append(
            {
                "topic": topic,
                "message": message,
                "qos": qos,
                "retain": retain,
            }
        )
        return _PublishReceipt()


def _transport() -> object:
    transport = mqtt_transport.BambuLanMqttTransport.__new__(
        mqtt_transport.BambuLanMqttTransport
    )
    transport.serial = "SERIAL"
    transport.client = _FakeClient()
    transport._mqtt = SimpleNamespace(MQTT_ERR_SUCCESS=0)
    transport._ensure_connected = lambda: None
    transport.on_error = lambda _message: None
    return transport


@pytest.mark.parametrize(
    "payload",
    [
        {"print": {"command": "project_file"}},
        {"print": {"command": "resume"}},
        {
            "print": {
                "command": "ams_control",
                "param": "resume",
            }
        },
    ],
)
def test_transport_rejects_replayable_qos_for_start_like_commands(
    payload: dict[str, object],
) -> None:
    transport = _transport()
    with pytest.raises(RuntimeError, match="requires QoS 0"):
        transport.publish(payload, qos=1)
    assert transport.client.calls == []


def test_transport_publishes_start_qos_zero_without_retaining() -> None:
    transport = _transport()
    result = transport.publish(
        {"print": {"command": "project_file"}},
        qos=0,
    )
    assert result.confirmed is True
    assert result.qos == 0
    assert transport.client.calls == [
        {
            "topic": "device/SERIAL/request",
            "message": '{"print":{"command":"project_file"}}',
            "qos": 0,
            "retain": False,
        }
    ]


@pytest.mark.parametrize("filename", ["Projekt.3mf", "Projekt.gcode", "Projekt.gcode.3mf", "Projekt.GCODE.3MF"])
def test_remote_upload_name_has_exactly_one_gcode_suffix(filename: str) -> None:
    assert direct_print._safe_remote_filename(filename) == "Projekt.gcode.3mf"


def test_remote_upload_name_keeps_suffix_when_truncated() -> None:
    name = direct_print._safe_remote_filename("Ä" * 250 + ".3mf")
    assert len(name) == 180
    assert name.endswith(".gcode.3mf")
    assert direct_print._safe_remote_filename("") == "Druckauftrag.gcode.3mf"
