"""Public product documentation, links and packaging boundaries."""
from pathlib import Path
import ast
import re
import unittest
from urllib.parse import unquote,urlsplit

ROOT=Path(__file__).resolve().parents[1]
COMPONENT=ROOT/'Slicer-Server'
STATUS=COMPONENT/'RELEASE_STATUS.md'


def text(path):
    return path.read_text(encoding='utf-8-sig')


def source_paths():
    tree=ast.parse((COMPONENT/'build_repository.py').read_bytes())
    node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SOURCE_PATHS' for t in n.targets))
    return ast.literal_eval(node.value)


def public_docs():
    return [ROOT/p for p in source_paths() if p.endswith('.md')]


def local_links(path):
    for target in re.findall(r'\]\(([^\s)]+)\)',text(path)):
        parts=urlsplit(target)
        if not parts.scheme and not parts.netloc and parts.path:
            yield (path.parent/unquote(parts.path)).resolve()


class ReleaseDocumentationTests(unittest.TestCase):
    def test_product_status_keeps_runtime_limitations_explicit(self):
        document=text(STATUS)
        for marker in ('keine Engine-Binaries','Runtime-Image','Supervisor-App','noch nicht veröffentlicht','Linux/amd64'):
            with self.subTest(marker=marker):self.assertIn(marker,document)

    def test_status_does_not_imply_that_documentation_unlocks_packages(self):
        document=text(STATUS)
        self.assertIn('release_complete=false',document)
        self.assertIn('production_approved=false',document)
        self.assertIn('nicht durch eine Änderung dieser Dokumentation',document)

    def test_component_manifest_excludes_private_reports(self):
        paths=source_paths()
        for name in ('LIVE_ENGINE_INVENTORY.md','LINUX_TEST_SERVER_RUNBOOK.md','WORK_SERVER_TEST_GUIDE.md','Release-Abnahme.md'):
            with self.subTest(name=name):self.assertFalse(any(p.endswith('/'+name) for p in paths))

    def test_public_pages_exclude_personal_context_and_internal_phase_order(self):
        patterns=(r'10[,.]?45\s*GB',r'10[ -]?GB-Frage',r'Brain\s*\d+',r'Nutzerauftrag',r'Tara-PC',r'Arbeitsplatz',r'Linux-Systemverifikation.*zuletzt',r'## [RVL]\s*[–:]')
        for page in public_docs():
            for pattern in patterns:
                with self.subTest(page=page.name,pattern=pattern):self.assertIsNone(re.search(pattern,text(page),re.I))

    def test_wiki_has_product_status_instead_of_internal_acceptance_page(self):
        paths=source_paths()
        self.assertIn('Slicer-Server/wiki/Entwicklungsstand.md',paths)
        for page in (COMPONENT/'wiki/Home.md',COMPONENT/'wiki/_Sidebar.md'):
            self.assertIn('Entwicklungsstand.md',text(page))
            self.assertNotIn('Release-Abnahme.md',text(page))

    def test_every_component_wiki_page_has_a_sidebar_entry(self):
        paths=source_paths();sidebar=text(COMPONENT/'wiki/_Sidebar.md')
        pages=[p for p in paths if p.startswith('Slicer-Server/wiki/') and not Path(p).name.startswith('_')]
        self.assertGreaterEqual(len(pages),10)
        for p in pages:
            with self.subTest(page=p):self.assertIn(Path(p).name,sidebar)

    def test_wiki_and_status_links_resolve_locally(self):
        pages=[STATUS]+[ROOT/p for p in source_paths() if p.startswith('Slicer-Server/wiki/')]
        for page in pages:
            for target in local_links(page):
                with self.subTest(page=page.name,target=target.name):
                    self.assertTrue(target.is_relative_to(ROOT.resolve()))
                    self.assertTrue(target.is_file())

    def test_neutral_linux_guide_is_in_test_package(self):
        tree=ast.parse((COMPONENT/'prepare_test_server_package.py').read_bytes())
        node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PACKAGE_FILES' for t in n.targets))
        paths=ast.literal_eval(node.value)
        self.assertIn('Slicer-Server/LINUX_SETUP.md',paths)
        self.assertNotIn('Slicer-Server/LINUX_TEST_SERVER_RUNBOOK.md',paths)
        self.assertTrue((COMPONENT/'LINUX_SETUP.md').is_file())

    def test_native_package_uses_neutral_developer_guide(self):
        source=text(ROOT/'packages/ultimate-slicer-server/build_target_testkit.py')
        self.assertIn('LINUX_TESTING.md',source)
        self.assertNotIn('WORK_SERVER_TEST_GUIDE.md',source)
        self.assertTrue((ROOT/'packages/ultimate-slicer-server/LINUX_TESTING.md').is_file())

    def test_repository_readme_template_links_work_at_root_and_source_location(self):
        document=text(COMPONENT/'REPOSITORY_README.md')
        self.assertEqual(list(local_links(COMPONENT/'REPOSITORY_README.md')),[])
        self.assertIn('/blob/main/Slicer-Server/INSTALLATION.md',document)
        self.assertIn('/blob/main/SOURCE_NOTICES.md',document)

    def test_public_component_pages_keep_license_and_installation_links(self):
        for page in (COMPONENT/'README.md',COMPONENT/'REPOSITORY_README.md'):
            self.assertIn('INSTALLATION.md',text(page))
            self.assertIn('THIRD_PARTY_NOTICES.md',text(page))
        for required in ('Slicer-Server/RELEASE_STATUS.md','tests/test_studio_release_documentation.py'):
            self.assertEqual(source_paths().count(required),1)


if __name__=='__main__':unittest.main()
