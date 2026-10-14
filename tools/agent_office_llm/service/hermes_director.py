"""Hermes Director Agent — Autonomous Swarm Lifecycle Supervisor.

Uses Nous Hermes tool-calling architecture to decompose goals, manage task dispatches,
evaluate pending connector approvals, and auto-interrupt failing or stalled agent tasks.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure llm-play repo is in sys.path for game_llm engine access
llm_play_root = Path(__file__).resolve().parents[4] / "llm-play"
if llm_play_root.exists() and str(llm_play_root) not in sys.path:
    sys.path.insert(0, str(llm_play_root))

try:
    from game_llm.engine.backends.hermes import HermesBackend, parse_hermes_output
except ImportError:
    class HermesBackend:  # type: ignore[no-redef]
        def generate(self, system_prompt: str, user_prompt: str) -> str:
            return "<thought>Hermes Director active.</thought>"

    def parse_hermes_output(text: str):  # type: ignore[misc]
        return "Hermes Director active.", [], text


class HermesDirectorAgent:
    def __init__(self, service: Any = None) -> None:
        self.service = service
        self.backend = HermesBackend()
        self.autopilot_enabled: bool = False
        self.reasoning_log: List[Dict[str, Any]] = []
        self.last_supervision_ts: float = 0.0

    def _resolve_security_agent_id(self) -> str:
        if self.service is not None and hasattr(self.service, "agents"):
            if "sec_ops" in self.service.agents:
                return "sec_ops"
            if "security" in self.service.agents:
                return "security"
        return "security"

    def decompose_goal(self, goal: str) -> Dict[str, Any]:
        """Decompose a high-level user goal into multi-agent task DAG dispatches."""
        system_prompt = (
            "You are Hermes Director, an autonomous swarm supervisor. "
            "Decompose the user goal into multi-agent dispatches for roles: comms, qa, ops, research, security.\n"
            "Respond with your reasoning in <thought>...</thought> and tool calls in "
            "<tool_call>{\"name\": \"dispatch_task\", \"arguments\": {\"target_agent\": \"<role>\", \"intent\": \"<intent>\"}}</tool_call>."
        )
        user_prompt = f"Goal to decompose: {goal}"
        raw_output = self.backend.generate(system_prompt, user_prompt)
        thought, tool_calls, _ = parse_hermes_output(raw_output)

        dispatches: List[Dict[str, str]] = []

        if tool_calls:
            for tc in tool_calls:
                args = tc.get("arguments", {})
                target = args.get("target_agent") or args.get("agent_id")
                intent = args.get("intent") or args.get("task")
                if target and intent:
                    dispatches.append({"target_agent": str(target), "intent": str(intent)})

        if not dispatches:
            lowered = goal.lower()
            if "release" in lowered or "test" in lowered:
                dispatches.append({"target_agent": "qa", "intent": "Execute unit and integration test suite"})
                dispatches.append({"target_agent": "comms", "intent": "Draft release notes and status announcement"})
                dispatches.append({"target_agent": "ops", "intent": "Verify build artifacts and deployment readiness"})
            elif "security" in lowered or "audit" in lowered:
                sec_id = self._resolve_security_agent_id()
                dispatches.append({"target_agent": sec_id, "intent": "Audit tenant data boundaries and API keys"})
                dispatches.append({"target_agent": "qa", "intent": "Run security regression suite"})
            else:
                dispatches.append({"target_agent": "research", "intent": f"Analyze requirements for: {goal}"})
                dispatches.append({"target_agent": "qa", "intent": f"Prepare validation plan for: {goal}"})

        executed_tasks: List[Dict[str, str]] = []
        if self.service is not None:
            for d in dispatches:
                target_id = d["target_agent"]
                if target_id == "sec_ops" and "sec_ops" not in self.service.agents and "security" in self.service.agents:
                    target_id = "security"
                try:
                    task = self.service.dispatch(target_id, d["intent"], created_by="hermes_director")
                    executed_tasks.append({"agent_id": target_id, "task_id": task.id, "intent": d["intent"]})
                except Exception as err:
                    executed_tasks.append({"agent_id": target_id, "error": str(err), "intent": d["intent"]})

        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "action": "decompose_goal",
            "goal": goal,
            "thought": thought or "Decomposed goal into structured multi-agent workflow DAG.",
            "dispatches": dispatches,
            "executed_tasks": executed_tasks,
        }
        self.reasoning_log.append(entry)
        return entry

    def evaluate_swarm_lifecycle(self) -> Dict[str, Any]:
        """Supervise all virtual office agents, connector approvals, and active tasks."""
        self.last_supervision_ts = time.time()
        actions_taken: List[Dict[str, Any]] = []

        if self.service is None:
            return {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "action": "evaluate_swarm_lifecycle",
                "thought": "OfficeService unavailable.",
                "actions_taken": [],
            }

        pending_approvals = self.service.pending_approvals()
        for appr in pending_approvals:
            card = getattr(appr, "card", None)
            if isinstance(card, dict):
                action_name = str(card.get("action") or "")
                auto_ok = bool(card.get("auto_approved")) or "read" in action_name.lower()
            else:
                action_name = str(getattr(appr, "action", "") or "")
                args_dict = getattr(appr, "args", {}) or {}
                risk_val = str(getattr(appr, "risk", "write") or "write")
                auto_ok = (
                    bool(args_dict.get("auto_approved"))
                    or risk_val == "read"
                    or "read" in action_name.lower()
                )
            if auto_ok:
                try:
                    if hasattr(self.service, "approve"):
                        self.service.approve(appr.id, decided_by="hermes_director")
                    elif hasattr(self.service.gateway, "perform_approval"):
                        self.service.gateway.perform_approval(appr.id, approved=True, reviewer="hermes_director")
                    actions_taken.append({
                        "type": "approve_card",
                        "approval_id": appr.id,
                        "agent_id": appr.agent_id,
                        "action": action_name,
                    })
                except Exception as err:
                    actions_taken.append({"type": "approval_error", "approval_id": appr.id, "error": str(err)})

        for task_id, task in list(self.service.tasks.items()):
            status_val = str(getattr(task.status, "value", task.status))
            already_cancelled = str(task.result or "").startswith("cancelled:")
            if status_val in ("failed", "error") and not already_cancelled:
                try:
                    self.service.cancel_task(task_id, reason="interrupted_by_hermes_director")
                    actions_taken.append({
                        "type": "interrupt_task",
                        "task_id": task_id,
                        "agent_id": task.agent_id,
                        "reason": "Task failed or stalled",
                    })
                except Exception as err:
                    actions_taken.append({
                        "type": "interrupt_error",
                        "task_id": task_id,
                        "error": str(err),
                    })

        fleet = self.service.fleet_status()
        thought_summary = (
            f"Supervised fleet ({len(fleet.get('embodied_agents', []))} agents). "
            f"Evaluated {len(pending_approvals)} approvals, executed {len(actions_taken)} actions."
        )

        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "action": "evaluate_swarm_lifecycle",
            "thought": thought_summary,
            "actions_taken": actions_taken,
            "auto_approved": [a["approval_id"] for a in actions_taken if a.get("type") == "approve_card"],
            "interrupted_tasks": [a["task_id"] for a in actions_taken if a.get("type") == "interrupt_task"],
            "fleet_summary": fleet.get("by_state", {}),
            "autopilot": self.autopilot_enabled,
        }
        self.reasoning_log.append(entry)
        if len(self.reasoning_log) > 50:
            self.reasoning_log = self.reasoning_log[-50:]
        return entry

    def status(self) -> Dict[str, Any]:
        """Return Hermes Director status and reasoning log."""
        return {
            "agent_id": "hermes",
            "name": "Hermes Director",
            "role": "Supervisory Director & Lifecycle Orchestrator",
            "autopilot_enabled": self.autopilot_enabled,
            "last_supervision_ts": self.last_supervision_ts,
            "reasoning_log_count": len(self.reasoning_log),
            "latest_thought": self.reasoning_log[-1]["thought"] if self.reasoning_log else "Hermes Director standing by.",
            "reasoning_log": self.reasoning_log[-10:],
        }
