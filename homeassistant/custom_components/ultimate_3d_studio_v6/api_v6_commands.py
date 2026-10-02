"""Compatibility imports for the canonical V6 HTTP API.

The complete API, including printer commands, is implemented in ``api.py``.
This module remains import-compatible for older development scripts without
maintaining a second route implementation.
"""

from .api import (
    CapabilitiesView,
    CommandView,
    DiscoveryView,
    HealthView,
    JobsView,
    PrintersView,
    async_register_http_views,
)

__all__ = [
    "CapabilitiesView",
    "CommandView",
    "DiscoveryView",
    "HealthView",
    "JobsView",
    "PrintersView",
    "async_register_http_views",
]