"""Pure audit filtering and recursive secret redaction for Ultimate 3D Studio V6."""
from __future__ import annotations

import re
from typing import Any, Mapping

MAX_COLLECTION_ITEMS = 250
MAX_STRING_LENGTH = 4000
MAX_NESTING_DEPTH = 12

_SENSITIVE_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "passwd",
    "authorization",
    "cookie",
    "apikey",
    "accesscode",
    "credential",
    "privatekey",
    "contentbase64",
)

_ALLOWED_ATTRIBUTE_KEYS = frozenset({
    "friendly_name",
    "icon",
    "printer_name",
    "printer_id",
    "provider",
    "updated_at",
    "connection_state",
    "state_class",
    "device_class",
    "unit_of_measurement",
    "error_code",
    "error_message",
    "issue_count",
    "issues",
    "resume_available",
    "supported_features",
    "hms",
    "host",
    "restored",
    "component_version",
    "provider_count",
    "providers",
    "printers",
    "job_current_count",
    "job_queue_count",
    "job_history_count",
    "latest_history_job",
    "snapshot_error",
    "discovery_candidates",
    "discovery_error",
    "started_at",
    "isolated_test_domain",
    "printer_state",
    "primary_issue_code",
    "primary_issue_message",
    "help_url",
    "qr_url",
    "port",
    "connected",
    "last_error",
    "transport",
    "read_only",
    "generated_at",
    "last_log_file",
    "worker_journal",
    "refresh_journal",
    "recent_jobs",
})

_BEARER_RE = re.compile(r"(?i)\b(bearer|basic)\s+[a-z0-9._~+/=-]+")
_URL_USERINFO_RE = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^\s/?#@]+@")
_SECRET_LABEL = r"access[_ -]?token|refresh[_ -]?token|bearer[_ -]?token|token|secret|password|passwd|authorization|cookie|api[_ -]?key|access[_ -]?code|credential|private[_ -]?key"
_QUOTED_SECRET_RE = re.compile(
    r"(?i)([\"'](?:" + _SECRET_LABEL + r")[\"']\s*:\s*)"
    r"(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^\s,;}]+)"
)
_QUERY_SECRET_RE = re.compile(
    r"(?i)([?&][^\s&#=]*(?:token|secret|passw(?:or)?d|auth|api[_-]?key|access[_-]?code|signature|sig)[^\s&#=]*=)([^\s&#]*)"
)
_INLINE_SECRET_RE = re.compile(
    r"(?i)\b(" + _SECRET_LABEL + r")\s*[:=]\s*"
    r"(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^\s,;&#]+)"
)


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def is_sensitive_audit_key(key: str) -> bool:
    normalized = _normalized_key(str(key))
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def redact_audit_text(value: str) -> str:
    text = _URL_USERINFO_RE.sub(lambda match: f"{match.group(1)}***@", str(value))
    text = _BEARER_RE.sub(lambda match: f"{match.group(1).title()} ***", text)
    text = _QUOTED_SECRET_RE.sub(lambda match: f'{match.group(1)}"***"', text)
    text = _QUERY_SECRET_RE.sub(lambda match: f"{match.group(1)}***", text)
    text = _INLINE_SECRET_RE.sub(lambda match: f"{match.group(1)}=***", text)
    if len(text) > MAX_STRING_LENGTH:
        return text[:MAX_STRING_LENGTH] + "…"
    return text


def sanitize_audit_value(value: Any, key: str | None = None, *, _depth: int = 0) -> Any:
    if key is not None and is_sensitive_audit_key(key):
        return "***"
    if _depth >= MAX_NESTING_DEPTH:
        return "<maximum nesting reached>"
    if isinstance(value, Mapping):
        return {
            str(item_key): sanitize_audit_value(item_value, str(item_key), _depth=_depth + 1)
            for item_key, item_value in list(value.items())[:MAX_COLLECTION_ITEMS]
        }
    if isinstance(value, (list, tuple)):
        return [
            sanitize_audit_value(item, _depth=_depth + 1)
            for item in value[:MAX_COLLECTION_ITEMS]
        ]
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if isinstance(value, str):
        return redact_audit_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_audit_text(str(value))


def safe_audit_attributes(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    source = attributes or {}
    return {
        str(key): sanitize_audit_value(value, str(key))
        for key, value in source.items()
        if str(key) in _ALLOWED_ATTRIBUTE_KEYS
    }
