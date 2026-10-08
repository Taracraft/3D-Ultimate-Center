"""Shared Studio primitives."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
