"""Release documentation contracts, without changing any release/runtime state.

These tests check phase separation, local references and source projection scope.
They do not evaluate legal obligations, engine readiness or product acceptance.
"""
from pathlib import Path
import ast
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "Slicer-Server"
STATUS = COMPONENT / "RELEASE_STATUS.md"
MATRIX = COMPONENT / "wiki/Release-Abnahme.md"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def local_links(path: Path):
    """Resolve relative Markdown targets; remote resources are not fetched."""
    for target in re.findall(r"\]\(([^\s)]+)\)", text(path)):
        parts = urlsplit(target)
        if parts.scheme or parts.netloc or not parts.path:
            continue
        yield (path.parent / unquote(parts.path)).resolve()


class ReleaseDocumentationTests(unittest.TestCase):
    def test_release_precedes_final_system_verification_and_live_is_separate(self):
        document = text(STATUS)
        release = document.index("## R – ")
        system = document.index("## V – ")
        live = document.index("## L – ")
        self.assertLess(release, system)
        self.assertLess(system, live)
        self.assertIn("`not_run`", document[release:system])
        self.assertIn("Host-/HA-Integration", document[release:system])
        self.assertIn("konkrete Enginepakete", document[release:system])
        self.assertIn("veröffentlichten, unveränderten Release", document[system:live])

    def test_release_matrix_keeps_real_delivery_requirements_before_linux(self):
        document = text(MATRIX)
        release = document[document.index("## R:"):document.index("## V:")]
        for required in ("Host-/HA-Integration", "Engines", "HACS", "Öffentliche Lieferung", "Bedien"):
            with self.subTest(required=required):
                self.assertIn(required, release)
        self.assertIn("vollständigen", release)
        self.assertIn("not_run", document)
        self.assertIn("zweistufige Bestätigung", document)

    def test_existing_component_verifiers_are_not_product_release_approvals(self):
        document = text(STATUS)
        section = document[document.index("## Aussagen der bestehenden Prüfwerkzeuge"):]
        for marker in ("verify_image_evidence.py", "linux_test_evidence.py",
                       "release_complete=false", "production_approved=false",
                       "container_deploy_ready", "native_deploy_ready"):
            with self.subTest(marker=marker):
                self.assertIn(marker, section)
        self.assertIn("nicht aufgrund dieser", section)

    def test_runtime_image_and_source_preflight_evidence_are_distinguished(self):
        document = text(STATUS)
        self.assertIn("Source-Preflight-Image", document)
        self.assertIn("Keine Engine-Binaries", document)
        self.assertIn("Runtime-Image", document)
        self.assertIn("ursprüngliche", document)
        self.assertIn("geändertes `main`", document)

    def test_snapshot_candidates_are_not_labelled_public_releases(self):
        document = text(STATUS)
        self.assertIn("Reproduzierbarer privater Kandidat", document)
        self.assertIn("Kein veröffentlichter HACS-Release", document)
        self.assertIn("Wiki deaktiviert", document)
        self.assertIn("datierte Nachweise", document)
        self.assertIn("beide Release-Listen leer", document)

    def test_all_component_entrypoints_link_the_same_release_definition(self):
        pages = [COMPONENT / "README.md", COMPONENT / "REPOSITORY_README.md",
                 COMPONENT / "DOCKER_QUICKSTART.md", COMPONENT / "LINUX_TEST_SERVER_RUNBOOK.md",
                 COMPONENT / "wiki/Home.md", MATRIX]
        for page in pages:
            with self.subTest(page=page.name):
                self.assertIn("RELEASE_STATUS.md", text(page))

    def test_shared_status_and_matrix_have_resolvable_local_links(self):
        for page in (STATUS, MATRIX):
            for target in local_links(page):
                with self.subTest(page=page.name, target=target.name):
                    self.assertTrue(target.is_relative_to(ROOT.resolve()))
                    self.assertTrue(target.is_file(), str(target))

    def test_stale_test_first_publication_order_is_removed_from_current_entrypoints(self):
        for page in (MATRIX, COMPONENT / "REPOSITORY_README.md"):
            document = text(page)
            for stale in ("Erst danach privaten Pilot", "anschliessend privater Pilot und Release",
                          "Erst nach Linux/Engine/HA/HACS"):
                with self.subTest(page=page.name, stale=stale):
                    self.assertNotIn(stale, document)

    def test_testserver_runbook_uses_published_release_without_private_additions(self):
        document = text(COMPONENT / "LINUX_TEST_SERVER_RUNBOOK.md")
        start = document.index("## Reihenfolge vor dem Testserver")
        end = document.index("## Erzeugtes Testserverpaket", start)
        section = document[start:end]
        self.assertIn("nach", section)
        self.assertIn("Release R", section)
        self.assertIn("Nicht nur einen GitHub-", section)
        self.assertIn("keine unveröffentlichten", section)

    def test_status_document_and_tests_are_in_complete_slicer_source_projection(self):
        tree = ast.parse((COMPONENT / "build_repository.py").read_bytes())
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == "SOURCE_PATHS"
                                  for target in node.targets))
        paths = ast.literal_eval(assignment.value)
        for required in ("Slicer-Server/RELEASE_STATUS.md", "tests/test_studio_release_documentation.py"):
            with self.subTest(required=required):
                self.assertEqual(paths.count(required), 1)


if __name__ == "__main__":
    unittest.main()
