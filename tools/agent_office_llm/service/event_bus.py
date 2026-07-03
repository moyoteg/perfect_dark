"""Append-only world event bus (VISION_AND_PRODUCT.md §6.6).

Every meaningful thing — approaches, hand-offs, Slack inbound, alerts, task
transitions — is an Event. The log is append-only so any office session is
replayable. Subscribers filter by type prefix (e.g. "task." or "slack.").
"""
from __future__ import annotations

from typing import Callable

from .models import Event

Subscriber = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._log: list[Event] = []
        self._subs: list[tuple[str, Subscriber]] = []

    def publish(self, event: Event) -> Event:
        self._log.append(event)
        for prefix, fn in list(self._subs):
            if event.type == prefix or event.type.startswith(prefix):
                fn(event)
        return event

    def subscribe(self, type_prefix: str, fn: Subscriber) -> None:
        """Call fn for every event whose type equals or starts with type_prefix.
        Use "" to receive everything."""
        self._subs.append((type_prefix, fn))

    def history(self, type_prefix: str = "") -> list[Event]:
        if not type_prefix:
            return list(self._log)
        return [e for e in self._log if e.type == type_prefix or e.type.startswith(type_prefix)]

    def __len__(self) -> int:
        return len(self._log)
