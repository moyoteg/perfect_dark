"""Connector Gateway — the single audited door to real tools (VISION §5, §6.4).

Agents never hold credentials or call MCP directly. They ask the gateway to invoke
a connector action; the gateway enforces the agent's per-tool autonomy level, records
an audit entry, and (for ask-approval actions) refuses to execute without a
human-present approval token. Connectors resolve credentials via PragCredentials
vault / tenant connector state / environment variables and execute live HTTP calls
when provisioned, falling back deterministically to offline local simulation when
no external credentials are installed.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .models import Agent, AuditEntry, Autonomy, _id
from .tenant import current_tenant_id, resolve_tenant_state_file


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


def _resolve_connector_credential(
    platform: str,
    env_key: str,
    *,
    repo_root: str | None = None,
) -> str | None:
    """Resolve connector credential via PragCredentials broker, tenant state file, or env."""
    tenant_id = current_tenant_id()
    try:
        from prag_credentials import AgentCredentialBroker  # type: ignore

        broker = AgentCredentialBroker()
        secret = broker.resolve(platform=platform, tenant_id=tenant_id)
        if isinstance(secret, str) and secret.strip():
            return secret.strip()
    except Exception:
        pass

    try:
        state_file = resolve_tenant_state_file(
            f"{platform}_connector.json",
            tenant_id=tenant_id,
            repo_root=repo_root,
        )
        if state_file.is_file():
            raw = json.loads(state_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                tok = str(raw.get("token") or raw.get("api_key") or "").strip()
                if tok:
                    return tok
    except (OSError, ValueError, json.JSONDecodeError):
        pass

    env_val = os.environ.get(env_key, "").strip()
    return env_val or None


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json; charset=utf-8", **headers}
    req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        body = resp.read().decode("utf-8")
        parsed = json.loads(body) if body else {}
        return parsed if isinstance(parsed, dict) else {"raw": parsed}


# --------------------------------------------------------------------------
# Connectors — live HTTP execution when credentials + URL are configured,
# with deterministic offline simulation fallback for local-first dev/tests.
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


def pagerduty_connector(
    sent_sink: list[dict] | None = None,
    *,
    repo_root: str | None = None,
    force_stub: bool = False,
) -> Connector:
    """Ops agent's PagerDuty. read_incidents (read), page_oncall (write)."""
    sent = sent_sink if sent_sink is not None else []

    def read_incidents(args: dict) -> Any:
        return {"open": [{"id": "INC-42", "title": "prod p99 spiking", "severity": "high"}]}

    def page_oncall(args: dict) -> Any:
        incident = str(args.get("incident") or args.get("title") or "INC-42")
        token = (
            _resolve_connector_credential("pagerduty", "PAGERDUTY_API_KEY", repo_root=repo_root)
            or _resolve_connector_credential("pagerduty", "PAGERDUTY_ROUTING_KEY", repo_root=repo_root)
        )
        events_url = os.environ.get("PAGERDUTY_EVENTS_URL", "").strip()
        if not force_stub and token and events_url:
            resp = _post_json(
                events_url,
                {
                    "routing_key": token,
                    "event_action": "trigger",
                    "payload": {
                        "summary": f"Page on-call for {incident}",
                        "severity": "critical",
                        "source": "virtual-agent-office",
                    },
                },
                headers={"Authorization": f"Token token={token}"},
            )
            return {"paged": True, "incident": incident, "live": True, "dedup_key": resp.get("dedup_key", "")}
        record = {"paged": True, "incident": incident}
        sent.append(record)
        return record

    return Connector("pagerduty", {
        "read_incidents": ("read", read_incidents),
        "page_oncall": ("write", page_oncall),
        "create_incident": ("write", page_oncall),
    })


def pagerduty_stub(sent_sink: list[dict] | None = None) -> Connector:
    """Offline-compatible PagerDuty connector factory."""
    return pagerduty_connector(sent_sink, force_stub=True)


def github_connector(
    sent_sink: list[dict] | None = None,
    *,
    repo_root: str | None = None,
    force_stub: bool = False,
) -> Connector:
    """Code/QA agents' GitHub. read_checks (read), open_pr (write), merge (destructive)."""
    sent = sent_sink if sent_sink is not None else []

    def read_checks(args: dict) -> Any:
        return {"pr": args.get("pr"), "checks": "green"}

    def open_pr(args: dict) -> Any:
        branch = str(args.get("branch") or "x")
        title = str(args.get("title") or f"PR for {branch}")
        token = _resolve_connector_credential("github", "GITHUB_TOKEN", repo_root=repo_root)
        api_url = os.environ.get("GITHUB_API_URL", "").strip()
        if not force_stub and token and api_url:
            resp = _post_json(
                f"{api_url.rstrip('/')}/pulls",
                {"head": branch, "base": str(args.get("base") or "main"), "title": title},
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            )
            url = str(resp.get("html_url") or f"{api_url.rstrip('/')}/pr/{branch}")
            return {"opened": True, "url": url, "live": True}
        record = {"opened": True, "url": f"https://github.example/pr/{branch}"}
        sent.append(record)
        return record

    def merge(args: dict) -> Any:
        pr = args.get("pr")
        token = _resolve_connector_credential("github", "GITHUB_TOKEN", repo_root=repo_root)
        api_url = os.environ.get("GITHUB_API_URL", "").strip()
        if not force_stub and token and api_url:
            resp = _post_json(
                f"{api_url.rstrip('/')}/pulls/{pr}/merge",
                {"merge_method": str(args.get("merge_method") or "squash")},
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            )
            return {"merged": bool(resp.get("merged", True)), "pr": pr, "live": True}
        record = {"merged": True, "pr": pr}
        sent.append(record)
        return record

    return Connector("github", {
        "read_checks": ("read", read_checks),
        "open_pr": ("write", open_pr),
        "merge": ("destructive", merge),
    })


def github_stub(sent_sink: list[dict] | None = None) -> Connector:
    """Offline-compatible GitHub connector factory."""
    return github_connector(sent_sink, force_stub=True)
