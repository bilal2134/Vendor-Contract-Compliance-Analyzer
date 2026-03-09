from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from typing import Any


class InMemoryRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}
        self.packages: dict[str, dict[str, Any]] = {}
        self.playbooks: dict[str, dict[str, Any]] = {}
        self.reports: dict[str, dict[str, Any]] = {}
        self.notes: dict[str, list[dict[str, Any]]] = {}

    def put(self, bucket: str, key: str, value: dict[str, Any]) -> dict[str, Any]:
        getattr(self, bucket)[key] = deepcopy(value)
        return deepcopy(value)

    def get(self, bucket: str, key: str) -> dict[str, Any] | None:
        value = getattr(self, bucket).get(key)
        return deepcopy(value) if value is not None else None

    def values(self, bucket: str) -> Iterable[dict[str, Any]]:
        return [deepcopy(item) for item in getattr(self, bucket).values()]


repository = InMemoryRepository()
