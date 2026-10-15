"""Version-neutral, isolated writable gallery paths for the Studio integration.

The historic printer-control archive is available only through an independent
read-only gallery catalog. Uploads and management must never write there.
"""
from __future__ import annotations

from pathlib import Path

from .const import DOMAIN


def _studio_data_path(hass, category: str) -> Path:
    """Resolve a Studio-owned writable path and reject linked/escaped directories."""
    if category not in {"gallery", "upload_sessions"}:
        raise ValueError("invalid_studio_storage_category")
    studio_root = Path(hass.config.path(DOMAIN))
    destination = Path(hass.config.path(DOMAIN, category))
    if studio_root.is_symlink() or destination.is_symlink():
        raise ValueError("linked_studio_storage_not_allowed")
    canonical_root = studio_root.resolve(strict=False)
    canonical_destination = destination.resolve(strict=False)
    if canonical_destination != canonical_root and not canonical_destination.is_relative_to(
        canonical_root
    ):
        raise ValueError("studio_storage_path_outside_integration")
    return destination


def studio_gallery_root(hass) -> Path:
    """Only the Studio-managed gallery may receive uploads, copies and deletions."""
    return _studio_data_path(hass, "gallery")


def studio_upload_session_root(hass) -> Path:
    """Store resumable model uploads independently of legacy galleries."""
    return _studio_data_path(hass, "upload_sessions")


def is_same_studio_storage_path(expected: Path, candidate: Path) -> bool:
    """Compare storage roots without accepting a linked cached path."""
    expected_path = Path(expected)
    candidate_path = Path(candidate)
    if expected_path.is_symlink() or candidate_path.is_symlink():
        raise ValueError("linked_studio_storage_not_allowed")
    return candidate_path.resolve(strict=False) == expected_path.resolve(strict=False)


def validated_studio_upload_session_path(
    hass,
    upload_id: str,
    candidate: str | Path,
) -> Path:
    """Return a part path only when it is the current Studio session path."""
    root = studio_upload_session_root(hass)
    path = Path(candidate)
    expected = root / f"{upload_id}.part"
    if not is_same_studio_storage_path(expected, path):
        raise ValueError("upload_session_path_outside_studio")
    return path
