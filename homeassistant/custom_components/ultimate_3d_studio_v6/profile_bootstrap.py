"""Profile runtime bootstrap for V6 setup."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from .profile_runtime_v2 import install_profile_runtime_v2


def bootstrap_profiles(hass: HomeAssistant) -> None:
    install_profile_runtime_v2(hass)
