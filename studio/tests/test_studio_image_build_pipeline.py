"""Static image build orchestration contracts. No Docker/engine invocation in tests."""
from pathlib import Path
import ast
import hashlib
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / 'Slicer-Server/slicer-source-contract.yml'
BASE = ROOT / 'Slicer-Server/TARGET_BASE_REFERENCE.json'


class ImageBuildPipelineTests(unittest.TestCase):
    def setUp(self):
        self.workflow = WORKFLOW.read_text(encoding='utf-8-sig')
        self.job = self.workflow.split('\n  build-target-image:', 1)[1]
        self.base = json.loads(BASE.read_bytes())

    def test_one_new_job_and_original_source_job_preserved(self):
        self.assertEqual(self.workflow.count('\n  build-target-image:'), 1)
        self.assertIn('needs: verified-slicer-source', self.job)
        self.assertIn('python -m pytest -q tests', self.workflow)
        self.assertIn('python Slicer-Server/build_repository.py --verify .', self.workflow)

    def test_main_only_and_no_pull_request_target_execution(self):
        self.assertIn("if: github.ref == 'refs/heads/main' && github.event_name != 'pull_request'", self.job)
        self.assertNotIn('pull_request_target', self.workflow)

    def test_hosted_runner_bounded_and_no_deployment_environment(self):
        self.assertIn('runs-on: ubuntu-24.04', self.job)
        self.assertIn('timeout-minutes: 30', self.job)
        self.assertNotIn('self-hosted', self.job)
        self.assertNotIn('environment:', self.job)

    def test_no_repository_write_or_registry_credentials(self):
        self.assertIn('permissions:\n      contents: read', self.job)
        self.assertNotIn('contents: write', self.job)
        self.assertNotIn('packages: write', self.job)
        self.assertNotIn('secrets.', self.job)
        self.assertNotIn('docker login', self.job)
        self.assertNotIn('docker push', self.job)
        self.assertNotIn('persist-credentials: true', self.job)

    def test_base_is_official_platform_digest_and_matches_manifest(self):
        self.assertEqual(self.base['schema'], 1)
        self.assertEqual(self.base['platform'], 'linux/amd64')
        self.assertEqual(self.base['source_tag'], '3.13-slim-trixie')
        digest = self.base['platform_manifest_sha256']
        self.assertRegex(digest, r'^[0-9a-f]{64}$')
        self.assertEqual(self.base['base_image'], 'docker.io/library/python@sha256:' + digest)
        self.assertIn('PYTHON_BASE: ' + self.base['base_image'], self.job)
        self.assertFalse(self.base['target_image_verified'])
        self.assertFalse(self.base['production_approved'])

    def test_other_base_identities_are_sha256_not_mutable_tags(self):
        for key in ('registry_index_sha256', 'image_config_sha256'):
            with self.subTest(key=key):
                self.assertRegex(self.base[key], r'^[0-9a-f]{64}$')
        self.assertNotIn('python:latest', self.job)

    def test_new_external_workspace_and_export_within_same_step(self):
        self.assertIn('mktemp -d "$RUNNER_TEMP/slicer-image-XXXXXX"', self.job)
        self.assertIn('export IMAGE_BUILD_ROOT="$BUILD_ROOT"', self.job)
        self.assertIn('echo "IMAGE_BUILD_ROOT=$BUILD_ROOT" >> "$GITHUB_ENV"', self.job)
        self.assertIn('prepare_context.py --source-root "$PWD" --output "$BUILD_ROOT/context"', self.job)

    def test_build_uses_explicit_platform_digest_context_and_iid(self):
        self.assertIn('docker build --pull --no-cache --platform linux/amd64', self.job)
        self.assertIn('--build-arg "PYTHON_BASE=$PYTHON_BASE"', self.job)
        self.assertIn('--iidfile "$BUILD_ROOT/image-id.txt" "$BUILD_ROOT/context"', self.job)
        self.assertIn("re.fullmatch(r'sha256:[0-9a-f]{64}', image)", self.job)

    def test_no_host_bind_mounts_privilege_or_host_network(self):
        for value in ('--privileged', '--network host', '--pid host', '--mount', '--volume', ' -v ', '/var/run/docker.sock'):
            with self.subTest(value=value):
                self.assertNotIn(value, self.job)

    def test_all_inspection_containers_use_restrictions(self):
        self.assertIn('--network none --read-only --cap-drop ALL', self.job)
        self.assertIn('--security-opt no-new-privileges:true --pids-limit 128 --memory 512m --user 65532:65532', self.job)
        runs = [line.strip() for line in self.job.splitlines() if line.strip().startswith('docker run')]
        self.assertEqual(len(runs), 3)
        for line in runs:
            self.assertIn('"${ISOLATION[@]}" --entrypoint python3 "$IMAGE_ID"', line)

    def test_no_engine_invocation_worker_start_or_compose(self):
        for value in ('docker compose', 'bambu-studio --', 'prusa-slicer --', 'CuraEngine slice', 'container_service.py serve'):
            self.assertNotIn(value, self.job)
        self.assertIn('container_check.py check', self.job)
        self.assertIn('container_engines.py verify-image', self.job)

    def test_inventory_uses_existing_capture_and_independent_verify(self):
        self.assertIn('import target_image_sbom as s', self.job)
        self.assertIn('/usr/share/ultimate-slicer-server/debian-packages.tsv', self.job)
        self.assertIn('copyright_root=Path("/usr/share/doc")', self.job)
        self.assertIn('python Slicer-Server/target_image_sbom.py verify', self.job)
        self.assertIn('--reference Slicer-Server/TARGET_IMAGE_REFERENCE.json', self.job)

    def test_image_inspection_identity_and_nonroot_configuration_checked(self):
        for expression in ("inspection[0]['Id'] == image", "info['Os'] == 'linux'", "info['Architecture'] == 'amd64'", "info['Config']['User'] == '65532:65532'", "not info['Config'].get('Volumes')"):
            with self.subTest(expression=expression):
                self.assertIn(expression, self.job)

    def test_evidence_bound_to_commit_image_inputs_and_file_hashes(self):
        for key in ('source_commit', 'run_id', 'image_id', 'base_image', 'base_reference_sha256', 'dockerfile_sha256', 'source_manifest_sha256', 'context_manifest_sha256', 'evidence_files'):
            with self.subTest(key=key):
                self.assertIn("'" + key + "'", self.job)

    def test_image_success_not_confused_with_engine_or_installation(self):
        for key in ('engine_binaries_included', 'engine_executed', 'services_started', 'host_mounts_used', 'image_pushed', 'clean_linux_installation_verified', 'production_approved'):
            with self.subTest(key=key):
                self.assertIn("'" + key + "': False", self.job)

    def test_artifact_action_pinned_and_only_json_evidence_uploaded(self):
        self.assertIn('actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9', self.job)
        self.assertIn('path: ${{ env.IMAGE_BUILD_ROOT }}/evidence/*.json', self.job)
        self.assertIn('if-no-files-found: error', self.job)
        self.assertIn('overwrite: false', self.job)
        self.assertIn('include-hidden-files: false', self.job)
        self.assertNotIn('if: always()', self.job)
        self.assertNotIn('continue-on-error', self.job)

    def test_artifact_is_bound_to_run_and_attempt(self):
        self.assertIn('target-image-evidence-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}', self.job)
        self.assertIn('retention-days: 30', self.job)
        self.assertNotIn('docker save', self.job)

    def test_inline_python_heredocs_compile(self):
        lines = self.job.splitlines()
        blocks = []
        for index, line in enumerate(lines):
            if line.strip() == "python - <<'PY'":
                end = next(j for j in range(index + 1, len(lines)) if lines[j].strip() == 'PY')
                blocks.append('\n'.join(text[10:] for text in lines[index + 1:end]))
        self.assertEqual(len(blocks), 3)
        for block in blocks:
            ast.parse(block)

    def test_final_source_identity_check_precedes_artifact_upload(self):
        self.assertLess(self.job.rindex('python Slicer-Server/build_repository.py --verify .'), self.job.index('actions/upload-artifact@'))



    def test_docker_copy_inputs_survive_explicit_context_filter(self):
        # This project uses only deny-all followed by exact file/directory
        # exceptions, not arbitrary ignore globs. Real Docker validates the
        # complete semantics in the separate hosted image-build job.
        import shlex
        ignore = (ROOT / 'Slicer-Server/.dockerignore').read_text().splitlines()
        self.assertEqual(ignore[0], '**')
        exceptions = [line[1:] for line in ignore[1:] if line and not line.startswith('#')]
        self.assertTrue(all(line.startswith('!') for line in ignore[1:] if line and not line.startswith('#')))
        for name in exceptions:
            self.assertRegex(name, r'^[A-Za-z0-9_.-]+(?:/|/\*\*)?$')
        docker = (ROOT / 'Slicer-Server/Dockerfile').read_text(encoding='utf-8-sig')
        sources = []
        for line in docker.splitlines():
            if line.startswith('COPY '):
                arguments = [item for item in shlex.split(line)[1:] if not item.startswith('--')]
                self.assertGreaterEqual(len(arguments), 2)
                sources.extend(arguments[:-1])
        self.assertGreater(len(sources), 12)
        for source in sources:
            with self.subTest(copy_source=source):
                self.assertIn(source, exceptions)
                if source.endswith('/'):
                    self.assertIn(source + '**', exceptions)
        self.assertIn('TARGET_IMAGE_REFERENCE.json', sources)
        self.assertIn('target_image_sbom.py', sources)

    def test_context_filter_keeps_private_neighbors_excluded(self):
        lines = (ROOT / 'Slicer-Server/.dockerignore').read_text().splitlines()
        self.assertEqual(lines[0], '**')
        explicit = {line[1:] for line in lines[1:] if line.startswith('!')}
        self.assertFalse({'*', '**', '*.json', 'config.json', '.env', '.git/', 'credentials.json'} & explicit)
        self.assertEqual({line for line in explicit if line.endswith('/**')}, {'payload/**', 'licenses/**'})

if __name__ == '__main__':
    unittest.main()
