from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio"
    / "request_body.py"
)
MODULE_NAME = "studio_request_body"
SPEC = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[MODULE_NAME] = MODULE
SPEC.loader.exec_module(MODULE)

RequestBodyTooLarge = MODULE.RequestBodyTooLarge
async_read_limited_body = MODULE.async_read_limited_body


class FakeContent:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks
        self.requested_chunk_size: int | None = None

    async def iter_chunked(self, size: int):
        self.requested_chunk_size = size
        for chunk in self._chunks:
            yield chunk


class FakeRequest:
    def __init__(self, chunks: list[bytes], content_length: int | None = None) -> None:
        self.content_length = content_length
        self.content = FakeContent(chunks)


class RequestBodyTests(unittest.IsolatedAsyncioTestCase):
    async def test_streams_body_without_request_read(self) -> None:
        request = FakeRequest([b"abc", b"def"], content_length=6)
        payload = await async_read_limited_body(request, 10, chunk_size=4)
        self.assertEqual(payload, b"abcdef")
        self.assertEqual(request.content.requested_chunk_size, 4)

    async def test_rejects_declared_oversize_before_streaming(self) -> None:
        request = FakeRequest([b"ignored"], content_length=11)
        with self.assertRaises(RequestBodyTooLarge):
            await async_read_limited_body(request, 10)
        self.assertIsNone(request.content.requested_chunk_size)

    async def test_rejects_chunked_upload_when_accumulated_size_exceeds_limit(self) -> None:
        request = FakeRequest([b"12345", b"67890", b"x"], content_length=None)
        with self.assertRaises(RequestBodyTooLarge):
            await async_read_limited_body(request, 10, chunk_size=5)

    async def test_accepts_body_at_exact_limit(self) -> None:
        request = FakeRequest([b"12345", b"67890"], content_length=None)
        payload = await async_read_limited_body(request, 10)
        self.assertEqual(payload, b"1234567890")


if __name__ == "__main__":
    unittest.main()
