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
from .social_bus import SocialBus
from .hermes_director import HermesDirectorAgent

Action = dict[str, Any]  # {"connector": str, "action": str, "args": dict}


class OfficeService:
    def __init__(self, gateway: ConnectorGateway, bus: Optional[EventBus] = None) -> None:
        self.gateway = gateway
        self.bus = bus or EventBus()
        self.social = SocialBus(self.bus)
        self.agents: dict[str, Agent] = {}
        self.tasks: dict[str, Task] = {}
        self.approvals: dict[str, Approval] = {}
        self._plan: dict[str, list[Action]] = {}   # task_id -> remaining actions
        self._cursor: dict[str, int] = {}           # task_id -> next action index
        self.attached_live_agents: dict[str, dict[str, Any]] = {}
        self.antigravity_ls_info: dict[str, Any] = {}
        self._antigravity_auto_sync: bool = False
        self._last_antigravity_sync_ts: float = 0.0
        self.hermes_director = HermesDirectorAgent(service=self)

    def sync_antigravity_live_agents(
        self,
        *,
        limit: int = 8,
        push_to_engine: bool = False,
        engine_url: str | None = None,
        summaries_db_path: str | None = None,
        brain_dir: str | None = None,
        ls_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Discover active Antigravity sessions and attach them onto the 8 embodied VAO desks."""
        import time as _time
        from .antigravity_bridge import attach_antigravity_agents_to_service

        res = attach_antigravity_agents_to_service(
            self,
            limit=limit,
            push_to_engine=push_to_engine,
            engine_url=engine_url,
            summaries_db_path=summaries_db_path,
            brain_dir=brain_dir,
            ls_info=ls_info,
        )
        self._last_antigravity_sync_ts = _time.time()
        return res

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

    def cancel_task(self, task_id: str, reason: str = "user_interrupted") -> Task:
        task = self.tasks[task_id]
        task.status = TaskStatus.FAILED
        task.result = f"cancelled: {reason}"
        if task.agent_id in self.agents:
            self.agents[task.agent_id].state = "idle"
        # Cancel any associated pending approvals
        for appr in list(self.approvals.values()):
            if appr.task_id == task_id and appr.status == ApprovalStatus.PENDING:
                appr.status = ApprovalStatus.DENIED
                appr.decided_by = "interrupted"
        self.bus.publish(Event.new("task.cancelled", {"task_id": task_id, "reason": reason}, source="user"))
        self._persist_state()
        return task

    def register_custom_agent(self, agent_id: str, name: str = "", role: str = "custom", autonomy: str = "ask_approval") -> Agent:
        from .models import Autonomy
        level = Autonomy.ACT if autonomy == "act" else Autonomy.ASK_APPROVAL
        agent = Agent(
            id=agent_id,
            role=role or name or agent_id,
            state="idle",
            chrnum=0x00C8 + (len(self.agents) % 4),
            autonomy={"slack": level, "github": level, "pagerduty": level},
            tools=["slack", "github", "pagerduty"],
        )
        self.agents[agent_id] = agent
        self.bus.publish(Event.new("agent.registered", {"agent_id": agent_id, "role": role}, source="user"))
        self._persist_state()
        return agent

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
    def agent_monitor(self, agent_id: str) -> dict:
        """Diegetic computer text for one embodied agent (VISION R3).

        Perfect Dark monitors / Perfect Menu and Flight Control both consume this
        projection — it is not a second source of truth.
        """
        agent = self.agents.get(agent_id)
        if agent is None:
            raise KeyError(agent_id)

        agent_tasks = [t for t in self.tasks.values() if t.agent_id == agent_id]
        agent_tasks.sort(key=lambda t: t.created_at, reverse=True)
        current = next(
            (t for t in agent_tasks if t.status in (
                TaskStatus.RUNNING, TaskStatus.QUEUED, TaskStatus.AWAITING_APPROVAL, TaskStatus.BLOCKED
            )),
            agent_tasks[0] if agent_tasks else None,
        )
        pending = [
            a for a in self.approvals.values()
            if a.agent_id == agent_id and a.status == ApprovalStatus.PENDING
        ]
        recent_audit = [e for e in self.gateway.audit if e.agent_id == agent_id][-3:]
        last_tool = None
        if recent_audit:
            last = recent_audit[-1]
            last_tool = {
                "connector": last.connector,
                "action": last.action,
                "result": last.result,
            }

        attached = self.attached_live_agents.get(agent_id)

        lines = [
            f"{agent.role} @ desk {agent.chrnum:#x}",
            f"state: {agent.state}",
        ]
        if current is not None:
            lines.append(f"task: {current.intent[:120]}")
            lines.append(f"task_status: {current.status.value}")
        else:
            lines.append("task: (idle — awaiting dispatch)")
        if attached:
            lines.append(f"antigravity_live: {attached.get('billboard') or attached.get('title')}")
        if pending:
            lines.append(f"approvals: {len(pending)} pending")
        if last_tool and last_tool.get("connector"):
            lines.append(f"last_tool: {last_tool['connector']} {last_tool.get('action') or ''}".strip())

        return {
            "agent_id": agent.id,
            "role": agent.role,
            "chrnum": agent.chrnum,
            "state": agent.state,
            "embodied": True,
            "current_task": None if current is None else {
                "id": current.id,
                "intent": current.intent,
                "status": current.status.value,
            },
            "antigravity_live_agent": attached,
            "pending_approvals": len(pending),
            "last_tool": last_tool,
            "monitor_text": "\n".join(lines),
            "monitor_lines": lines,
        }

    def fleet_status(self) -> dict:
        by_state: dict[str, int] = {}
        embodied: list[dict] = []
        menu_lines: list[str] = []
        for a in self.agents.values():
            by_state[a.state] = by_state.get(a.state, 0) + 1
            try:
                monitor = self.agent_monitor(a.id)
            except KeyError:
                monitor = {"monitor_text": f"{a.role}: {a.state}", "monitor_lines": [f"{a.role}: {a.state}"]}
            monitor_text = monitor.get("monitor_text", "")
            attached = monitor.get("antigravity_live_agent")
            spatial_waypoint = {
                "entity_id": f"entity_{a.id}",
                "agent_id": a.id,
                "chrnum": a.chrnum,
                "badge_state": a.state.upper(),
                "desk_anchor": f"desk_{a.id}",
            }
            if attached:
                spatial_waypoint["antigravity_cascade_id"] = attached.get("cascade_id")
                spatial_waypoint["antigravity_badge_state"] = (
                    "WORKING" if attached.get("is_running") else "IDLE"
                )
            embodied.append({
                "agent_id": a.id,
                "role": a.role,
                "chrnum": a.chrnum,
                "state": a.state,
                "embodied": True,
                "monitor_text": monitor_text,
                "spatial_waypoint": spatial_waypoint,
                "antigravity_live_agent": attached,
            })
            # One compact Perfect Menu row per desk (pipe-safe, no newlines).
            compact = " · ".join(
                part.strip() for part in str(monitor_text).splitlines() if part.strip()
            )
            if not compact:
                compact = f"{a.role}: {a.state}"
            menu_lines.append(compact.replace("|", "/"))
        # Diegetic Perfect Menu / lobby console — single JSON string for the C bridge.
        perfect_menu_text = " | ".join(menu_lines)
        if len(perfect_menu_text) > 1400:
            perfect_menu_text = perfect_menu_text[:1397].rstrip() + "..."
        waypoints = [row["spatial_waypoint"] for row in embodied]
        return {
            "agents": {a.role: a.state for a in self.agents.values()},
            "by_state": by_state,
            "tasks": {s.value: sum(1 for t in self.tasks.values() if t.status == s) for s in TaskStatus},
            "pending_approvals": len(self.pending_approvals()),
            "audit_entries": len(self.gateway.audit),
            # Flight Control + diegetic computers: curated cast of ≤8 bodies.
            "embodiment_capacity": 8,
            "embodied_agents": embodied,
            "spatial_waypoints": waypoints,
            "perfect_menu_text": perfect_menu_text,
            "antigravity_connected": bool(
                self.attached_live_agents or self.antigravity_ls_info.get("connected")
            ),
            "antigravity_language_server": self.antigravity_ls_info,
            "antigravity_attached_count": len(self.attached_live_agents),
            "antigravity_active_count": sum(
                1 for v in self.attached_live_agents.values() if v.get("is_running")
            ),
            "antigravity_live_agents": list(self.attached_live_agents.values()),
        }
