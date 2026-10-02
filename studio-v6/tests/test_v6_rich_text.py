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


def test_safe_html_keeps_format_and_inline_image_position() -> None:
    result = module.safe_rich_html('<h2>Title</h2><p><strong>Before</strong></p><img src="https://example.com/a.png?a=1&amp;b=2"><table><tr><td>Cell</td></tr></table>')
    assert '<h2>Title</h2>' in result
    assert '<strong>Before</strong>' in result
    assert '<table><tr><td>Cell</td></tr></table>' in result
    assert result.index('<img') > result.index('Before')
    assert 'a=1&amp;b=2' in result


def test_safe_html_removes_active_content_attributes_and_unsafe_urls() -> None:
    result = module.safe_rich_html('<p onclick="evil()">Visible</p><script>evil()</script><iframe>Hidden</iframe><img src="javascript:evil()"><img src=""><a href="data:text/html,bad">Text</a>')
    assert 'Visible' in result and 'Text' in result
    assert 'evil' not in result and 'Hidden' not in result
    assert '<img' not in result and 'onclick' not in result and 'data:' not in result


def test_safe_html_plain_paragraphs_and_encoded_markup_stay_passive() -> None:
    assert module.safe_rich_html('First\n\nSecond') == '<p>First</p><p>Second</p>'
    result = module.safe_rich_html('&lt;img src=x onerror=evil()&gt;')
    assert '<img' not in result
