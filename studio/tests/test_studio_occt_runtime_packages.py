"""Regression for the shipped Prusa STEP plugin's missing runtime libraries.

These are package/source contract tests, not a STEP conversion or engine run.
Actual ELF closure of the reviewed candidate is retained in private build evidence.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = frozenset({
    'libocct-data-exchange-7.8', 'libocct-foundation-7.8',
    'libocct-modeling-algorithms-7.8', 'libocct-modeling-data-7.8',
    'libocct-ocaf-7.8', 'libocct-visualization-7.8',
})

class OcctRuntimePackages(unittest.TestCase):
    def setUp(self):
        self.docker = (ROOT / 'Slicer-Server/Dockerfile').read_bytes()
        self.reference = json.loads((ROOT / 'Slicer-Server/TARGET_IMAGE_REFERENCE.json').read_bytes())

    def test_all_step_plugin_runtime_families_are_installed(self):
        found = set(re.findall(r'(?m)^\s+([a-z][a-z0-9+.-]*)\s+\\$', self.docker.decode('utf-8-sig')))
        self.assertTrue(PACKAGES <= found, sorted(PACKAGES - found))

    def test_package_evidence_requires_every_occt_runtime_family(self):
        self.assertTrue(PACKAGES <= set(self.reference['required_packages']))
        self.assertEqual(len(self.reference['required_packages']), len(set(self.reference['required_packages'])))
        self.assertEqual(self.reference['required_package_count'], len(self.reference['required_packages']))

    def test_exact_docker_bytes_are_bound_to_package_reference(self):
        self.assertEqual(self.reference['dockerfile_sha256'], hashlib.sha256(self.docker).hexdigest())

    def test_no_system_slicer_is_installed_as_a_workaround(self):
        found = set(re.findall(r'(?m)^\s+([a-z][a-z0-9+.-]*)\s+\\$', self.docker.decode('utf-8-sig')))
        self.assertFalse({'prusaslicer', 'bambustudio', 'cura', 'curaengine'} & found)

    def test_regression_is_in_standalone_slicer_delivery(self):
        builder = (ROOT / 'Slicer-Server/build_repository.py').read_text(encoding='utf-8-sig')
        self.assertIn(chr(34) + 'tests/test_studio_occt_runtime_packages.py' + chr(34), builder)

    def test_dependencies_do_not_grant_approval(self):
        self.assertIs(self.reference['production_approved'], False)
        self.assertIs(self.reference['target_image_verified'], False)

    def test_vendor_library_scope_remains_per_bambu_invocation(self):
        script = (ROOT / 'deploy/homeassistant/host/3d-printer-slicing-server/dispatch-job.sh').read_text(encoding='utf-8-sig')
        self.assertEqual(script.count('LD_LIBRARY_PATH="$ROOT/bin"'), 2)
        self.assertNotIn('ENV LD_LIBRARY_PATH=', self.docker.decode('utf-8-sig'))

if __name__ == '__main__':
    unittest.main()
