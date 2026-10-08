"""Safe conversion of remote rich HTML into readable plain text."""
from __future__ import annotations

from html import unescape, escape
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit

_BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "div",
    "dl",
    "dt",
    "dd",
    "figcaption",
    "figure",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}
_DROP_TAGS = {"script", "style", "template", "iframe", "object", "svg", "math"}
_UNICODE_SPACES = re.compile(r"[\u00a0\u2007\u202f]")


class _RichTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._drop_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        normalized = tag.casefold()
        if normalized in _DROP_TAGS:
            self._drop_depth += 1
            return
        if self._drop_depth:
            return
        if normalized == "li":
            self.parts.append("\n• ")
        elif normalized in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        if tag.casefold() in _DROP_TAGS and self._drop_depth:
            self._drop_depth -= 1

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if normalized in _DROP_TAGS:
            if self._drop_depth:
                self._drop_depth -= 1
            return
        if self._drop_depth:
            return
        if normalized in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._drop_depth:
            self.parts.append(data)


def readable_rich_text(value: object, limit: int = 30_000) -> str:
    """Return readable text without exposing remote HTML source or active markup."""
    raw = str(value or "")
    if not raw:
        return ""
    parser = _RichTextParser()
    try:
        parser.feed(unescape(raw))
        parser.close()
        text = "".join(parser.parts)
    except Exception:
        text = re.sub(r"<[^>]*>", " ", unescape(raw))
    text = _UNICODE_SPACES.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[: max(1, int(limit))]


_HTML_TAGS = {"p", "br", "strong", "b", "em", "i", "u", "s", "ul", "ol", "li",
              "h1", "h2", "h3", "h4", "h5", "h6", "img", "a", "blockquote",
              "pre", "code", "table", "thead", "tbody", "tfoot", "tr", "th", "td", "hr"}
_VOID_TAGS = {"br", "img", "hr"}


def _safe_remote_url(value: str) -> str:
    value = value.strip()
    if value.startswith("//"):
        value = "https:" + value
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme.lower() in {"http", "https"} and parsed.hostname else ""
    except ValueError:
        return ""


class _SafeHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.dropped: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _DROP_TAGS:
            self.dropped.append(tag)
            return
        if self.dropped or tag not in _HTML_TAGS:
            return
        values = dict(attrs)
        attributes = ""
        if tag in {"img", "a"}:
            key = "src" if tag == "img" else "href"
            url = _safe_remote_url(values.get(key) or "")
            if tag == "img" and not url:
                return
            if url:
                attributes = f' {key}="{escape(url, quote=True)}"'
            if tag == "img":
                attributes += f' alt="{escape(values.get("alt") or "", quote=True)}" loading="lazy"'
            else:
                attributes += ' target="_blank" rel="noopener noreferrer"'
        self.parts.append(f"<{tag}{attributes}>")

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.dropped:
            if tag == self.dropped[-1]:
                self.dropped.pop()
            return
        if tag in _HTML_TAGS and tag not in _VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self.dropped:
            self.parts.append(escape(data))


def safe_rich_html(value: object, limit: int = 30_000) -> str:
    """Preserve remote document structure using a passive HTML allowlist."""
    raw = str(value or "")[:max(1, int(limit))]
    if not re.search(r"<[a-z][\s\S]*>", raw, re.I):
        return "<p>" + escape(raw).replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>" if raw else ""
    parser = _SafeHtmlParser()
    parser.feed(raw)
    parser.close()
    return "".join(parser.parts)
