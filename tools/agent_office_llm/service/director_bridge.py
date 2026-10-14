"""Live Director boundary for walk-up DM agent replies (Pass 7 / Pass 9 / Pass 12).

When ``AGENT_OFFICE_DIRECTOR_LIVE=1``, append path tries a brain reply (llm-play
backend when configured, else scripted ``brain.json`` / ``profile_opener``) and
optional POST to the game LLM bridge ``/api/llm/act`` ``agents[].say``. When the
llm-play backend is missing, slow, or errors, Pass 12 returns a typed
``SCRIPTED_FALLBACK`` outcome so DM threads keep in-character scripted lines
instead of static ``AGENT_DM_STUB_REPLIES``.

Full proximity-driven ``office_director.py`` loop remains separate; this module is
the Office Service seam for Z-target / HTTP walk-up append only.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

JSON = dict[str, Any]

try:
    from .schema import IntentRoutingOutcome
except ImportError:
    from schema import IntentRoutingOutcome

# Mirrors create_default_service / office_director ROLE_ORDER chrnums.
AGENT_ID_TO_ROLE: dict[str, str] = {
    "director": "Director",
    "orchestrator": "Orchestrator",
    "research": "Research",
    "code": "Code",
    "qa": "QA",
    "security": "Security",
    "ops": "Ops",
    "comms": "Comms",
}

AGENT_ID_TO_CHRNUM: dict[str, int] = {
    "director": 0x31,
    "orchestrator": 0x32,
    "research": 0x33,
    "code": 0x34,
    "qa": 0x35,
    "security": 0x36,
    "ops": 0x37,
    "comms": 0x38,
}


class DirectorDmReplyStatus(str, Enum):
    """Outcome of attempting a live Director reply for a walk-up DM append."""

    LIVE = "live"
    SCRIPTED_FALLBACK = "scripted_fallback"
    STUB_BOUNDARY = "stub_boundary"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class DirectorDmReplyOutcome:
    """Structured result — never logs utterance body to stdout lifecycle logs."""

    status: DirectorDmReplyStatus
    reply_text: str | None = None
    act_posted: bool = False
    error: str | None = None
    backend: str | None = None
    fallback_reason: str | None = None


@dataclass(frozen=True)
class SupervisoryVoiceCommand:
    """Structured voice command parsed from spatial speech utterance."""

    action: str  # "dispatch" | "create_agent" | "cancel_task"
    target_agent: str | None = None
    intent_or_role: str | None = None
    agent_name: str | None = None


def parse_supervisory_voice_command(human_text: str) -> SupervisoryVoiceCommand | None:
    """Parse hands-free spatial voice commands from player speech transcript."""
    text = (human_text or "").strip().lower()
    if not text:
        return None

    # Pattern 1: Cancel / Interrupt task (e.g. "stop qa", "cancel task", "interrupt code")
    if any(k in text for k in ("stop ", "cancel ", "interrupt ")) and any(a in text for a in AGENT_ID_TO_ROLE):
        for aid in AGENT_ID_TO_ROLE:
            if aid in text:
                return SupervisoryVoiceCommand(action="cancel_task", target_agent=aid)

    # Pattern 2: Create agent (e.g. "create agent sec_ops for security")
    if "create agent" in text:
        parts = text.split("create agent")[-1].strip().split()
        if parts:
            aid = parts[0]
            role = parts[2] if len(parts) >= 3 and parts[1] in ("for", "as") else "General"
            return SupervisoryVoiceCommand(
                action="create_agent",
                target_agent=aid,
                agent_name=aid.capitalize(),
                intent_or_role=role,
            )

    # Pattern 3: Tell/Ask agent to dispatch task (e.g. "tell qa to run unit tests", "ask comms to post update")
    for aid in AGENT_ID_TO_ROLE:
        for prefix in (f"tell {aid} to", f"ask {aid} to", f"have {aid}", f"dispatch {aid}"):
            if prefix in text:
                intent = text.split(prefix)[-1].strip()
                if intent:
                    return SupervisoryVoiceCommand(action="dispatch", target_agent=aid, intent_or_role=intent)

    return None


def parse_semantic_voice_intent(human_text: str) -> IntentRoutingOutcome | None:
    """Parse hands-free spatial voice commands into structured IntentRoutingOutcome.
    
    Supports multi-clause intents (e.g. 'tell qa to run tests and have comms post status').
    """
    text = (human_text or "").strip().lower()
    if not text:
        return None

    # Step 1: Check multi-clause patterns (e.g. split by " and " / " then ")
    if any(sep in text for sep in (" and ", " then ", ";")):
        clauses = [c.strip() for c in text.replace(" and ", ";").replace(" then ", ";").split(";") if c.strip()]
        if len(clauses) > 1:
            target_agents = []
            intents = []
            for clause in clauses:
                cmd = parse_supervisory_voice_command(clause)
                if cmd and cmd.target_agent:
                    target_agents.append(cmd.target_agent)
                    intents.append(cmd.intent_or_role or "General task")
            if target_agents:
                return IntentRoutingOutcome(
                    action="multi_dispatch",
                    target_agents=target_agents,
                    intents=intents,
                    reasoning="multi_clause_voice_command",
                    confidence=0.95,
                )

    # Step 2: Check single-clause pattern
    single_cmd = parse_supervisory_voice_command(human_text)
    if single_cmd is not None:
        return IntentRoutingOutcome(
            action=single_cmd.action,
            target_agents=[single_cmd.target_agent] if single_cmd.target_agent else [],
            intents=[single_cmd.intent_or_role] if single_cmd.intent_or_role else [],
            reasoning="single_clause_voice_command",
            confidence=1.0,
        )

    return None


@dataclass(frozen=True)
class _BrainReplyResult:
    """Internal brain path — separates llm success from offline scripted fallback."""

    reply_text: str
    backend_label: str | None = None
    fallback_reason: str | None = None


_LLM_BACKEND: Any | None = None
_LLM_BACKEND_TRIED = False


def _llm_backend_name() -> str | None:
    """Return llm-play backend name when live + configured; None keeps scripted path."""
    if not director_live_enabled():
        return None
    raw = os.environ.get("AGENT_OFFICE_LLM_BACKEND", "auto").strip().lower()
    if raw in ("", "off", "none", "scripted", "stub"):
        return None
    return raw


def _resolve_llm_backend(repo_root: str | None) -> Any | None:
    """Lazy-load llm-play backend once when live flag + backend name are set."""
    global _LLM_BACKEND, _LLM_BACKEND_TRIED

    if _LLM_BACKEND_TRIED:
        return _LLM_BACKEND
    _LLM_BACKEND_TRIED = True

    backend_name = _llm_backend_name()
    if not backend_name:
        return None

    try:
        from office_director import make_llm_backend  # noqa: WPS433

        llm_play_dir = os.environ.get("AGENT_OFFICE_LLM_PLAY_DIR", "").strip() or None
        play_path = Path(llm_play_dir) if llm_play_dir else None
        _LLM_BACKEND = make_llm_backend(backend_name, play_path)
    except Exception as exc:  # noqa: BLE001 — llm-play optional; scripted fallback remains
        _LLM_BACKEND = None
        print(f"[director_bridge] llm backend unavailable: {exc}")
    return _LLM_BACKEND


def director_live_enabled() -> bool:
    """True when Office Service should attempt live Director reply before static stub."""
    flag = os.environ.get("AGENT_OFFICE_DIRECTOR_LIVE", "").strip().lower()
    return flag in ("1", "true", "yes", "on")


def _env_float(name: str, default: float, *, minimum: float = 0.1) -> float:
    """Parse a positive float timeout from the environment."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, value)


