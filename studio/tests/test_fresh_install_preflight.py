from pathlib import Path
import re
import shlex

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/homeassistant/host/release/fresh-install-preflight.sh"


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8-sig")


def test_fresh_install_preflight_is_read_only_and_studio_only():
    text = source()
    forbidden = [
        "printer_control_center",
        "apt-get ",
        "apt ",
        "rm -",
        "cp -",
        "mv ",
        "systemctl start",
        "systemctl restart",
        "systemctl enable",
        "ha core restart",
        "/print/start",
        "startDirectPrint",
        "prepareDirectPrint",
    ]
    for marker in forbidden:
        assert marker not in text, marker
    assert "No files, services, jobs or printers were changed." in text


def test_fresh_install_preflight_validates_split_public_package():
    text = source()
    for path in [
        "homeassistant/custom_components/ultimate_3d_studio",
        "homeassistant/custom_components/printer_slicing_server",
        "homeassistant/www/3d-studio",
        "slicing-server",
        "deployment/systemd",
    ]:
        assert path in text
    assert 'case "$relative" in' in text
    assert 'systemd/*) source="$UNITS_SRC/' in text
    assert 'sha256sum "$source"' in text
    assert 'DEPENDENCY-SHA256SUMS' in text
    assert '[ "$count" -ge 11 ]' in text


def test_fresh_install_preflight_requires_idle_worker_and_pinned_engine():
    text = source()
    assert "*.slicing.json" in text
    assert "*.queued.json" in text
    assert "dispatcher.lock" in text
    assert "BAMBU_APPIMAGE_SHA256" in text
    assert "Bambu AppImage SHA-256 mismatch." in text
    assert "Reviewed Bambu runtime requires x86_64." in text
    assert 'TARGET_WORKER_ROOT" = "/var/lib/homeassistant/3d-printer-slicing-server"' in text


REVIEWED_UNITS = {
    "3d-printer-slicing-server.service",
    "3d-printer-slicing-dispatch.service",
    "3d-printer-slicing-dispatch.timer",
    "3d-printer-slicing-refresh.service",
    "3d-printer-slicing-refresh.timer",
}


def assert_reviewed_units(text: str) -> None:
    # Shell permits a single line or backslash-continued word list. Check its
    # actual members, not indentation, and still reject duplicates or omissions.
    loops = re.findall(r"(?ms)^for unit in[ \t]+(.+?)\n[ \t]*do[ \t]*$", text)
    assert len(loops) == 1
    units = shlex.split(loops[0].replace("\\\n", " "), comments=True)
    assert len(units) == len(REVIEWED_UNITS)
    assert set(units) == REVIEWED_UNITS


def test_fresh_install_preflight_requires_all_reviewed_systemd_units():
    assert_reviewed_units(source())


@pytest.mark.parametrize("joiner", [" ", " \\\n  "])
def test_unit_contract_accepts_both_valid_shell_layouts(joiner):
    assert_reviewed_units("for unit in " + joiner.join(sorted(REVIEWED_UNITS)) + "\ndo\n  :\ndone\n")


@pytest.mark.parametrize("change", ["missing", "duplicate", "foreign"])
def test_unit_contract_still_rejects_incomplete_or_extra_units(change):
    units = sorted(REVIEWED_UNITS)
    if change == "missing": units.pop()
    elif change == "duplicate": units.append(units[0])
    else: units[-1] = "foreign.service"
    with pytest.raises(AssertionError):
        assert_reviewed_units("for unit in " + " ".join(units) + "\ndo\n  :\ndone\n")
