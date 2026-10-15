"""Static checks for the independent, unprivileged Linux slicer service units.

No systemctl, root access, live printer, or slicing operation occurs.
"""
from __future__ import annotations

import configparser
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
UNITS = ROOT / "packages" / "ultimate-slicer-server" / "systemd"
PREFIX = "ultimate-slicer"


def read_unit(name: str):
    path = UNITS / name
    assert path.is_file() and not path.is_symlink()
    data = path.read_text(encoding="utf-8")
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read_string(data)
    return parser, data


def test_required_native_linux_units_are_version_neutral_and_complete():
    names = {p.name for p in UNITS.iterdir() if p.is_file()}
    assert names == {
        "ultimate-slicer-server.service",
        "ultimate-slicer-dispatch.service",
        "ultimate-slicer-refresh.service",
        "ultimate-slicer-dispatch.timer",
        "ultimate-slicer-refresh.timer",
    }


def test_services_use_dedicated_user_and_split_program_from_mutable_state():
    for name in (
        "ultimate-slicer-server.service",
        "ultimate-slicer-dispatch.service",
        "ultimate-slicer-refresh.service",
    ):
        parser, data = read_unit(name)
        service = parser["Service"]
        assert service["User"] == service["Group"] == "ultimate-slicer"
        assert service["ProtectSystem"] == "strict"
        assert service["NoNewPrivileges"] == "yes"
        assert service["PrivateTmp"] == "yes"
        assert service["ProtectHome"] == "yes"
        assert service["StateDirectory"] == "ultimate-slicer-server"
        assert service["Environment"].startswith("STUDIO_BAMBU_ROOT=")
        assert "/opt/ultimate-slicer-server" in data
        assert "/var/lib/ultimate-slicer-server" in data
        assert "/var/lib/homeassistant" not in data
        assert "User=root" not in data
        assert re.search(r"(?i)\bv[0-9]+(?:[._-][0-9]+)*\b", data) is None
        assert "beta-" not in data.casefold()



def test_native_dispatcher_inherits_engine_cli_library_and_locale_contract():
    _, data = read_unit("ultimate-slicer-dispatch.service")
    declared = {
        line.removeprefix("Environment=")
        for line in data.splitlines()
        if line.startswith("Environment=")
    }
    assert "LC_ALL=C" in declared
    assert (
        "LD_LIBRARY_PATH="
        "/opt/ultimate-slicer-server/engines/bambu-studio/squashfs-root/bin"
    ) in declared
    assert "EnvironmentFile=-/etc/ultimate-slicer-server/runtime.env" in data
    assert "/var/lib/homeassistant" not in data


def test_service_does_not_put_secret_on_command_line_or_in_environment():
    parser, data = read_unit("ultimate-slicer-server.service")
    exec_start = parser["Service"]["ExecStart"]
    assert exec_start.endswith(
        "/opt/ultimate-slicer-server/server.py /etc/ultimate-slicer-server/config.json"
    )
    assert "token" not in data.casefold()
    assert "password" not in data.casefold()


def test_timers_only_trigger_respective_slicer_units():
    for kind in ("dispatch", "refresh"):
        parser, data = read_unit(f"ultimate-slicer-{kind}.timer")
        assert parser["Timer"]["Unit"] == f"ultimate-slicer-{kind}.service"
        assert "WantedBy" in parser["Install"]
        assert "/var/lib/homeassistant" not in data
