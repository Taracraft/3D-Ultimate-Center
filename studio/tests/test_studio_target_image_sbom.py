from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "Slicer-Server" / "target_image_sbom.py"
SPEC = importlib.util.spec_from_file_location("target_image_sbom", MODULE_PATH)
assert SPEC and SPEC.loader
target_image_sbom = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(target_image_sbom)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TargetImageSbomTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.reference = self.root / "reference.json"
        self.packages = self.root / "packages.tsv"
        self.docs = self.root / "doc"
        reference = {
            "schema": 1,
            "kind": "ultimate-slicer-target-image-package-reference",
            "dockerfile_sha256": "1" * 64,
            "host_reference_sha256": "2" * 64,
            "required_packages": ["jq", "libfoo1"],
            "production_approved": False,
            "target_image_verified": False,
        }
        self.reference.write_text(json.dumps(reference), encoding="utf-8")
        self.packages.write_text(
            "jq\t1.7-1\tamd64\tjq\t1.7-1\n"
            "libbar2:amd64\t2.0-1\tamd64\tbar\t2.0-1\n"
            "libfoo1:amd64\t1.0-2\tamd64\tfoo\t1.0-2\n",
            encoding="utf-8",
        )
        for package in ("jq", "libbar2", "libfoo1"):
            folder = self.docs / package
            folder.mkdir(parents=True)
            (folder / "copyright").write_bytes((package + " license\n").encode())
        self.base = "python@sha256:" + "a" * 64
        self.image = "sha256:" + "b" * 64

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def capture(self):
        return target_image_sbom.capture(
            reference_path=self.reference,
            packages_tsv=self.packages,
            copyright_root=self.docs,
            base_image=self.base,
            image_id=self.image,
        )

    def test_capture_and_verify_complete_inventory(self) -> None:
        result = self.capture()
        target_image_sbom.verify(result, self.reference)
        self.assertEqual(result["package_count"], 3)
        self.assertEqual(
            [item["binary_package"] for item in result["packages"]],
            ["jq", "libbar2", "libfoo1"],
        )
        self.assertFalse(result["production_approved"])
        self.assertFalse(result["runtime_approved"])
        self.assertTrue(result["target_inventory_complete"])
        self.assertEqual(
            result["packages"][0]["copyright_sha256"],
            sha256(b"jq license\n"),
        )

    def test_duplicate_reference_key_is_rejected(self) -> None:
        self.reference.write_text(
            '{"schema":1,"schema":1,"dockerfile_sha256":"' + "1" * 64
            + '","host_reference_sha256":"' + "2" * 64
            + '","required_packages":["jq"],"production_approved":false}',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(target_image_sbom.EvidenceError, "duplicate JSON key"):
            self.capture()

    def test_missing_required_package_is_rejected(self) -> None:
        self.packages.write_text("jq\t1.7-1\tamd64\tjq\t1.7-1\n", encoding="utf-8")
        with self.assertRaisesRegex(target_image_sbom.EvidenceError, "missing required packages"):
            self.capture()

    def test_mutable_base_or_image_identity_is_rejected(self) -> None:
        with self.assertRaisesRegex(target_image_sbom.EvidenceError, "base image"):
            target_image_sbom.capture(
                reference_path=self.reference,
                packages_tsv=self.packages,
                copyright_root=self.docs,
                base_image="python:3.13",
                image_id=self.image,
            )
        with self.assertRaisesRegex(target_image_sbom.EvidenceError, "image_id"):
            target_image_sbom.capture(
                reference_path=self.reference,
                packages_tsv=self.packages,
                copyright_root=self.docs,
                base_image=self.base,
                image_id="latest",
            )

    def test_linked_copyright_is_rejected(self) -> None:
        copyright_path = self.docs / "jq" / "copyright"
        copyright_path.unlink()
        copyright_path.symlink_to(self.docs / "libfoo1" / "copyright")
        with self.assertRaisesRegex(target_image_sbom.EvidenceError, "non-link"):
            self.capture()

    def test_duplicate_package_row_is_rejected(self) -> None:
        with self.packages.open("a", encoding="utf-8") as handle:
            handle.write("jq:amd64\t1.7-1\tamd64\tjq\t1.7-1\n")
        with self.assertRaisesRegex(target_image_sbom.EvidenceError, "duplicate binary package"):
            self.capture()

    def test_tampered_evidence_is_rejected(self) -> None:
        result = self.capture()
        tampered = copy.deepcopy(result)
        tampered["packages"][0]["copyright_sha256"] = "not-a-hash"
        with self.assertRaisesRegex(target_image_sbom.EvidenceError, "lowercase SHA-256"):
            target_image_sbom.verify(tampered, self.reference)

    def test_reference_hash_binds_evidence(self) -> None:
        result = self.capture()
        reference = json.loads(self.reference.read_text(encoding="utf-8"))
        reference["required_packages"].append("liblater3")
        self.reference.write_text(json.dumps(reference), encoding="utf-8")
        with self.assertRaisesRegex(target_image_sbom.EvidenceError, "reference hash mismatch"):
            target_image_sbom.verify(result, self.reference)

    def test_cli_refuses_to_overwrite_output(self) -> None:
        output = self.root / "evidence.json"
        output.write_text("existing", encoding="utf-8")
        with self.assertRaisesRegex(target_image_sbom.EvidenceError, "refusing to overwrite"):
            target_image_sbom.main(
                [
                    "capture",
                    "--reference", str(self.reference),
                    "--packages-tsv", str(self.packages),
                    "--copyright-root", str(self.docs),
                    "--base-image", self.base,
                    "--image-id", self.image,
                    "--output-new", str(output),
                ]
            )


if __name__ == "__main__":
    unittest.main()
