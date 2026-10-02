"""Regression tests for safe MakerWorld rich-text conversion."""
from __future__ import annotations

import importlib.util
from pathlib import Path


PATH = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio_v6"
    / "rich_text.py"
)
SPEC = importlib.util.spec_from_file_location("v6_rich_text", PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_html_is_converted_to_readable_text() -> None:
    result = module.readable_rich_text(
        "<h2>Überschrift</h2><p>Hello&nbsp;<strong>world</strong></p>"
    )
    assert "<h2>" not in result
    assert "Überschrift" in result
    assert "Hello world" in result
    assert "&nbsp;" not in result


def test_active_content_is_removed_completely() -> None:
    result = module.readable_rich_text(
        "<p>Sichtbar</p><script>alert('x')</script><style>.x{color:red}</style>"
    )
    assert result == "Sichtbar"
    assert "alert" not in result
    assert "color" not in result


def test_lists_keep_readable_structure() -> None:
    result = module.readable_rich_text("<ul><li>Erster Punkt</li><li>Zweiter Punkt</li></ul>")
    assert "• Erster Punkt" in result
    assert "• Zweiter Punkt" in result
    assert "\n" in result


def test_text_is_limited_after_normalization() -> None:
    result = module.readable_rich_text("<p>abcdefghijk</p>", 5)
    assert result == "abcde"