def llm_generate_timeout_sec() -> float:
    """Wall-clock cap for one llm-play ``backend.generate`` call (Pass 12)."""
    return _env_float("AGENT_OFFICE_LLM_TIMEOUT_SEC", 8.0)


def act_post_timeout_sec() -> float:
    """Wall-clock cap for best-effort ``/api/llm/act`` POST (Pass 12)."""
    return _env_float("AGENT_OFFICE_ACT_TIMEOUT_SEC", 0.8, minimum=0.05)


def _generate_with_timeout(
    backend: Any,
    system_prompt: str,
    user_prompt: str,
    timeout_sec: float,
) -> tuple[str | None, str | None]:
    """Run backend.generate off-thread; return (raw_text, fallback_reason)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(backend.generate, system_prompt, user_prompt)
        try:
            return future.result(timeout=timeout_sec), None
        except concurrent.futures.TimeoutError:
            return None, "backend_timeout"
        except Exception as exc:  # noqa: BLE001 — llm-play errors map to scripted fallback
            return None, f"backend_error:{type(exc).__name__}"


def _llm_bridge_base() -> str:
    return os.environ.get("AGENT_OFFICE_LLM_BRIDGE_URL", "http://127.0.0.1:8780").rstrip("/")


def _characters_dir(repo_root: str | None) -> Path:
    root = repo_root or os.environ.get("PD_REPO_ROOT", "").strip()
    if not root:
        root = str(Path(__file__).resolve().parents[3])
    return Path(root) / "tools" / "agent_office_llm" / "characters"


def _scripted_reply_for_role(role: str, human_text: str) -> str:
    """Deterministic in-character line — same shape as office_director scripted fallback."""
    from office_director import _compact_reply, profile_opener  # noqa: WPS433

    opener = profile_opener(role)
    utterance = (human_text or "").strip()
    if utterance:
        return _compact_reply(f"{opener} I heard you: {utterance}")
    return _compact_reply(opener)


def _brain_reply_result(
    agent_id: str,
    human_text: str,
    repo_root: str | None,
) -> _BrainReplyResult | None:
    """Load brain.json when present; llm-play with timeout + offline scripted fallback."""
    role = AGENT_ID_TO_ROLE.get(agent_id)
    if not role:
        return None

    backend_requested = _llm_backend_name() is not None
    backend = _resolve_llm_backend(repo_root) if director_live_enabled() else None
    backend_label = getattr(backend, "name", "llm") if backend is not None else None

    chars_dir = _characters_dir(repo_root)
    brain_path = chars_dir / agent_id / "brain.json"
    profile: JSON | None = None
    if brain_path.is_file():
        try:
            profile = json.loads(brain_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            profile = None
    if profile is None and backend is not None:
        profile = {"slug": agent_id, "role": role}
    if profile is not None:
        try:
            from .antigravity_bridge import DESK_ORDER, discover_antigravity_live_agents

            desk_index = next((i for i, (did, _, _) in enumerate(DESK_ORDER) if did == agent_id), -1)
            if desk_index >= 0 and os.environ.get("AGENT_OFFICE_ATTACH_ANTIGRAVITY", "1") != "0":
                live_disc = discover_antigravity_live_agents(limit=8)
                live_list = live_disc.get("agents") or []
                if desk_index < len(live_list):
                    profile = dict(profile)
                    know = dict(profile.get("knowledge") or {})
                    know["antigravity_live_agent"] = {
                        "cascade_id": live_list[desk_index]["cascade_id"],
                        "title": live_list[desk_index]["title"],
                        "step_count": live_list[desk_index]["step_count"],
                        "last_tool_action": live_list[desk_index]["last_tool_action"],
                        "is_running": live_list[desk_index]["is_running"],
                    }
                    profile["knowledge"] = know
        except Exception as exc:
            _ = exc

    from office_director import AgentBrain  # noqa: WPS433

    if profile is not None and backend is not None:
        brain = AgentBrain(profile, backend=None, persist_memory=False)
        raw, fallback_reason = _generate_with_timeout(
            backend,
            brain._system_prompt(),
            brain._user_prompt(human_text),
            llm_generate_timeout_sec(),
        )
        if raw is not None:
            return _BrainReplyResult(
                reply_text=brain._extract_reply(raw),
                backend_label=backend_label,
            )
        return _BrainReplyResult(
            reply_text=brain._scripted_reply(human_text),
            backend_label=None,
            fallback_reason=fallback_reason or "backend_error",
        )

    if backend_requested and backend is None:
        return _BrainReplyResult(
            reply_text=_scripted_reply_for_role(role, human_text),
            backend_label=None,
            fallback_reason="backend_unavailable",
        )

    if profile is not None:
        try:
            brain = AgentBrain(profile, backend=None, persist_memory=False)
            return _BrainReplyResult(reply_text=brain.respond(human_text))
        except (KeyError, ValueError):
            pass

    return _BrainReplyResult(reply_text=_scripted_reply_for_role(role, human_text))


def post_act_say(agent_id: str, line: str) -> bool:
    """POST say payload to game LLM bridge; best-effort — DM persistence does not depend on it."""
    chrnum = AGENT_ID_TO_CHRNUM.get(agent_id)
    if chrnum is None or not line.strip():
        return False
    payload = {"agents": [{"chrnum": chrnum, "say": line.strip(), "face_player": True}]}
    url = _llm_bridge_base() + "/api/llm/act"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=act_post_timeout_sec()) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False


def director_dm_reply_outcome(
    agent_id: str,
    human_text: str,
    *,
    repo_root: str | None = None,
) -> DirectorDmReplyOutcome:
    """Try live Director reply + optional /act say; scripted fallback when llm-play fails."""
    target = str(agent_id).strip()
    if not director_live_enabled():
        return DirectorDmReplyOutcome(status=DirectorDmReplyStatus.STUB_BOUNDARY)

    brain_result = _brain_reply_result(target, human_text, repo_root)
    if brain_result is None:
        return DirectorDmReplyOutcome(
            status=DirectorDmReplyStatus.UNAVAILABLE,
            error=f"no reply path for agent: {target}",
        )

    reply = brain_result.reply_text
    act_posted = post_act_say(target, reply)
    if brain_result.fallback_reason:
        return DirectorDmReplyOutcome(
            status=DirectorDmReplyStatus.SCRIPTED_FALLBACK,
            reply_text=reply,
            act_posted=act_posted,
            fallback_reason=brain_result.fallback_reason,
        )

    return DirectorDmReplyOutcome(
        status=DirectorDmReplyStatus.LIVE,
        reply_text=reply,
        act_posted=act_posted,
        backend=brain_result.backend_label,
    )
