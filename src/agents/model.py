"""Model client interface. Foundry (later) plugs in by implementing `ModelClient`."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Protocol

from contracts.agents import Role


class ModelClient(Protocol):
    model_id: str

    async def generate(self, *, role: Role, system: str, input_json: str) -> str:
        """Return the model's raw text (expected: one JSON object). May raise; the
        coordinator owns timeouts."""
        ...


@dataclass(frozen=True)
class Delay:
    seconds: float
    item: "str | Exception | Delay"


class ScriptExhausted(RuntimeError):
    pass


class FakeModelClient:
    """Scripted client for tests and the smoke demo. Per-role FIFO scripts; each item is
    a str (returned), an Exception (raised) or Delay(seconds, item)."""

    def __init__(self, model_id: str = "fake", scripts: dict[Role, list] | None = None):
        self.model_id = model_id
        self.calls: list[tuple[Role, str, str]] = []
        self._scripts: dict[Role, deque] = defaultdict(deque)
        for role, items in (scripts or {}).items():
            self.script(role, *items)

    def script(self, role: Role, *items: "str | Exception | Delay") -> None:
        self._scripts[role].extend(items)

    async def generate(self, *, role: Role, system: str, input_json: str) -> str:
        self.calls.append((role, system, input_json))
        if not self._scripts[role]:
            raise ScriptExhausted(f"no scripted response left for role {role.value}")
        item = self._scripts[role].popleft()
        while isinstance(item, Delay):
            await asyncio.sleep(item.seconds)
            item = item.item
        if isinstance(item, Exception):
            raise item
        return item
