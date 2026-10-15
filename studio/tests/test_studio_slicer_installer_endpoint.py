"""Installer endpoint parser and provisioned mount contract regressions."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio"
          / "slicer_installer_endpoint.py")
spec = importlib.util.spec_from_file_location("studio_installer_endpoint_test", MODULE)
endpoint = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = endpoint
spec.loader.exec_module(endpoint)

HOST_ID = "a" * 32
SERVER_UID = 65532
SOCKET_DIR = "/run/ultimate-slicer-server/installer"
HANDOFF_DIR = "/run/ultimate-slicer-server/handoff"
PINS_DIR = "/run/ultimate-slicer-server/pins"


def payload(**overrides):
    value = {"schema": 1, "host_id": HOST_ID, "server_uid": SERVER_UID,
             "socket_directory": SOCKET_DIR, "handoff_directory": HANDOFF_DIR}
    value.update(overrides)
    return json.dumps(value, separators=(",", ":")).encode("ascii")


class InstallerEndpointTests(unittest.TestCase):
    def decode(self, data):
        return endpoint.decode_installer_endpoint(
            data, expected_host_id=HOST_ID, expected_server_uid=SERVER_UID,
            expected_socket_directory=SOCKET_DIR, expected_handoff_directory=HANDOFF_DIR)

    def test_accepts_exact_locally_pinned_contract(self):
        actual = self.decode(payload())
        self.assertEqual(actual.host_id, HOST_ID)
        self.assertEqual(actual.server_uid, SERVER_UID)
        self.assertEqual(actual.socket_directory, SOCKET_DIR)
        self.assertEqual(actual.handoff_directory, HANDOFF_DIR)

    def test_rejects_wrong_pinned_identity_or_uid(self):
        for change in ({"host_id": "b" * 32}, {"server_uid": 65531}):
            with self.subTest(change=change), self.assertRaisesRegex(
                    endpoint.InstallerEndpointError, "endpoint_pin_mismatch"):
                self.decode(payload(**change))

    def test_rejects_extra_or_missing_fields_and_wrong_schema(self):
        cases = (payload(untrusted_path="/tmp/other.sock"), json.dumps({"schema": 1}).encode("ascii"),
                 payload(schema=True))
        for data in cases:
            with self.subTest(data=data), self.assertRaisesRegex(
                    endpoint.InstallerEndpointError, "invalid_endpoint_schema"):
                self.decode(data)

    def test_rejects_duplicate_json_keys(self):
        raw = ('{"schema":1,"host_id":"' + HOST_ID + '","host_id":"' + HOST_ID
               + '","server_uid":65532,"socket_directory":"' + SOCKET_DIR
               + '","handoff_directory":"' + HANDOFF_DIR + '"}').encode("ascii")
        with self.assertRaisesRegex(endpoint.InstallerEndpointError, "duplicate_endpoint_key"):
            self.decode(raw)

    def test_rejects_relative_traversal_and_noncanonical_paths(self):
        for field, value in (("socket_directory", "run/installer"),
                             ("socket_directory", "/run/../tmp"),
                             ("socket_directory", "/run//installer"),
                             ("handoff_directory", "/run/./handoff"),
                             ("handoff_directory", "/")):
            with self.subTest(field=field, value=value), self.assertRaises(
                    endpoint.InstallerEndpointError):
                self.decode(payload(**{field: value}))

    def test_rejects_paths_that_do_not_match_local_pins(self):
        for change in ({"socket_directory": "/run/other/installer"},
                       {"handoff_directory": "/run/other/handoff"}):
            with self.subTest(change=change), self.assertRaisesRegex(
                    endpoint.InstallerEndpointError, "endpoint_pin_mismatch"):
                self.decode(payload(**change))

    def test_rejects_overlapping_directories(self):
        data = payload(handoff_directory=SOCKET_DIR)
        with self.assertRaisesRegex(endpoint.InstallerEndpointError, "overlapping_endpoint_directories"):
            endpoint.decode_installer_endpoint(data, expected_host_id=HOST_ID,
                expected_server_uid=SERVER_UID, expected_socket_directory=SOCKET_DIR,
                expected_handoff_directory=SOCKET_DIR)

    def test_rejects_boolean_uid_and_invalid_identity(self):
        with self.assertRaisesRegex(endpoint.InstallerEndpointError, "invalid_server_uid"):
            self.decode(payload(server_uid=True))
        with self.assertRaisesRegex(endpoint.InstallerEndpointError, "invalid_host_id"):
            endpoint.decode_installer_endpoint(payload(), expected_host_id="not-a-host",
                expected_server_uid=SERVER_UID, expected_socket_directory=SOCKET_DIR,
                expected_handoff_directory=HANDOFF_DIR)

    def test_rejects_oversized_or_non_ascii_data(self):
        with self.assertRaisesRegex(endpoint.InstallerEndpointError, "invalid_endpoint_size"):
            self.decode(b"x" * (endpoint.MAX_ENDPOINT_BYTES + 1))
        with self.assertRaisesRegex(endpoint.InstallerEndpointError, "invalid_endpoint_json"):
            self.decode(b'{"schema":1,"note":"\xff"}')

    def test_accepts_exact_pin_record(self):
        actual = endpoint.decode_installer_endpoint_pins(payload())
        self.assertEqual(actual.host_id, HOST_ID)

    def test_rejects_ambiguous_pin_records(self):
        cases = (payload(schema=True), payload(extra="x"),
                 payload(server_uid=True), payload(socket_directory="/run/../tmp"))
        for data in cases:
            with self.subTest(data=data), self.assertRaises(endpoint.InstallerEndpointError):
                endpoint.decode_installer_endpoint_pins(data)

    def test_mountinfo_finds_longest_mount_and_decodes_escapes(self):
        text = ("10 1 0:1 / /run rw - tmpfs tmpfs rw\n"
                "11 10 0:2 / /run/ultimate-slicer-server rw - tmpfs tmpfs rw\n"
                "12 11 0:3 / /run/ultimate-slicer-server/installer ro - tmpfs tmpfs ro\n"
                "13 11 0:4 / /run/ultimate-slicer-server/my\\040pins ro - tmpfs tmpfs ro\n")
        entries = endpoint._mount_entries(text)
        self.assertEqual(endpoint._covering_mount(SOCKET_DIR + "/endpoint.json", entries)[0], 12)
        self.assertEqual(endpoint._covering_mount("/run/ultimate-slicer-server/my pins/x", entries)[0], 13)

    def test_mount_layout_requires_three_separate_mounts(self):
        text = ("10 1 0:1 / /run rw - tmpfs tmpfs rw\n"
                "11 10 0:2 / /run/ultimate-slicer-server/pins ro - tmpfs tmpfs ro\n"
                "12 10 0:3 / /run/ultimate-slicer-server/installer ro - tmpfs tmpfs ro\n"
                "13 10 0:4 / /run/ultimate-slicer-server/handoff rw - tmpfs tmpfs rw\n")
        endpoint._validate_mount_layout(endpoint.PIN_FILE, endpoint.ENDPOINT_FILE, HANDOFF_DIR, text)

    def test_mount_layout_rejects_stacked_mount_at_trusted_path(self):
        for duplicate in (
            ("11 10 0:2 / /run/ultimate-slicer-server/pins ro - tmpfs tmpfs ro",
             "14 10 0:5 / /run/ultimate-slicer-server/pins rw - tmpfs tmpfs rw"),
            ("14 10 0:5 / /run/ultimate-slicer-server/pins rw - tmpfs tmpfs rw",
             "11 10 0:2 / /run/ultimate-slicer-server/pins ro - tmpfs tmpfs ro"),
        ):
            rows = [
                "10 1 0:1 / /run rw - tmpfs tmpfs rw",
                duplicate[0], duplicate[1],
                f"12 10 0:3 / {SOCKET_DIR} ro - tmpfs tmpfs ro",
                f"13 10 0:4 / {HANDOFF_DIR} rw - tmpfs tmpfs rw",
            ]
            with self.subTest(duplicate=duplicate), self.assertRaisesRegex(
                    endpoint.InstallerEndpointError, "endpoint_mount_ambiguous"):
                endpoint._validate_mount_layout(endpoint.PIN_FILE, endpoint.ENDPOINT_FILE,
                    HANDOFF_DIR, "\n".join(rows))

    def test_mount_layout_rejects_writable_pins_or_endpoint(self):
        for target in (PINS_DIR, SOCKET_DIR):
            rows = [
                "10 1 0:1 / /run rw - tmpfs tmpfs rw",
                f"11 10 0:2 / {PINS_DIR} ro - tmpfs tmpfs ro",
                f"12 10 0:3 / {SOCKET_DIR} ro - tmpfs tmpfs ro",
                f"13 10 0:4 / {HANDOFF_DIR} rw - tmpfs tmpfs rw",
            ]
            index = 1 if target == PINS_DIR else 2
            rows[index] = rows[index].replace(" ro ", " rw ").replace(" ro", " rw")
            with self.subTest(target=target), self.assertRaisesRegex(
                    endpoint.InstallerEndpointError, "endpoint_mount_policy"):
                endpoint._validate_mount_layout(endpoint.PIN_FILE, endpoint.ENDPOINT_FILE,
                    HANDOFF_DIR, "\n".join(rows))

    def test_mount_layout_rejects_shared_or_readonly_handoff_mount(self):
        shared = ("10 1 0:1 / /run rw - tmpfs tmpfs rw\n"
                  "11 10 0:2 / /run/ultimate-slicer-server/pins ro - tmpfs tmpfs ro\n"
                  "12 10 0:3 / /run/ultimate-slicer-server/installer ro - tmpfs tmpfs ro\n"
                  "12 10 0:3 / /run/ultimate-slicer-server/handoff rw - tmpfs tmpfs rw\n")
        with self.assertRaisesRegex(endpoint.InstallerEndpointError, "endpoint_mount_separation"):
            endpoint._validate_mount_layout(endpoint.PIN_FILE, endpoint.ENDPOINT_FILE, HANDOFF_DIR, shared)
        rows = shared.replace("12 10 0:3 / /run/ultimate-slicer-server/handoff rw - tmpfs tmpfs rw",
                              "13 10 0:4 / /run/ultimate-slicer-server/handoff ro - tmpfs tmpfs ro")
        with self.assertRaisesRegex(endpoint.InstallerEndpointError, "endpoint_mount_policy"):
            endpoint._validate_mount_layout(endpoint.PIN_FILE, endpoint.ENDPOINT_FILE, HANDOFF_DIR, rows)


if __name__ == "__main__":
    unittest.main()

