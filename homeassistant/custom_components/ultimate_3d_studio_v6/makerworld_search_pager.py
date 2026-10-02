"""Progressive, cached MakerWorld pagination for one or more search filters."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable

SearchItem = dict[str, Any]
SearchLoader = Callable[[str, int, int], Awaitable[tuple[list[SearchItem], str, bool]]]


@dataclass
class _TermState:
    items: dict[str, SearchItem] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    next_offset: int = 0
    exhausted: bool = False
    sources: list[str] = field(default_factory=list)


@dataclass
class _QueryState:
    terms: tuple[str, ...]
    term_states: dict[str, _TermState]


@dataclass(frozen=True)
class SearchPage:
    items: list[SearchItem]
    has_more: bool
    source_endpoint: str
    known_count: int
    total_count: int | None


class MakerWorldSearchPager:
    """Loads real upstream pages and intersects accumulated filter results."""

    def __init__(
        self,
        *,
        upstream_page_size: int = 60,
        max_rounds_per_request: int = 20,
        max_cached_queries: int = 16,
    ) -> None:
        self._upstream_page_size = max(1, min(int(upstream_page_size), 60))
        self._max_rounds_per_request = max(1, int(max_rounds_per_request))
        self._max_cached_queries = max(1, int(max_cached_queries))
        self._queries: OrderedDict[tuple[str, ...], _QueryState] = OrderedDict()

    @staticmethod
    def _normalize_terms(values: Iterable[str]) -> tuple[str, ...]:
        result: list[str] = []
        seen: set[str] = set()
        for raw in values:
            value = " ".join(str(raw or "").split())[:120]
            folded = value.casefold()
            if not value or folded in seen:
                continue
            seen.add(folded)
            result.append(value)
            if len(result) >= 12:
                break
        return tuple(result)

    def clear(self, terms: Iterable[str] | None = None) -> None:
        if terms is None:
            self._queries.clear()
            return
        self._queries.pop(self._normalize_terms(terms), None)

    def _state(self, terms: tuple[str, ...]) -> _QueryState:
        existing = self._queries.pop(terms, None)
        if existing is not None:
            self._queries[terms] = existing
            return existing
        state = _QueryState(
            terms=terms,
            term_states={term: _TermState() for term in terms},
        )
        self._queries[terms] = state
        while len(self._queries) > self._max_cached_queries:
            self._queries.popitem(last=False)
        return state

    @staticmethod
    def _combined(state: _QueryState) -> list[SearchItem]:
        if not state.terms:
            return []
        primary = state.term_states[state.terms[0]]
        if len(state.terms) == 1:
            return [primary.items[item_id] for item_id in primary.order if item_id in primary.items]
        remaining = [set(state.term_states[term].items) for term in state.terms[1:]]
        return [
            primary.items[item_id]
            for item_id in primary.order
            if item_id in primary.items and all(item_id in ids for ids in remaining)
        ]

    async def page(
        self,
        terms: Iterable[str],
        offset: int,
        limit: int,
        loader: SearchLoader,
    ) -> SearchPage:
        normalized = self._normalize_terms(terms)
        if not normalized:
            return SearchPage([], False, "", 0, 0)
        safe_offset = max(0, int(offset))
        safe_limit = max(1, int(limit))
        target = safe_offset + safe_limit
        state = self._state(normalized)

        rounds = 0
        while len(self._combined(state)) < target and rounds < self._max_rounds_per_request:
            pending = [term for term in normalized if not state.term_states[term].exhausted]
            if not pending:
                break
            for term in pending:
                term_state = state.term_states[term]
                items, source, has_more = await loader(
                    term,
                    term_state.next_offset,
                    self._upstream_page_size,
                )
                if source and source not in term_state.sources:
                    term_state.sources.append(source)
                for item in items:
                    item_id = str(item.get("id", "")).strip()
                    if not item_id or item_id in term_state.items:
                        continue
                    term_state.items[item_id] = item
                    term_state.order.append(item_id)
                term_state.next_offset += self._upstream_page_size
                term_state.exhausted = not has_more or not items
            rounds += 1

        combined = self._combined(state)
        exhausted = all(state.term_states[term].exhausted for term in normalized)
        sources: list[str] = []
        for term in normalized:
            for source in state.term_states[term].sources:
                if source not in sources:
                    sources.append(source)
        return SearchPage(
            items=combined[safe_offset:target],
            has_more=len(combined) > target or not exhausted,
            source_endpoint=",".join(sources),
            known_count=len(combined),
            total_count=len(combined) if exhausted else None,
        )