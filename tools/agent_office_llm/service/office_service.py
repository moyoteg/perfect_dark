"""Office Service — dispatch, approvals, and the fleet control plane (VISION §6).

Ties the roster, task queue, connector gateway, and event bus into the management
primitives the 3D client drives: dispatch a task to an agent, let the agent act
through tools, gate side effects behind human-present approvals, and surface fleet
state. In-memory and synchronous for testability; a real deployment wraps this in the
persistent service + HTTP API of VISION §6.4.
"""
from __future__ import annotations

from typing import Any, Optional

from .connectors import ConnectorGateway, PolicyError
from .event_bus import EventBus
from .models import (
    Agent, Approval, ApprovalStatus, Event, Task, TaskStatus,
)

Action = dict[str, Any]  # {"connector": str, "action": str, "args": dict}


class OfficeService:
    def __init__(self, gateway: ConnectorGateway, bus: Optional[EventBus] = None) -> None:
        self.gateway = gateway
        self.bus = bus or EventBus()
        self.agents: dict[str, Agent] = {}
        self.tasks: dict[str, Task] = {}
        self.approvals: dict[str, Approval] = {}
        self._plan: dict[str, list[Action]] = {}   # task_id -> remaining actions
        self._cursor: dict[str, int] = {}           # task_id -> next action index

    # -- roster ------------------------------------------------------------
    def add_agent(self, agent: Agent) -> None:
        self.agents[agent.id] = agent

    def agent(self, agent_id: str) -> Agent:
        return self.agents[agent_id]

    # -- dispatch ----------------------------------------------------------
    def dispatch(self, agent_id: str, intent: str, context: dict | None = None,
                 created_by: str = "human") -> Task:
        if agent_id not in self.agents:
            raise KeyError(f"no agent {agent_id}")
        task = Task.new(agent_id, intent, context=context or {}, created_by=created_by)
        self.tasks[task.id] = task
        self.bus.publish(Event.new("task.created", {"intent": intent}, source=created_by, target=agent_id))
        return task

    def perform(self, task: Task, actions: list[Action]) -> Task:
        """Run a task's planned connector actions in order. On a policy block, stage an
        Approval and pause (task -> awaiting_approval); resume via approve()."""
        self._plan[task.id] = list(actions)
        self._cursor[task.id] = 0
        return self._run(task)

    def _run(self, task: Task) -> Task:
        agent = self.agents[task.agent_id]
        task.status = TaskStatus.RUNNING
        agent.state = "working"
        actions = self._plan.get(task.id, [])
        i = self._cursor.get(task.id, 0)

        while i < len(actions):
            act = actions[i]
            try:
                res = self.gateway.invoke(agent, act["connector"], act["action"], act.get("args", {}))
            except PolicyError:
                # Side effect needs a human — stage approval and pause here.
                appr = Approval.new(task.id, agent.id, act["connector"], act["action"],
                                    act.get("args", {}),
                                    risk=self._risk(act))
                self.approvals[appr.id] = appr
                self._cursor[task.id] = i  # resume AT this action after approval
                task.status = TaskStatus.AWAITING_APPROVAL
                agent.state = "awaiting_approval"
                self.bus.publish(Event.new("approval.pending",
                                           {"approval_id": appr.id, "action": act["action"]},
                                           source=agent.id))
                self._persist_state()
                return task
            if not res.ok:
                task.status = TaskStatus.FAILED
                task.result = f"{act['connector']}.{act['action']} failed: {res.error}"
                agent.state = "idle"
                self.bus.publish(Event.new("task.failed", {"task": task.id}, source=agent.id))
                return task
            if res.data is not None:
                task.artifacts.append(str(res.data))
            i += 1
            self._cursor[task.id] = i

        task.status = TaskStatus.DONE
        task.result = task.result or (task.artifacts[-1] if task.artifacts else "done")
        agent.state = "idle"
        self.bus.publish(Event.new("task.done", {"task": task.id}, source=agent.id))
        return task

    def _risk(self, act: Action) -> str:
        conn = self.gateway._connectors.get(act["connector"])
        return conn.risk_of(act["action"]) if conn else "write"

    # -- approvals (the human-present gate) --------------------------------
    def pending_approvals(self) -> list[Approval]:
        return [a for a in self.approvals.values() if a.status == ApprovalStatus.PENDING]

    def approve(self, approval_id: str, decided_by: str = "human") -> Task:
        appr = self.approvals[approval_id]
        appr.status = ApprovalStatus.APPROVED
        appr.decided_by = decided_by
        agent = self.agents[appr.agent_id]
        task = self.tasks[appr.task_id]
        # Execute the staged action WITH the human-present token, then continue the plan.
        res = self.gateway.invoke(agent, appr.connector, appr.action, appr.args, approved=True)
        self.bus.publish(Event.new("approval.approved", {"approval_id": approval_id}, source=decided_by))
        if not res.ok:
            task.status = TaskStatus.FAILED
            task.result = f"{appr.connector}.{appr.action} failed: {res.error}"
            agent.state = "idle"
            self._persist_state()
            return task
        if res.data is not None:
            task.artifacts.append(str(res.data))
        self._cursor[task.id] = self._cursor.get(task.id, 0) + 1  # move past the approved action
        resumed = self._run(task)
        self._persist_state()
        return resumed

    def deny(self, approval_id: str, decided_by: str = "human") -> Task:
        appr = self.approvals[approval_id]
        appr.status = ApprovalStatus.DENIED
        appr.decided_by = decided_by
        task = self.tasks[appr.task_id]
        task.status = TaskStatus.BLOCKED
        task.result = f"denied: {appr.connector}.{appr.action}"
        self.agents[appr.agent_id].state = "idle"
        self.bus.publish(Event.new("approval.denied", {"approval_id": approval_id}, source=decided_by))
        self._persist_state()
        return task

    def _persist_state(self) -> None:
        """Pass 38: snapshot pending connector approvals for process restart continuity."""
        from .service_state import maybe_persist_service_state

        maybe_persist_service_state(self)

    # -- inbound (Slack round-trip, VISION §5.2) ---------------------------
    def ingest_slack(self, message: dict) -> Event:
        """A Slack message arrives → world event; a mention of you flags Comms as
        needing you. Returns the published event."""
        needs_you = bool(message.get("mention"))
        ev = self.bus.publish(Event.new("slack.msg", {"message": message, "needs_you": needs_you},
                                        source="slack"))
        for a in self.agents.values():
            if a.role.lower() == "comms":
                a.state = "blocked" if needs_you else a.state
        return ev

    # -- overview (the lobby console, VISION §3) ---------------------------
    def fleet_status(self) -> dict:
        by_state: dict[str, int] = {}
        for a in self.agents.values():
            by_state[a.state] = by_state.get(a.state, 0) + 1
        return {
            "agents": {a.role: a.state for a in self.agents.values()},
            "by_state": by_state,
            "tasks": {s.value: sum(1 for t in self.tasks.values() if t.status == s) for s in TaskStatus},
            "pending_approvals": len(self.pending_approvals()),
            "audit_entries": len(self.gateway.audit),
        }
