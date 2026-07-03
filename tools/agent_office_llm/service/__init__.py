"""Office Service — the persistent core behind the Virtual Agent Office.

Implements the vision's control-plane primitives (VISION_AND_PRODUCT.md §6): tasks,
an append-only event bus, a connector gateway with per-agent/per-tool autonomy and an
audit log, and a dispatch/approval service. Pure stdlib, in-memory, fully unit-tested —
the 3D client and connectors bind to it; nothing here needs the game running.
"""

from .models import (
    Agent, Task, Approval, Event, AuditEntry,
    Autonomy, TaskStatus, ApprovalStatus,
)
from .event_bus import EventBus
from .connectors import ConnectorGateway, Connector, ConnectorResult, PolicyError
from .office_service import OfficeService

__all__ = [
    "Agent", "Task", "Approval", "Event", "AuditEntry",
    "Autonomy", "TaskStatus", "ApprovalStatus",
    "EventBus", "ConnectorGateway", "Connector", "ConnectorResult", "PolicyError",
    "OfficeService",
]
