"""Safe conversion of remote rich HTML into readable plain text."""
from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import re

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