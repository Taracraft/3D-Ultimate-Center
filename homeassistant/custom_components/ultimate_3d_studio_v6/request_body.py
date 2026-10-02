"""Bounded streaming helpers for authenticated V6 binary uploads."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class _ChunkStream(Protocol):
    def iter_chunked(self, size: int): ...


class _RequestLike(Protocol):
    content_length: int | None
    content: _ChunkStream


@dataclass(frozen=True, slots=True)
class RequestBodyTooLarge(Exception):
    """Raised when an upload exceeds the endpoint-specific byte limit."""

    maximum_bytes: int

    def __str__(self) -> str:
        return f"request body exceeds {self.maximum_bytes} bytes"


async def async_read_limited_body(
    request: _RequestLike,
    maximum_bytes: int,
    *,
    chunk_size: int = 1024 * 1024,
) -> bytes:
    """Read a request incrementally while enforcing an explicit byte limit.

    Home Assistant's aiohttp request.read() applies the application's global
    client_max_size before endpoint-specific V6 limits. Reading the content
    stream directly keeps V6's own 160/300 MB contracts authoritative while
    still failing closed as soon as the configured maximum is exceeded.
    """
    if maximum_bytes <= 0:
        raise ValueError("maximum_bytes must be positive")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    content_length = request.content_length
    if content_length is not None and content_length > maximum_bytes:
        raise RequestBodyTooLarge(maximum_bytes)

    payload = bytearray()
    async for chunk in request.content.iter_chunked(chunk_size):
        if not chunk:
            continue
        if len(payload) + len(chunk) > maximum_bytes:
            raise RequestBodyTooLarge(maximum_bytes)
        payload.extend(chunk)
    return bytes(payload)