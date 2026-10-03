"""Resolve supported connected hardware independently of job/display profiles.

Manufacturer identity definitions, pinned for review:
https://github.com/bambulab/BambuStudio/tree/da8b44ee34dd349f2ae0df3f1cbae366df482354/resources/printers
N2S.json: Bambu Lab A1, sn_prefix 039.
O1S.json: Bambu Lab H2S, sn_prefix 093.
Unknown serial families and conflicting telemetry stay fail-closed.
"""
from __future__ import annotations

import re

from .printer_model_contract import canonical_model

_SERIAL_MODELS = {"039": "A1", "093": "H2S"}
_REPORTED_MODEL_IDS = {"N2S": "A1", "O1S": "H2S"}


def resolve_connected_printer_model(reported_model: object, serial: object) -> str | None:
    """Use the connected provider serial, never a user name or slice payload."""
    serial_text = str(serial or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{12,32}", serial_text):
        return None
    serial_model = _SERIAL_MODELS.get(serial_text[:3])
    if serial_model is None:
        return None
    reported = str(reported_model or "").strip()
    if not reported:
        return serial_model
    normalized = canonical_model(reported) or _REPORTED_MODEL_IDS.get(reported.upper())
    # A nonempty unknown model is not treated as missing telemetry.
    return serial_model if normalized == serial_model else None
