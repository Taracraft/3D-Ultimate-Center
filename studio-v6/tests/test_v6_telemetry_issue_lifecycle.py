"""Regression tests for Bambu printer issue activation and resolution."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = (
    ROOT
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio_v6"
)
PACKAGE_NAME = "ultimate_3d_studio_v6_telemetry_tests"

package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(PACKAGE_DIR)]
sys.modules.setdefault(PACKAGE_NAME, package)


def load_module(name: str):
    full_name = f"{PACKAGE_NAME}.{name}"
    spec = importlib.util.spec_from_file_location(full_name, PACKAGE_DIR / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


load_module("printer_issues")
telemetry = load_module("telemetry")


def test_blocking_issue_is_resolved_when_print_returns_to_running() -> None:
    state = telemetry.BambuTelemetryState()
    state.update({
        "print": {
            "gcode_state": "PAUSE",
            "print_error": 302022662,
            "hms": [{"attr": 83887104, "code": 65604}],
        }
    })

    assert state.error_code == 302022662
    assert len(state.issues) == 2
    assert state.issues[0]["code"] == "1200-8006"

    # Bambu sends partial updates. The old HMS list may remain in the merged
    # snapshot even though print_error is cleared and the print is running.
    state.update({
        "print": {
            "gcode_state": "RUNNING",
            "print_error": 0,
        }
    })

    assert state.printer_state == "running"
    assert state.error_code is None
    assert state.hms == []
    assert state.error_message is None
    assert state.issues == []


def test_explicit_error_clear_removes_stale_hms_even_if_failed_state_lingers() -> None:
    state = telemetry.BambuTelemetryState()
    state.update({
        "print": {
            "gcode_state": "FAILED",
            "print_error": 302022662,
            "hms": [{"attr": 83887104, "code": 65604}],
        }
    })

    assert state.printer_state == "failed"
    assert state.error_code == 302022662
    assert state.hms

    # The printer can leave gcode_state=FAILED after the physical condition was
    # acknowledged. An explicit error clear without a new HMS payload must
    # remove the previously merged HMS record instead of keeping it forever.
    state.update({
        "print": {
            "gcode_state": "FAILED",
            "print_error": 0,
        }
    })

    assert state.printer_state == "failed"
    assert state.error_code is None
    assert state.hms == []
    assert state.error_message is None
    assert state.issues == []


def test_new_hms_in_same_clear_packet_is_not_discarded() -> None:
    state = telemetry.BambuTelemetryState()
    state.update({
        "print": {
            "gcode_state": "FAILED",
            "print_error": 0,
            "hms": [{"attr": 83887104, "code": 65604}],
        }
    })

    assert state.error_code is None
    assert len(state.hms) == 1
    assert state.hms[0]["code"] == "HMS_0500-0400-0001-0044"


def test_non_blocking_hms_information_remains_visible_while_running() -> None:
    state = telemetry.BambuTelemetryState()
    informational_code = (4 << 16) | 68
    state.update({
        "print": {
            "gcode_state": "RUNNING",
            "print_error": 0,
            "hms": [{"attr": 83887104, "code": informational_code}],
        }
    })

    assert len(state.hms) == 1
    assert state.hms[0]["severity"] == "info"
    assert len(state.issues) == 1



def test_stale_hms_expires_after_confirmed_error_free_packets() -> None:
    state = telemetry.BambuTelemetryState()
    started = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    state.update({
        "print": {
            "gcode_state": "FAILED",
            "print_error": 0,
            "hms": [{"attr": 83887104, "code": 65604}],
        }
    }, now=started)
    assert state.hms

    state.update({"print": {"gcode_state": "FAILED"}}, now=started + timedelta(seconds=5))
    state.update({"print": {"gcode_state": "FAILED"}}, now=started + timedelta(seconds=10))
    assert state.hms

    state.update({"print": {"gcode_state": "FAILED"}}, now=started + timedelta(seconds=16))
    assert state.error_code is None
    assert state.hms == []
    assert state.issues == []


def test_new_hms_resets_stale_expiry_confirmation_window() -> None:
    state = telemetry.BambuTelemetryState()
    started = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    packet = {
        "print": {
            "gcode_state": "FAILED",
            "print_error": 0,
            "hms": [{"attr": 83887104, "code": 65604}],
        }
    }
    state.update(packet, now=started)
    state.update({"print": {"gcode_state": "FAILED"}}, now=started + timedelta(seconds=8))
    state.update(packet, now=started + timedelta(seconds=12))
    state.update({"print": {"gcode_state": "FAILED"}}, now=started + timedelta(seconds=20))
    state.update({"print": {"gcode_state": "FAILED"}}, now=started + timedelta(seconds=25))
    assert state.hms

    state.update({"print": {"gcode_state": "FAILED"}}, now=started + timedelta(seconds=28))
    assert state.hms == []