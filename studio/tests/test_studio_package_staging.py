"""Synthetic package staging tests; never execute downloaded programs."""
from dataclasses import replace
import gzip
import hashlib
import io
import json
import lzma
from pathlib import Path
import shutil
import ssl
import stat
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Slicer-Server"))
import engine_catalog as catalog
import package_staging as staging

BASE = {
    "usr/bin/CuraEngine": (b"synthetic engine bytes, never executed", "bin/CuraEngine", "engine", True),
    "usr/share/cura/resources/base.json": (b"{}", "resources/base.json", "resources", False),
    "usr/share/cura/resources/definitions/fdmprinter.def.json":
        (b'{"version":2}', "resources/definitions/fdmprinter.def.json", "profiles", False),
    "usr/share/doc/cura/copyright": (b"synthetic notice", "licenses/NOTICE", "license", False),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tar_bytes(entries=None):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, data, kind in entries or [(n, v[0], "file") for n, v in BASE.items()]:
            info = tarfile.TarInfo(name)
            info.mode = 0o6777
            if kind == "file":
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            else:
                info.type = {"link": tarfile.SYMTYPE, "hardlink": tarfile.LNKTYPE,
                             "directory": tarfile.DIRTYPE, "fifo": tarfile.FIFOTYPE}[kind]
                info.linkname = "../../escape" if kind in {"link", "hardlink"} else ""
                archive.addfile(info)
    return output.getvalue()


def ar_member(name, data):
    header = f"{name:<16}{0:<12}{0:<6}{0:<6}{'100644':<8}{len(data):<10}".encode() + b"\x60\n"
    assert len(header) == 60
    return header + data + (b"\n" if len(data) % 2 else b"")


def deb_bytes(data, *, name="data.tar.xz", control=b"must never be interpreted"):
    return b"!<arch>\n" + ar_member("debian-binary", b"2.0\n") + ar_member("control.tar.xz", control) + ar_member(name, data)


def zip_bytes(entries=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data, kind in entries or [(n, v[0], "file") for n, v in BASE.items()]:
            info = zipfile.ZipInfo(name + ("/" if kind == "directory" else ""))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((stat.S_IFLNK if kind == "link" else stat.S_IFDIR if kind == "directory"
                                   else stat.S_IFREG) | 0o6777) << 16
            archive.writestr(info, data)
    return output.getvalue()


def artifact(data, form="tar"):
    files = tuple(catalog.FileSpec(path, sha(content), len(content), role, executable, archive_path)
                  for archive_path, (content, path, role, executable) in BASE.items())
    return catalog.Artifact("package", "5.0.0", "https://deb.debian.org/debian/pool/cura.deb",
                            sha(data), len(data), form, "synthetic-test",
                            "https://github.com/Ultimaker/CuraEngine/tree/" + "a" * 40,
                            "a" * 40, files)


def release(art):
    return catalog.Release("curaengine", "5.0.0", "amd64", (art,))


class Response(io.BytesIO):
    def __init__(self, data, *, status=200, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers if headers is not None else [("Content-Length", str(len(data)))]
    def getheaders(self):
        return self.headers


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.parent = self.root / "private"
        self.parent.mkdir(mode=0o700)

    def run_local(self, data, form="tar", art=None, **kwargs):
        source = self.root / "source.archive"
        source.write_bytes(data)
        return staging.prepare_release(release(art or artifact(data, form)), self.parent,
                                       archives={"package": source}, **kwargs)

    def assert_clean(self):
        self.assertEqual(list(self.parent.iterdir()), [])

    def assert_payload(self, work):
        payload = work / "payload/curaengine"
        self.assertEqual({p.relative_to(payload).as_posix() for p in payload.rglob("*") if p.is_file()},
                         {v[1] for v in BASE.values()})
        for content, target, _, executable in BASE.values():
            self.assertEqual((payload / target).read_bytes(), content)
            if sys.platform != "win32":
                self.assertEqual(stat.S_IMODE((payload / target).stat().st_mode), 0o755 if executable else 0o644)
        receipt = json.loads((work / "READY.json").read_text())
        self.assertFalse(receipt["activated"])
        self.assertFalse(receipt["engine_executed"])
        self.assertEqual({p.name for p in work.iterdir()}, {"payload", "READY.json"})

    def test_all_supported_formats(self):
        raw = tar_bytes()
        for form, data in [("tar", raw), ("tar.gz", gzip.compress(raw)),
                           ("tar.xz", lzma.compress(raw)), ("zip", zip_bytes()),
                           ("deb", deb_bytes(lzma.compress(raw))),
                           ("deb", deb_bytes(gzip.compress(raw), name="data.tar.gz")),
                           ("deb", deb_bytes(raw, name="data.tar"))]:
            with self.subTest(form=form):
                work = self.run_local(data, form)
                self.assert_payload(work)
                shutil.rmtree(work)

    def test_fresh_directories_allow_independent_preparation(self):
        data = tar_bytes()
        first = self.run_local(data)
        second = self.run_local(data)
        self.assertNotEqual(first, second)
        self.assert_payload(first)
        self.assert_payload(second)

    def test_catalog_old_paths_and_mapping(self):
        art = artifact(tar_bytes())
        checked = staging._checked_release(release(art))
        self.assertEqual(checked.artifacts[0].files[0].archive_path, "usr/bin/CuraEngine")
        legacy = replace(art, files=tuple(replace(f, archive_path=None) for f in art.files))
        self.assertIsNone(staging._checked_release(release(legacy)).artifacts[0].files[0].archive_path)

    def test_catalog_rejects_unsafe_archive_mapping(self):
        art = artifact(tar_bytes())
        for value in ["../file", "/file", "C:/file", "a\\b", "a/./b"]:
            with self.subTest(value=value), self.assertRaises(catalog.CatalogError):
                staging._checked_release(release(replace(art, files=(replace(art.files[0], archive_path=value), *art.files[1:]))))

    def test_catalog_rejects_duplicate_archive_mapping(self):
        art = artifact(tar_bytes())
        changed = replace(art.files[1], archive_path=art.files[0].archive_path.upper())
        with self.assertRaisesRegex(catalog.CatalogError, "conflicting_archive_paths"):
            staging._checked_release(release(replace(art, files=(art.files[0], changed, *art.files[2:]))))

    def test_rejects_wrong_archive_digest(self):
        data = tar_bytes()
        with self.assertRaisesRegex(staging.StagingError, "file_digest_mismatch"):
            self.run_local(data, art=replace(artifact(data), sha256="0" * 64))
        self.assert_clean()

    def test_rejects_wrong_archive_size(self):
        data = tar_bytes()
        for delta in [-1, 1]:
            with self.subTest(delta=delta), self.assertRaises(staging.StagingError):
                self.run_local(data, art=replace(artifact(data), size_bytes=len(data) + delta))
            self.assert_clean()

    def test_missing_file_and_wrong_file_digest(self):
        data = tar_bytes()
        art = artifact(data)
        for field in [{"archive_path": "missing/file"}, {"sha256": "0" * 64}, {"size_bytes": 99}]:
            with self.subTest(field=field), self.assertRaises(staging.StagingError):
                self.run_local(data, art=replace(art, files=(replace(art.files[0], **field), *art.files[1:])))
            self.assert_clean()

    def test_tar_paths_rejected_even_when_unselected(self):
        base = [(n, v[0], "file") for n, v in BASE.items()]
        for name in ["../escape", "/escape", "a/../../escape", "a\\escape", "C:/escape", "a//escape"]:
            with self.subTest(name=name), self.assertRaisesRegex(staging.StagingError, "unsafe_member_path"):
                self.run_local(tar_bytes(base + [(name, b"bad", "file")]))
            self.assert_clean()
        self.assertFalse((self.root / "escape").exists())

    def test_duplicate_members_rejected(self):
        entries = [(n, v[0], "file") for n, v in BASE.items()]
        with self.assertRaisesRegex(staging.StagingError, "duplicate_member"):
            self.run_local(tar_bytes(entries + [entries[0]]))
        self.assert_clean()

    def test_unselected_links_not_created_or_followed(self):
        entries = [(n, v[0], "file") for n, v in BASE.items()]
        work = self.run_local(tar_bytes(entries + [("desktop/link", b"", "link"), ("desktop/hard", b"", "hardlink")]))
        self.assert_payload(work)

    def test_selected_link_rejected(self):
        entries = [(n, v[0], "file") for n, v in BASE.items()]
        for kind in ["link", "hardlink", "directory"]:
            changed = [(entries[0][0], b"", kind), *entries[1:]]
            with self.subTest(kind=kind), self.assertRaisesRegex(staging.StagingError, "selected_not_regular"):
                self.run_local(tar_bytes(changed))
            self.assert_clean()

    def test_special_file_rejected(self):
        entries = [(n, v[0], "file") for n, v in BASE.items()]
        with self.assertRaisesRegex(staging.StagingError, "special_member"):
            self.run_local(tar_bytes(entries + [("special", b"", "fifo")]))
        self.assert_clean()

    def test_expansion_budget(self):
        data = gzip.compress(tar_bytes())
        with patch.object(staging, "MAX_EXPANDED", 100), self.assertRaisesRegex(staging.StagingError, "expanded_limit"):
            self.run_local(data, "tar.gz")
        self.assert_clean()

    def test_member_and_count_budgets(self):
        data = tar_bytes()
        for name, value in [("MAX_MEMBER", 1), ("MAX_ENTRIES", 1)]:
            with self.subTest(name=name), patch.object(staging, name, value), self.assertRaisesRegex(staging.StagingError, "archive_limit"):
                self.run_local(data)
            self.assert_clean()

    def test_truncated_and_concatenated_compression(self):
        raw = tar_bytes()
        for form, data in [("tar.gz", gzip.compress(raw)[:-4]), ("tar.xz", lzma.compress(raw)[:-4]),
                           ("tar.gz", gzip.compress(raw) + gzip.compress(raw)),
                           ("tar.xz", lzma.compress(raw) + lzma.compress(raw))]:
            with self.subTest(form=form), self.assertRaises(staging.StagingError):
                self.run_local(data, form)
            self.assert_clean()

    def test_bad_tar_header_and_end(self):
        raw = tar_bytes()
        for data in [b"bad" + raw[3:], raw[:513], raw[:512], raw[:-1] + b"x"]:
            with self.subTest(size=len(data)), self.assertRaises(staging.StagingError):
                self.run_local(data)
            self.assert_clean()

    def test_deb_rejects_unsupported_version_or_members(self):
        raw = deb_bytes(lzma.compress(tar_bytes()))
        for data in [raw.replace(b"2.0\n", b"3.0\n", 1), raw + ar_member("extra", b"x"),
                     deb_bytes(b"x", name="data.tar.zst"), raw[:-1]]:
            with self.subTest(size=len(data)), self.assertRaises(staging.StagingError):
                self.run_local(data, "deb")
            self.assert_clean()

    def test_zip_paths_links_and_limits(self):
        entries = [(n, v[0], "file") for n, v in BASE.items()]
        with self.assertRaisesRegex(staging.StagingError, "unsafe_member_path"):
            self.run_local(zip_bytes(entries + [("../escape", b"x", "file")]), "zip")
        self.assert_clean()
        with self.assertRaisesRegex(staging.StagingError, "selected_not_regular"):
            self.run_local(zip_bytes([(entries[0][0], b"../../escape", "link"), *entries[1:]]), "zip")
        self.assert_clean()
        with patch.object(staging, "MAX_ZIP_DIRECTORY", 1), self.assertRaisesRegex(staging.StagingError, "unsupported_zip"):
            self.run_local(zip_bytes(), "zip")
        self.assert_clean()

    def test_invalid_cache_mapping(self):
        with self.assertRaisesRegex(staging.StagingError, "invalid_cache_mapping"):
            staging.prepare_release(release(artifact(tar_bytes())), self.parent, archives={})
        self.assert_clean()

    def test_cancel_before_and_during_staging(self):
        with self.assertRaisesRegex(staging.StagingError, "cancelled"):
            self.run_local(tar_bytes(), cancelled=lambda: True)
        self.assert_clean()
        calls = []
        def cancel():
            calls.append(1)
            return len(calls) > 6
        with self.assertRaisesRegex(staging.StagingError, "cancelled"):
            self.run_local(tar_bytes(), cancelled=cancel)
        self.assert_clean()

    def test_deadline(self):
        with patch.object(staging, "OPERATION_SECONDS", -1), self.assertRaisesRegex(staging.StagingError, "deadline_exceeded"):
            self.run_local(tar_bytes())
        self.assert_clean()

    def test_unrelated_data_preserved_after_failure(self):
        marker = self.parent / "existing.txt"
        marker.write_text("keep")
        with self.assertRaises(staging.StagingError):
            self.run_local(tar_bytes(), art=replace(artifact(tar_bytes()), sha256="0" * 64))
        self.assertEqual(list(self.parent.iterdir()), [marker])
        self.assertEqual(marker.read_text(), "keep")

    def test_symlink_parent_rejected(self):
        alias = self.root / "alias"
        try:
            alias.symlink_to(self.parent, target_is_directory=True)
        except OSError:
            self.skipTest("Symlink privilege unavailable")
        with self.assertRaisesRegex(staging.StagingError, "unsafe_parent"):
            staging.prepare_release(release(artifact(tar_bytes())), alias)

    def test_symlink_archive_rejected(self):
        source = self.root / "real"
        source.write_bytes(tar_bytes())
        alias = self.root / "alias"
        try:
            alias.symlink_to(source)
        except OSError:
            self.skipTest("Symlink privilege unavailable")
        with self.assertRaisesRegex(staging.StagingError, "unsafe_archive"):
            staging.prepare_release(release(artifact(tar_bytes())), self.parent, archives={"package": alias})
        self.assert_clean()

    def test_shared_parent_rejected_on_linux(self):
        if sys.platform == "win32":
            self.skipTest("POSIX ownership/mode contract")
        self.parent.chmod(0o777)
        with self.assertRaisesRegex(staging.StagingError, "parent_not_private"):
            self.run_local(tar_bytes())

    def test_target_case_conflict_and_reserved_name(self):
        art = artifact(tar_bytes())
        for target in ["Resources/definitions/fdmprinter.def.json", "resources/CON.txt"]:
            changed = replace(art.files[2], path=target)
            # First remains a valid profile path only for the lower-level target guard.
            with self.subTest(target=target), self.assertRaises(staging.StagingError):
                staging._target_contract((art.files[1], changed))

    def network(self, response, art=None):
        data = tar_bytes()
        with patch.object(staging.http.client, "HTTPSConnection") as connection:
            connection.return_value.getresponse.return_value = response
            result = staging.prepare_release(release(art or artifact(data)), self.parent)
            context = connection.call_args.kwargs["context"]
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
            self.assertEqual(connection.call_args.kwargs["timeout"], 20)
            connection.return_value.close.assert_called_once()
            return result

    def test_download_tls_and_success(self):
        self.assert_payload(self.network(Response(tar_bytes())))

    def test_download_chunked_success(self):
        self.assert_payload(self.network(Response(tar_bytes(), headers=[("Transfer-Encoding", "chunked")])))

    ASSET_LOCATION = ("https://release-assets.githubusercontent.com/"
                      "github-production-release-asset/123456/"
                      "01234567-89ab-cdef-0123-456789abcdef?signature=synthetic%2Bvalue")
    RELEASE_URL = "https://github.com/Ultimaker/CuraEngine/releases/download/5.0.0/engine.tar"

    def github_network(self, first=None, second=None, *, art=None, cancelled=None):
        first = first if first is not None else Response(
            b"untrusted redirect body", status=302, headers=[("Location", self.ASSET_LOCATION)])
        second = second if second is not None else Response(tar_bytes())
        origin, asset = Mock(), Mock()
        origin.getresponse.return_value = first
        asset.getresponse.return_value = second
        with patch.object(staging.http.client, "HTTPSConnection", side_effect=[origin, asset]) as factory:
            try:
                work = staging.prepare_release(
                    release(art or replace(artifact(tar_bytes()), url=self.RELEASE_URL)),
                    self.parent, cancelled=cancelled)
            finally:
                self.last_hops = (factory, origin, asset)
            return work

    def test_github_single_asset_hop_preserves_payload_and_tls(self):
        work = self.github_network(first=Response(b"", status=302, headers=[
            ("Location", self.ASSET_LOCATION), ("Set-Cookie", "synthetic=not-forwarded"),
            ("Authorization", "synthetic-not-forwarded")]))
        self.assert_payload(work)
        factory, origin, asset = self.last_hops
        self.assertEqual(factory.call_count, 2)
        self.assertEqual([c.args for c in factory.call_args_list],
                         [("github.com", 443), ("release-assets.githubusercontent.com", 443)])
        for call in factory.call_args_list:
            self.assertEqual(call.kwargs["timeout"], staging.IO_TIMEOUT)
            self.assertEqual(call.kwargs["context"].verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(call.kwargs["context"].check_hostname)
        self.assertIs(factory.call_args_list[0].kwargs["context"],
                      factory.call_args_list[1].kwargs["context"])
        self.assertEqual(origin.request.call_args.args, ("GET", "/Ultimaker/CuraEngine/releases/download/5.0.0/engine.tar"))
        self.assertEqual(asset.request.call_args.args, ("GET", self.ASSET_LOCATION.split(".com", 1)[1]))
        for conn in [origin, asset]:
            self.assertEqual(set(conn.request.call_args.kwargs["headers"]),
                             {"Accept-Encoding", "User-Agent", "Connection"})
            conn.close.assert_called_once()
        self.assertNotIn("signature", (work / "READY.json").read_text())

    def test_github_direct_200_remains_supported(self):
        self.assert_payload(self.network(Response(tar_bytes()),
                           art=replace(artifact(tar_bytes()), url=self.RELEASE_URL)))

    def test_github_chunked_asset_payload(self):
        self.assert_payload(self.github_network(second=Response(
            tar_bytes(), headers=[("Transfer-Encoding", "chunked")])))

    def test_github_asset_hop_reaches_all_existing_archive_adapters(self):
        raw = tar_bytes()
        for form, data in [("tar", raw), ("tar.gz", gzip.compress(raw)),
                           ("tar.xz", lzma.compress(raw)), ("zip", zip_bytes()),
                           ("deb", deb_bytes(lzma.compress(raw)))]:
            with self.subTest(form=form):
                art = replace(artifact(data, form), url=self.RELEASE_URL)
                work = self.github_network(second=Response(data), art=art)
                self.assert_payload(work)
                shutil.rmtree(work)

    def test_github_asset_rejects_unsafe_location_before_second_connection(self):
        good = self.ASSET_LOCATION
        invalid = ["", "/relative", "//release-assets.githubusercontent.com/path",
                   good.replace("https:", "http:", 1),
                   good.replace("release-assets.githubusercontent.com", "localhost"),
                   good.replace("release-assets.githubusercontent.com", "127.0.0.1"),
                   good.replace("release-assets.githubusercontent.com", "[::1]"),
                   good.replace("release-assets.githubusercontent.com", "release-assets.githubusercontent.com.evil.invalid"),
                   good.replace("release-assets.githubusercontent.com", "evil.invalid@release-assets.githubusercontent.com"),
                   good.replace(".com/", ".com:443/", 1),
                   good.replace(".com/", ".com:8443/", 1),
                   good.replace("/123456/", "/../"),
                   good.replace("/123456/", "/%31%32%33/"),
                   good.replace("/123456/", "/0123456/"),
                   good.replace("github-production-release-asset", "other"),
                   good.replace("?signature", "#signature"),
                   good.split("?", 1)[0], good + "#fragment", good + "\r\nInjected: yes",
                   good + " ", good + "\\", good + "\u00e4",
                   good + "x" * 16384]
        for value in invalid:
            with self.subTest(value=value[:70]), self.assertRaisesRegex(staging.StagingError, "^redirect_denied$"):
                self.github_network(first=Response(b"", status=302, headers=[("Location", value)]))
            factory, origin, asset = self.last_hops
            self.assertEqual(factory.call_count, 1)
            origin.close.assert_called_once()
            asset.request.assert_not_called()
            self.assert_clean()

    def test_github_redirect_location_must_be_unique(self):
        for headers in [[], [("Location", self.ASSET_LOCATION), ("location", self.ASSET_LOCATION)]]:
            with self.subTest(headers=len(headers)), self.assertRaisesRegex(staging.StagingError, "^redirect_denied$"):
                self.github_network(first=Response(b"", status=302, headers=headers))
            self.assertEqual(self.last_hops[0].call_count, 1)
            self.assert_clean()

    def test_only_github_302_is_supported(self):
        for status in [301, 303, 307, 308]:
            with self.subTest(status=status), self.assertRaisesRegex(staging.StagingError, "^redirect_denied$"):
                self.github_network(first=Response(b"", status=status, headers=[("Location", self.ASSET_LOCATION)]))
            self.assertEqual(self.last_hops[0].call_count, 1)
            self.assert_clean()
        with self.assertRaisesRegex(staging.StagingError, "^redirect_denied$"):
            self.github_network(art=artifact(tar_bytes()))
        self.assertEqual(self.last_hops[0].call_count, 1)
        self.assert_clean()

    def test_github_second_redirect_is_never_followed(self):
        for status in [301, 302, 303, 307, 308]:
            with self.subTest(status=status), self.assertRaisesRegex(staging.StagingError, "^redirect_denied$"):
                self.github_network(second=Response(b"", status=status, headers=[("Location", self.ASSET_LOCATION)]))
            factory, origin, asset = self.last_hops
            self.assertEqual(factory.call_count, 2)
            origin.close.assert_called_once()
            asset.close.assert_called_once()
            self.assert_clean()

    def test_github_asset_still_enforces_headers_size_and_digest(self):
        raw = tar_bytes()
        responses = [Response(raw, status=403), Response(raw, headers=[("Content-Encoding", "gzip")]),
                     Response(raw, headers=[("Content-Length", "1")]),
                     Response(raw, headers=[("Content-Length", str(len(raw))), ("Content-Length", str(len(raw)))]),
                     Response(raw, headers=[("Content-Length", str(len(raw))), ("Transfer-Encoding", "chunked")]),
                     Response(raw[:-1], headers=[]), Response(raw + b"x", headers=[]),
                     Response(bytes(len(raw)), headers=[])]
        for response in responses:
            with self.subTest(status=response.status, size=len(response.getvalue())), self.assertRaises(staging.StagingError):
                self.github_network(second=response)
            self.last_hops[2].close.assert_called_once()
            self.assert_clean()

    def test_github_cancel_after_origin_response_prevents_asset_connection(self):
        cancelled = False
        def stop():
            return cancelled
        response = Response(b"", status=302, headers=[("Location", self.ASSET_LOCATION)])
        original = response.getheaders
        def cancel_after_headers():
            nonlocal cancelled
            cancelled = True
            return original()
        response.getheaders = cancel_after_headers
        with self.assertRaisesRegex(staging.StagingError, "^cancelled$"):
            self.github_network(first=response, cancelled=stop)
        self.assertEqual(self.last_hops[0].call_count, 1)
        self.last_hops[1].close.assert_called_once()
        self.assert_clean()

    def test_github_asset_errors_never_include_transient_url(self):
        origin, asset = Mock(), Mock()
        origin.getresponse.return_value = Response(b"", status=302, headers=[("Location", self.ASSET_LOCATION)])
        asset.request.side_effect = OSError(self.ASSET_LOCATION)
        with patch.object(staging.http.client, "HTTPSConnection", side_effect=[origin, asset]):
            with self.assertRaisesRegex(staging.StagingError, "^download_failed$") as error:
                staging.prepare_release(release(replace(artifact(tar_bytes()), url=self.RELEASE_URL)), self.parent)
        self.assertNotIn("signature", str(error.exception))
        self.assertIsNone(error.exception.__cause__)
        self.assertTrue(error.exception.__suppress_context__)
        origin.close.assert_called_once()
        asset.close.assert_called_once()
        self.assert_clean()

    def test_github_hop_does_not_reset_operation_deadline(self):
        clock = 0
        response = Response(b"", status=302, headers=[("Location", self.ASSET_LOCATION)])
        original = response.getheaders
        def advance_clock():
            nonlocal clock
            clock = 11
            return original()
        response.getheaders = advance_clock
        with patch.object(staging, "OPERATION_SECONDS", 10), patch.object(staging.time, "monotonic", side_effect=lambda: clock):
            with self.assertRaisesRegex(staging.StagingError, "^deadline_exceeded$"):
                self.github_network(first=response)
        self.assertEqual(self.last_hops[0].call_count, 1)
        self.last_hops[1].close.assert_called_once()
        self.assert_clean()

    def test_download_rejects_redirect_status_encoding_and_headers(self):
        raw = tar_bytes()
        cases = [Response(raw, status=302), Response(raw, status=404),
                 Response(raw, headers=[("Content-Encoding", "gzip")]),
                 Response(raw, headers=[("Content-Length", "1")]),
                 Response(raw, headers=[("Content-Length", str(len(raw))), ("Content-Length", str(len(raw)))]),
                 Response(raw, headers=[("Content-Length", str(len(raw))), ("Transfer-Encoding", "chunked")]),
                 Response(raw, headers=[("Transfer-Encoding", "other")])]
        for response in cases:
            with self.subTest(status=response.status, headers=response.headers), self.assertRaises(staging.StagingError):
                self.network(response)
            self.assert_clean()

    def test_download_truncation_extra_bytes_and_digest(self):
        raw = tar_bytes()
        for data in [raw[:-1], raw + b"x", bytes(len(raw))]:
            with self.subTest(size=len(data)), self.assertRaises(staging.StagingError):
                self.network(Response(data, headers=[]))
            self.assert_clean()

    def test_network_error_is_sanitized(self):
        with patch.object(staging.http.client, "HTTPSConnection") as connection:
            connection.return_value.request.side_effect = OSError("private response must not escape")
            with self.assertRaisesRegex(staging.StagingError, "^download_failed$"):
                staging.prepare_release(release(artifact(tar_bytes())), self.parent)
            connection.return_value.close.assert_called_once()
        self.assert_clean()


    def test_gnu_long_name_selected_file(self):
        name = "usr/share/" + "long-directory/" * 12 + "engine"
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w", format=tarfile.GNU_FORMAT) as archive:
            for index, (source, entry) in enumerate(BASE.items()):
                info = tarfile.TarInfo(name if index == 0 else source)
                info.size = len(entry[0])
                archive.addfile(info, io.BytesIO(entry[0]))
        data = output.getvalue()
        art = artifact(data)
        art = replace(art, files=(replace(art.files[0], archive_path=name), *art.files[1:]))
        self.assert_payload(self.run_local(data, art=art))

    def test_gnu_long_name_bounds_and_dangling(self):
        def extension(data):
            info = tarfile.TarInfo("././@LongLink")
            info.type = tarfile.GNUTYPE_LONGNAME
            info.size = len(data)
            return info.tobuf(tarfile.GNU_FORMAT) + data + bytes((-len(data)) % 512)
        raw = tar_bytes()
        for data in [extension(b"../escape\x00") + raw,
                     extension(b"/escape\x00") + raw,
                     extension(b"x" * 1025 + b"\x00") + raw,
                     extension(b"unterminated") + raw,
                     extension(b"bad\x00inside\x00") + raw,
                     extension(b"name\x00") + bytes(1024),
                     extension(b"name\x00") + extension(b"name\x00") + raw]:
            with self.subTest(size=len(data)), self.assertRaises(staging.StagingError):
                self.run_local(data)
            self.assert_clean()

    def test_xz_memory_budget(self):
        data = lzma.compress(tar_bytes())
        with patch.object(staging, "LZMA_MEMORY", 1024), self.assertRaises(staging.StagingError):
            self.run_local(data, "tar.xz")
        self.assert_clean()

    def test_pax_extensions_remain_unsupported(self):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w", format=tarfile.PAX_FORMAT) as archive:
            info = tarfile.TarInfo("file")
            info.mtime = 0.5
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))
        with self.assertRaises(staging.StagingError):
            self.run_local(output.getvalue())
        self.assert_clean()

    def test_shipped_catalog_remains_pending(self):
        parsed = catalog.load_catalog()
        self.assertFalse(parsed.releases)
        self.assertEqual(set(parsed.pending), set(catalog.ENTRYPOINTS))


if __name__ == "__main__":
    unittest.main()

