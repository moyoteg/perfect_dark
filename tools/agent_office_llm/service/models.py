"""Data model for the Office Service (VISION_AND_PRODUCT.md §6.5)."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _now() -> float:
    return time.time()


class Autonomy(str, Enum):
    """Per-agent, per-tool safety dial (VISION §4)."""
    SUGGEST = "suggest"            # propose only; nothing happens without the human
    ASK_APPROVAL = "ask-approval"  # stage the action; needs a human-present approval
    ACT = "act"                    # may execute autonomously within scope

    def rank(self) -> int:
        return {"suggest": 0, "ask-approval": 1, "act": 2}[self.value]


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    BLOCKED = "blocked"
    AWAITING_APPROVAL = "awaiting_approval"
    DONE = "done"
    FAILED = "failed"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


@dataclass
class Agent:
    id: str
    role: str
    chrnum: int
    persona: str = ""
    model: str = "gemma3:4b"
    tools: list[str] = field(default_factory=list)                 # connectors it may operate
    autonomy: dict[str, Autonomy] = field(default_factory=dict)    # connector -> level
    voice_slug: str = ""
    home_pad: int = 0
    state: str = "idle"                                            # idle|working|blocked|awaiting_approval

    def autonomy_for(self, connector: str) -> Autonomy:
        return self.autonomy.get(connector, Autonomy.ASK_APPROVAL)  # safe default


@dataclass
class Task:
    id: str
    agent_id: str
    intent: str
    context: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.QUEUED
    result: Optional[str] = None
    artifacts: list[str] = field(default_factory=list)             # links to real outputs (PR, thread…)
    created_by: str = "human"                                      # human|agent:<id>|slack
    created_at: float = field(default_factory=_now)

    @staticmethod
    def new(agent_id: str, intent: str, **kw) -> "Task":
        return Task(id=_id("task"), agent_id=agent_id, intent=intent, **kw)


@dataclass
class Approval:
    id: str
    task_id: str
    agent_id: str
    connector: str
    action: str
    args: dict[str, Any]
    risk: str = "write"                                            # read|write|destructive
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_by: Optional[str] = None
    created_at: float = field(default_factory=_now)

    @staticmethod
    def new(task_id: str, agent_id: str, connector: str, action: str, args: dict, risk: str = "write") -> "Approval":
        return Approval(id=_id("appr"), task_id=task_id, agent_id=agent_id,
                        connector=connector, action=action, args=args, risk=risk)


@dataclass
class Event:
    id: str
    type: str                                                     # approach|handoff|slack.msg|alert|task.*
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    target: str = ""
    ts: float = field(default_factory=_now)

    @staticmethod
    def new(type: str, payload: dict | None = None, source: str = "", target: str = "") -> "Event":
        return Event(id=_id("evt"), type=type, payload=payload or {}, source=source, target=target)


@dataclass
class AuditEntry:
    id: str
    agent_id: str
    connector: str
    action: str
    args: dict[str, Any]
    autonomy: Autonomy
    human: bool                                                   # was a human present/approving?
    result: str = "ok"
    ts: float = field(default_factory=_now)
