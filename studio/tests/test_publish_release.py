import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

module_path = Path(__file__).parents[1] / "Slicer-Server/publish_release.py"
spec = importlib.util.spec_from_file_location("publisher", module_path)
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)
SHA = "a" * 40


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = "Taracraft/3D-Ultimate-Center"
        self.prepare(self.repo)

    def prepare(self, repo):
        self.repo = repo
        config = publisher.SPECS[repo]
        path = self.root / config["version_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": config["version"]}))
        self.run = {"id": 123, "run_attempt": 1, "status": "completed", "conclusion": "success", "head_branch": "main",
                    "name": config["workflow"], "path": config["workflow_path"], "head_sha": SHA,
                    "event": "push", "repository": {"full_name": repo}, "head_repository": {"full_name": repo}}
        self.event = {"action": "completed", "repository": {"full_name": repo}, "workflow_run": copy.deepcopy(self.run)}
        self.env = {"GITHUB_REPOSITORY": repo, "GITHUB_EVENT_NAME": "workflow_run", "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": SHA}
        self.calls = []
        self.existing = None
        self.head = SHA
        self.tag_collision = False

    def api(self, method, path, body=None, allow_missing=False):
        self.calls.append((method, path, copy.deepcopy(body)))
        if path.endswith("/actions/runs/123"):
            return copy.deepcopy(self.run)
        if "/releases/tags/" in path:
            return self.existing
        if path.endswith("/git/ref/heads/main"):
            return {"object": {"sha": self.head}}
        if path.endswith("/git/refs"):
            if self.tag_collision:
                raise publisher.PublicationError("GitHub POST fehlgeschlagen: HTTP 422.")
            return {"ref": body["ref"], "object": {"sha": body["sha"]}}
        if path.endswith("/releases"):
            return {**body, "html_url": "https://github.com/" + self.repo + "/releases/tag/" + body["tag_name"]}
        self.fail("Unexpected endpoint " + path)

    def publish(self):
        return publisher.publish(self.event, self.env, self.root, self.api)

    def assert_rejected(self):
        with self.assertRaises(publisher.PublicationError):
            self.publish()
        self.assertFalse(any(method == "POST" for method, _, _ in self.calls))

    def test_source_version_pins_match_canonical_artifacts(self):
        root = module_path.parents[1]
        sources = {
            "Taracraft/3D-Ultimate-Slicer-Server": "packages/ultimate-slicer-server/release.json",
            "Taracraft/3D-Ultimate-Center": "deploy/homeassistant/custom_components/ultimate_3d_studio/manifest.json",
        }
        self.assertTrue((root / sources["Taracraft/3D-Ultimate-Slicer-Server"]).is_file())
        for repository, relative in sources.items():
            path = root / relative
            # The standalone Slicer projection intentionally excludes HA's manifest.
            if not path.is_file():
                self.assertEqual(repository, "Taracraft/3D-Ultimate-Center")
                continue
            with self.subTest(repository=repository):
                actual = json.loads(path.read_text(encoding="utf-8-sig"))["version"]
                self.assertEqual(publisher.SPECS[repository]["version"], actual)

    def test_success_exact_head_and_only_tag_then_release_mutations(self):
        result = self.publish()
        self.assertEqual(result["state"], "created")
        writes = [call for call in self.calls if call[0] == "POST"]
        self.assertEqual(len(writes), 2)
        self.assertTrue(writes[0][1].endswith("/git/refs"))
        self.assertEqual(writes[0][2], {"ref": "refs/tags/v" + publisher.SPECS[self.repo]["version"], "sha": SHA})
        self.assertEqual(writes[1][2]["target_commitish"], SHA)
        self.assertFalse(writes[1][2]["prerelease"])
        self.assertIn("Engine-Binärpakete", writes[1][2]["body"])

    def test_slicer_alpha_metadata_stays_prerelease(self):
        self.prepare("Taracraft/3D-Ultimate-Slicer-Server")
        result = self.publish()
        self.assertEqual(result["tag"], "v" + publisher.SPECS[self.repo]["version"])
        self.assertTrue(result["prerelease"])
        body = self.calls[-1][2]
        self.assertEqual(body["make_latest"], "false")

    def valid_existing(self):
        config = publisher.SPECS[self.repo]
        tag = "v" + config["version"]
        return {"html_url": f"https://github.com/{self.repo}/releases/tag/{tag}", "tag_name": tag,
                "target_commitish": SHA, "draft": False, "prerelease": config["prerelease"]}

    def test_existing_release_is_never_mutated(self):
        self.existing = self.valid_existing()
        self.assertEqual(self.publish()["state"], "existing_unchanged")
        self.assertFalse(any(method == "POST" for method, _, _ in self.calls))

    def test_existing_draft_is_not_published_or_overwritten(self):
        self.existing = {**self.valid_existing(), "draft": True}
        self.assert_rejected()

    def test_existing_release_with_wrong_commit_is_reconciliation(self):
        self.existing = {**self.valid_existing(), "target_commitish": "b" * 40}
        self.assert_rejected()

    def test_existing_release_with_branch_target_is_not_assumed_exact(self):
        self.existing = {**self.valid_existing(), "target_commitish": "main"}
        self.assert_rejected()

    def test_existing_release_without_url_is_reconciliation(self):
        self.existing = {**self.valid_existing(), "html_url": None}
        self.assert_rejected()

    def test_existing_release_wrong_prerelease_is_reconciliation(self):
        self.existing = {**self.valid_existing(), "prerelease": True}
        self.assert_rejected()

    def test_existing_release_wrong_tag_is_reconciliation(self):
        self.existing = {**self.valid_existing(), "tag_name": "v9.9.9"}
        self.assert_rejected()

    def test_tag_collision_aborts_without_release_or_new_name(self):
        self.tag_collision = True
        with self.assertRaises(publisher.PublicationError):
            self.publish()
        writes = [call for call in self.calls if call[0] == "POST"]
        self.assertEqual(len(writes), 1)
        self.assertTrue(writes[0][1].endswith("/git/refs"))

    def test_main_drift_aborts_before_tag(self):
        self.head = "b" * 40
        self.assert_rejected()

    def test_fork_run_is_rejected(self):
        self.event["workflow_run"]["head_repository"]["full_name"] = "other/fork"
        self.assert_rejected()

    def test_pull_request_run_is_rejected(self):
        self.event["workflow_run"]["event"] = "pull_request"
        self.assert_rejected()

    def test_ci_head_differs_from_trusted_checkout(self):
        self.event["workflow_run"]["head_sha"] = "b" * 40
        self.assert_rejected()

    def test_failure_is_rejected(self):
        self.event["workflow_run"]["conclusion"] = "failure"
        self.assert_rejected()

    def test_live_run_restarted_since_event_is_rejected(self):
        self.run["run_attempt"] = 2
        self.assert_rejected()

    def test_different_ci_workflow_path_is_rejected(self):
        self.run["path"] = ".github/workflows/untrusted.yml"
        self.assert_rejected()

    def test_metadata_drift_is_rejected(self):
        path = self.root / publisher.SPECS[self.repo]["version_path"]
        path.write_text('{"version":"9.9.9"}')
        self.assert_rejected()

    def test_other_event_is_rejected(self):
        self.env["GITHUB_EVENT_NAME"] = "pull_request_target"
        self.assert_rejected()

    def test_alternate_api_host_is_rejected(self):
        self.env["GITHUB_API_URL"] = "https://untrusted.invalid"
        self.assert_rejected()

    def test_no_tag_inventory_or_update_endpoints_are_used(self):
        self.publish()
        for method, path, _ in self.calls:
            self.assertIn(method, {"GET", "POST"})
            self.assertNotIn("/git/ref/tags", path)
            self.assertNotIn("/git/matching-refs", path)
            self.assertNotIn("/secrets", path)
            self.assertNotIn("/assets", path)


if __name__ == "__main__":
    unittest.main()
