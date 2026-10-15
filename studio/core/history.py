"""Deterministic in-memory undo and redo history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class History(Generic[T]):
    current: T
    undo_stack: list[T]
    redo_stack: list[T]
    limit: int = 100

    @classmethod
    def create(cls, initial: T, limit: int = 100) -> "History[T]":
        if limit < 1:
            raise ValueError("history limit must be at least 1")
        return cls(initial, [], [], limit)

    def push(self, value: T) -> T:
        self.undo_stack.append(self.current)
        if len(self.undo_stack) > self.limit:
            del self.undo_stack[0]
        self.current = value
        self.redo_stack.clear()
        return self.current

    def undo(self) -> T:
        if not self.undo_stack:
            return self.current
        self.redo_stack.append(self.current)
        self.current = self.undo_stack.pop()
        return self.current

    def redo(self) -> T:
        if not self.redo_stack:
            return self.current
        self.undo_stack.append(self.current)
        self.current = self.redo_stack.pop()
        return self.current
