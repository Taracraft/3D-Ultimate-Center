from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

COMPONENT = (
    Path(__file__).resolve().parents[1]
    / "deploy/homeassistant/custom_components/ultimate_3d_studio"
)
PACKAGE_NAME = "ultimate_3d_studio"
MODULE_NAME = f"{PACKAGE_NAME}.direct_print_views"


def _package(name: str) -> ModuleType:
    module = ModuleType(name)
    module.__path__ = []
    sys.modules[name] = module
    return module


homeassistant = _package("homeassistant")
components = _package("homeassistant.components")
http_module = ModuleType("homeassistant.components.http")
core_module = ModuleType("homeassistant.core")


class _HomeAssistantView:
    pass


class _HomeAssistant:
    pass


http_module.HomeAssistantView = _HomeAssistantView
core_module.HomeAssistant = _HomeAssistant
sys.modules[http_module.__name__] = http_module
sys.modules[core_module.__name__] = core_module
homeassistant.components = components
components.http = http_module
homeassistant.core = core_module

package = ModuleType(PACKAGE_NAME)
package.__path__ = [str(COMPONENT)]
sys.modules[PACKAGE_NAME] = package


def _stub(name: str, **values: object) -> None:
    module = ModuleType(f"{PACKAGE_NAME}.{name}")
    for key, value in values.items():
        setattr(module, key, value)
    sys.modules[module.__name__] = module


class _DirectPrintError(RuntimeError):
    pass


class _DirectPrintAuthorizationError(RuntimeError):
    pass


class _DirectPrintMaterialPlanError(RuntimeError):
    pass


class _SlicerServerConfigurationError(RuntimeError):
    pass


class _SlicerServerError(RuntimeError):
    pass


class _Runtime:
    pass


class _Router:
    pass


class _AuthoritativeAmsStart:
    pass


_stub(
    "bambu_direct_print",
    DirectPrintError=_DirectPrintError,
    build_remote_3mf_filename=lambda project_name, plate_index: (
        f"{project_name}_Druckplatte{int(plate_index) + 1}.3mf"
    ),
)
_stub("const", DATA_RUNTIMES="runtimes", DOMAIN="ultimate_3d_studio")
_stub(
    "direct_print_material_plan",
    AuthoritativeAmsStart=_AuthoritativeAmsStart,
    DirectPrintMaterialPlanError=_DirectPrintMaterialPlanError,
    derive_authoritative_ams_start=lambda *_args, **_kwargs: None,
)
_stub(
    "direct_print_runtime",
    DirectPrintAuthorizationError=_DirectPrintAuthorizationError,
    get_direct_print_runtime=lambda _hass: None,
)
_stub("runtime", Ultimate3DStudioRuntime=_Runtime)
_stub("slicer_backend_router", StudioSlicerBackendRouter=_Router)
_stub(
    "slicer_native_contract",
    SlicerServerConfigurationError=_SlicerServerConfigurationError,
    SlicerServerError=_SlicerServerError,
)

SPEC = importlib.util.spec_from_file_location(
    MODULE_NAME,
    COMPONENT / "direct_print_views.py",
)
assert SPEC and SPEC.loader
readiness = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = readiness
SPEC.loader.exec_module(readiness)

NOW = datetime(2026, 7, 18, 1, 30, tzinfo=timezone.utc)


def _printer(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "connection_state": "connected",
        "printer_state": "idle",
        "updated_at": NOW.isoformat(),
        "issues": [],
        "hms": [],
        "error_code": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_fresh_connected_idle_printer_is_ready() -> None:
    assert readiness._printer_ready(_printer(), now=NOW) == (True, "")


def test_failed_state_without_active_issue_is_recoverable() -> None:
    ready, reason = readiness._printer_ready(
        _printer(printer_state="failed"),
        now=NOW,
    )
    assert ready is True
    assert reason == ""


def test_active_blocking_hms_rejects_prepare_and_start_contract() -> None:
    ready, reason = readiness._printer_ready(
        _printer(
            hms=[{
                "code": "HMS_0500-0400-0001-0044",
                "active": True,
                "blocking": True,
                "severity": "error",
            }]
        ),
        now=NOW,
    )
    assert ready is False
    assert "HMS_0500-0400-0001-0044" in reason


def test_error_code_rejects_new_print_even_without_issue_list() -> None:
    ready, reason = readiness._printer_ready(
        _printer(error_code=50348044),
        now=NOW,
    )
    assert ready is False
    assert "50348044" in reason


def test_stale_snapshot_rejects_new_print() -> None:
    ready, reason = readiness._printer_ready(
        _printer(updated_at=(NOW - timedelta(seconds=31)).isoformat()),
        now=NOW,
    )
    assert ready is False
    assert "veraltet" in reason


def test_missing_snapshot_timestamp_rejects_new_print() -> None:
    ready, reason = readiness._printer_ready(
        _printer(updated_at=None),
        now=NOW,
    )
    assert ready is False
    assert "Aktualisierungszeitpunkt" in reason


def test_nonblocking_warning_does_not_block_idle_printer() -> None:
    ready, reason = readiness._printer_ready(
        _printer(
            issues=[{
                "code": "WARN_TEST",
                "active": True,
                "blocking": False,
                "severity": "warning",
            }]
        ),
        now=NOW,
    )
    assert ready is True
    assert reason == ""


def test_disconnected_printer_is_rejected_before_timestamp_check() -> None:
    ready, reason = readiness._printer_ready(
        _printer(connection_state="disconnected", updated_at=None),
        now=NOW,
    )
    assert ready is False
    assert "nicht verbunden" in reason
