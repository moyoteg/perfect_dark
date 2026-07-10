"""Connector Gateway — the single audited door to real tools (VISION §5, §6.4).

Agents never hold credentials or call MCP directly. They ask the gateway to invoke
a connector action; the gateway enforces the agent's per-tool autonomy level, records
an audit entry, and (for ask-approval actions) refuses to execute without a
human-present approval token. Connectors here are stdlib stubs that mirror the shape
of the real MCP connectors (Slack, GitHub, PagerDuty, …) so the whole control plane is
testable offline; swap the `.call` body for a real MCP invocation in production.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .models import Agent, AuditEntry, Autonomy, _id


class PolicyError(Exception):
    """Raised when an action is blocked by autonomy policy (needs approval / suggest-only)."""


# risk classification per connector action; drives the default approval gate.
RISK = {"read": "read", "write": "write", "destructive": "destructive"}


@dataclass
class ConnectorResult:
    ok: bool
    data: Any = None
    error: Optional[str] = None


@dataclass
class Connector:
    """One tool. `actions` maps action name -> (risk, fn(args)->data)."""
    name: str
    actions: dict[str, tuple[str, Callable[[dict], Any]]] = field(default_factory=dict)

    def risk_of(self, action: str) -> str:
        return self.actions.get(action, ("write", None))[0]

    def call(self, action: str, args: dict) -> ConnectorResult:
        if action not in self.actions:
            return ConnectorResult(False, error=f"unknown action {self.name}.{action}")
        try:
            return ConnectorResult(True, data=self.actions[action][1](args))
        except Exception as e:  # noqa: BLE001 - surface connector failure as a result, never crash
            return ConnectorResult(False, error=str(e))


class ConnectorGateway:
    def __init__(self) -> None:
        self._connectors: dict[str, Connector] = {}
        self.audit: list[AuditEntry] = []

    def register(self, connector: Connector) -> None:
        self._connectors[connector.name] = connector

    def available(self) -> list[str]:
        return sorted(self._connectors)

    def invoke(
        self,
        agent: Agent,
        connector: str,
        action: str,
        args: dict | None = None,
        *,
        approved: bool = False,
    ) -> ConnectorResult:
        """Run connector.action for agent, enforcing autonomy + audit.

        - read actions: always allowed (autonomy >= suggest).
        - write/destructive: require autonomy `act`, OR autonomy `ask-approval` WITH a
          human-present approval (`approved=True`). `suggest` never executes.
        Raises PolicyError when blocked (the caller stages an Approval instead).
        """
        args = args or {}
        conn = self._connectors.get(connector)
        if conn is None:
            return ConnectorResult(False, error=f"no such connector: {connector}")
        if connector not in agent.tools:
            raise PolicyError(f"{agent.id} is not equipped with {connector}")

        level = agent.autonomy_for(connector)
        risk = conn.risk_of(action)
        human_present = approved

        if risk == "read":
            allowed = level.rank() >= Autonomy.SUGGEST.rank()  # everyone can read
        elif level == Autonomy.ACT and risk != "destructive":
            allowed = True                                     # autonomous within scope (not destructive)
        elif level.rank() >= Autonomy.ASK_APPROVAL.rank() and human_present:
            allowed = True                                     # staged + human approved
        else:
            allowed = False

        if not allowed:
            raise PolicyError(
                f"{agent.id} needs approval for {connector}.{action} "
                f"(autonomy={level.value}, risk={risk})"
            )

        result = conn.call(action, args)
        self.audit.append(AuditEntry(
            id=_id("aud"), agent_id=agent.id, connector=connector, action=action,
            args=args, autonomy=level, human=human_present,
            result="ok" if result.ok else f"error:{result.error}",
        ))
        return result


# --------------------------------------------------------------------------
# Stub connectors — mirror real MCP shapes; replace `.call` bodies in production.
# --------------------------------------------------------------------------
def slack_stub(sent_sink: list[dict] | None = None) -> Connector:
    """Offline stub Slack connector — always records post_message to sent_sink."""
    return slack_connector(sent_sink, force_stub=True)


def slack_connector(
    sent_sink: list[dict] | None = None,
    *,
    repo_root: str | None = None,
    force_stub: bool = False,
) -> Connector:
    """Comms agent's Slack. read_threads (read), post_message (write).

    When OAuth bot token is installed (Pass 32), approved post_message actions call
    slack_outbound_post_outcome → real chat.postMessage. Without a token, falls back
    to the offline stub (append to sent_sink) so tests and local-first dev unchanged.
    """
    from .slack_api import SlackOutboundPostStatus, slack_bot_token_installed, slack_outbound_post_outcome

    inbox = [
        {"channel": "#eng", "text": "@you can you review the vault-log PR?", "mention": True},
        {"channel": "#marketing", "text": "when does the feature ship?", "mention": False},
    ]
    sent = sent_sink if sent_sink is not None else []

    def read_threads(args: dict) -> Any:
        return {"threads": inbox, "awaiting_reply": len(inbox),
                "mentions_of_you": sum(1 for m in inbox if m["mention"])}

    def post_message(args: dict) -> Any:
        channel = str(args.get("channel") or "#general").strip()
        text = str(args.get("text") or "").strip()
        if not force_stub and slack_bot_token_installed(repo_root):
            post_url = os.environ.get("SLACK_CHAT_POST_URL", "").strip() or None
            outcome = slack_outbound_post_outcome(
                channel=channel,
                text=text,
                repo_root=repo_root,
                post_url=post_url,
            )
            if outcome.status == SlackOutboundPostStatus.POSTED:
                return {
                    "posted": True,
                    "channel": outcome.channel,
                    "text": outcome.text,
                    "slack_ts": outcome.slack_ts,
                    "live": True,
                }
            raise RuntimeError(outcome.error or outcome.status.value)
        msg = {"channel": channel, "text": text}
        sent.append(msg)
        return {"posted": True, **msg}

    return Connector("slack", {
        "read_threads": ("read", read_threads),
        "post_message": ("write", post_message),
    })


def pagerduty_stub() -> Connector:
    """Ops agent's PagerDuty. read_incidents (read), page_oncall (write)."""
    def read_incidents(args: dict) -> Any:
        return {"open": [{"id": "INC-42", "title": "prod p99 spiking", "severity": "high"}]}

    def page_oncall(args: dict) -> Any:
        return {"paged": True, "incident": args.get("incident", "INC-42")}

    return Connector("pagerduty", {
        "read_incidents": ("read", read_incidents),
        "page_oncall": ("write", page_oncall),
    })


def github_stub() -> Connector:
    """Code/QA agents' GitHub. read_checks (read), open_pr (write), merge (destructive)."""
    def read_checks(args: dict) -> Any:
        return {"pr": args.get("pr"), "checks": "green"}

    def open_pr(args: dict) -> Any:
        return {"opened": True, "url": f"https://github.example/pr/{args.get('branch', 'x')}"}

    def merge(args: dict) -> Any:
        return {"merged": True, "pr": args.get("pr")}

    return Connector("github", {
        "read_checks": ("read", read_checks),
        "open_pr": ("write", open_pr),
        "merge": ("destructive", merge),
    })
