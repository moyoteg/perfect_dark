#!/usr/bin/env python3
"""Office Director — proximity-driven, per-character LLM conversation for the
Virtual Agent Office.

This remains deliberately dependency-light and runnable:

    # Dry run against a bundled fixture (no game needed) — proves the proximity
    # + brain + dispatch wiring end to end:
    python3 tools/agent_office_llm/office_director.py --dry-run

    # C3 live-brain dry run via llm-play's local backend:
    python3 tools/agent_office_llm/office_director.py --dry-run --llm --utterance "status?"

    # Live, once the engine emits observe.agents[] and accepts act.agents[].say
    # (see journal/agent_office/LLM_CONVERSATION_LAYER.md §3):
    python3 tools/agent_office_llm/office_director.py --url http://127.0.0.1:8780

What works now: perception parsing, earshot/line-of-sight perception slicing,
proximity engine with hysteresis + view-cone, per-agent live-brain dispatch via
llm-play backends, tenant-scoped memory files, R7 social bus background ticker,
Office Service task dispatch + live status billboards, and act payload construction.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

# Must match tools/pdmap/agent_office.py CHR_AGENT_FIRST and GREET_RANGE.
CHR_AGENT_FIRST = 0x31
EARSHOT_RANGE = 650.0    # perception slicing radius for earshot / nearby awareness
ENGAGE_RANGE = 750.0     # start a conversation inside this (world units)
DISENGAGE_RANGE = 950.0  # end it past this (hysteresis so it doesn't flicker)
VIEW_CONE_DOT = 0.1      # generous view cone (cos ~85°)
TICK_HZ = 6.0

# Role order matches VIRTUAL_AGENTS in tools/pdmap/agent_office.py (chrnum = base+offset).
ROLE_ORDER = ["Director", "Orchestrator", "Research", "Code", "QA", "Security", "Ops", "Comms"]
# Maps in-world role labels to Office Service agent ids (shared with Z-target DM threads).
ROLE_TO_AGENT_ID: dict[str, str] = {
    "Director": "director",
    "Orchestrator": "orchestrator",
    "Research": "research",
    "Code": "code",
    "QA": "qa",
    "Security": "security",
    "Ops": "ops",
    "Comms": "comms",
}
AGENT_ID_TO_ROLE_NAME: dict[str, str] = {v: k for k, v in ROLE_TO_AGENT_ID.items()}
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LLM_PLAY_DIR = Path(__file__).resolve().parents[3] / "llm-play"
MAX_REPLY_CHARS = 180


class BrainBackend(Protocol):
    """Minimal subset of the llm-play backend contract used by office brains."""

    name: str

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


InputProvider = Callable[[], Optional[str]]


# ---------------------------------------------------------------------------
# Bridge client (stdlib only)
# ---------------------------------------------------------------------------
class BridgeClient:
    def __init__(self, url: str, prefix: str = "/api/llm") -> None:
        self.base = url.rstrip("/") + prefix

    def observe(self) -> dict[str, Any]:
        with urllib.request.urlopen(self.base + "/observe", timeout=2.0) as r:
            return json.loads(r.read().decode())

    def act(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.base + "/act", data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=2.0) as r:
            return json.loads(r.read().decode())


# ---------------------------------------------------------------------------
# Perception & Earshot / Line-of-Sight Slicing (VISION §6 / §9)
# ---------------------------------------------------------------------------
@dataclass
class AgentView:
    chrnum: int
    role: str
    pos: tuple[float, float, float]
    facing_deg: float
    player_dist: float
    status: str = "work"
    talking: bool = False


def parse_observation(obs: dict[str, Any]) -> tuple[Optional[dict], list[AgentView]]:
    """Extract the player and the office agents from an /observe snapshot.

    Reads the `agents[]` array added in engine §3a. Falls back to scanning
    `actors[]` for chrnum >= CHR_AGENT_FIRST if a build predates that change.
    """
    players = obs.get("players") or []
    player = players[0] if players else None

    agents: list[AgentView] = []
    raw_agents = obs.get("agents")
    if raw_agents:
        for a in raw_agents:
            chrnum = int(a["chrnum"])
            role = a.get("role") or _role_for(chrnum, a.get("role_hint"))
            p = a["pos"]
            agents.append(
                AgentView(
                    chrnum=chrnum,
                    role=role,
                    pos=(p["x"], p["y"], p["z"]),
                    facing_deg=float(a.get("facing_deg", 0.0)),
                    player_dist=float(a.get("player_dist", _dist(player, p) if player else 1e9)),
                    status=str(a.get("status") or "work"),
                    talking=bool(a.get("talking", False)),
                )
            )
    else:
        # Fallback: office agents not yet in observe — scan actors[] by chrnum.
        for a in obs.get("actors", []):
            cid = int(a.get("id", -1))
            if cid >= CHR_AGENT_FIRST and a.get("kind") not in ("player", "bot"):
                p = a["pos"]
                agents.append(
                    AgentView(
                        cid,
                        _role_for(cid),
                        (p["x"], p["y"], p["z"]),
                        float(a.get("facing_deg", 0.0)),
                        _dist(player, p) if player else 1e9,
                    )
                )
    return player, agents


def slice_observation_for_agent(
    obs: dict[str, Any],
    target_chrnum: int,
    *,
    earshot_range: float = EARSHOT_RANGE,
) -> dict[str, Any]:
    """Slice global /observe snapshot so an agent only perceives entities within earshot or LOS.

    Enforces VISION §6/§9: no god-view omniscience across distant rooms or buildings.
    """
    raw_agents = obs.get("agents") or []
    origin_pos: Optional[dict[str, float]] = None
    for a in raw_agents:
        if int(a.get("chrnum", -1)) == target_chrnum:
            origin_pos = a.get("pos")
            break
    if origin_pos is None:
        for a in obs.get("actors") or []:
            if int(a.get("id", -1)) == target_chrnum:
                origin_pos = a.get("pos")
                break

    if origin_pos is None:
        return {
            "tick": obs.get("tick", 0),
            "stage": obs.get("stage", 0),
            "sliced_for_chrnum": target_chrnum,
            "earshot_range": earshot_range,
            "players": [],
            "agents": [],
        }

    ox, oy, oz = float(origin_pos["x"]), float(origin_pos["y"]), float(origin_pos["z"])

    def _within(pos_dict: Optional[dict[str, Any]], visible: bool = False) -> bool:
        if visible:
            return True
        if not isinstance(pos_dict, dict):
            return False
        d = math.dist(
            (ox, oy, oz),
            (float(pos_dict.get("x", 0.0)), float(pos_dict.get("y", 0.0)), float(pos_dict.get("z", 0.0))),
        )
        return d <= earshot_range

    sliced_players = [
        p for p in (obs.get("players") or [])
        if _within(p.get("pos"), bool(p.get("visible", False)))
    ]
    sliced_agents = [
        a for a in raw_agents
        if int(a.get("chrnum", -1)) == target_chrnum
        or _within(a.get("pos"), bool(a.get("visible", False)))
    ]
    return {
        "tick": obs.get("tick", 0),
        "stage": obs.get("stage", 0),
        "sliced_for_chrnum": target_chrnum,
        "earshot_range": earshot_range,
        "players": sliced_players,
        "agents": sliced_agents,
    }


def _role_for(chrnum: int, role_hint: Any = None) -> str:
    if role_hint is not None:
        try:
            hint = int(role_hint)
            if 0 <= hint < len(ROLE_ORDER):
                return ROLE_ORDER[hint]
        except (TypeError, ValueError):
            pass
    idx = chrnum - CHR_AGENT_FIRST
    return ROLE_ORDER[idx] if 0 <= idx < len(ROLE_ORDER) else f"Agent{chrnum:#x}"


def _dist(player: Optional[dict], p: dict) -> float:
    if not player:
        return 1e9
    pp = player["pos"]
    return math.dist((pp["x"], pp["y"], pp["z"]), (p["x"], p["y"], p["z"]))


def player_faces(player: dict, agent: AgentView) -> bool:
    """True if the player is roughly looking at the agent (view-cone gate)."""
    pp = player["pos"]
    bearing = math.atan2(agent.pos[0] - pp["x"], agent.pos[2] - pp["z"])
    facing = math.radians(player.get("facing_deg", 0.0))
    return math.cos(bearing - facing) >= VIEW_CONE_DOT


# ---------------------------------------------------------------------------
# Brains
# ---------------------------------------------------------------------------
class AgentBrain:
    """One per character. Loaded from characters/<slug>/brain.json."""

    def __init__(
        self,
        profile: dict[str, Any],
        *,
        backend: Optional[BrainBackend] = None,
        repo_root: Path = REPO_ROOT,
        max_memory_turns: int = 6,
        persist_memory: bool = True,
        account_pool: Optional[Any] = None,
        tenant_id: Optional[str] = None,
    ) -> None:
        self.slug = profile["slug"]
        self.role = profile.get("role", self.slug)
        self.system_prompt = profile.get("system_prompt", "")
        self.voice_slug = profile.get("voice_slug", self.slug)
        self.knowledge = profile.get("knowledge", {})
        self.backend = backend
        self.account_pool = account_pool
        self.max_memory_turns = max_memory_turns
        self.persist_memory = persist_memory
        self.tenant_id = tenant_id
        self.memory_file = self._resolve_memory_file(profile.get("memory_file"), repo_root, tenant_id=tenant_id)
        self.memory: list[tuple[str, str]] = self._load_memory()

    def respond(self, player_said: Optional[str]) -> str:
        """Return one in-character line.

        C3: when a llm-play backend is configured, use it for one short in-character
        reply. Without a backend, keep the deterministic scripted fallback so dry-run
        and tests remain useful offline.
        """
        player_text = (player_said or "").strip()
        if self.backend is not None:
            try:
                raw = self._generate_with_optional_lease(self._system_prompt(), self._user_prompt(player_text))
                line = self._extract_reply(raw)
            except Exception as e:  # noqa: BLE001 - live brain failures fall back visibly in logs
                print(f"[brain failed] {self.role}: {e}")
                line = self._scripted_reply(player_text)
        else:
            line = self._scripted_reply(player_text)

        self._remember(player_text or "[approach]", line)
        return line

    def ingest_rumor(self, kind: str, from_office: str, text: str) -> None:
        """Record an R7 social bus rumor/guard_report/handoff into this agent's memory."""
        cleaned = " ".join((text or "").split()).strip()
        if not cleaned:
            return
        entry = f"[{kind} from {from_office}] {cleaned}"
        self.memory.append(("rumor", entry))
        self.memory = self.memory[-self.max_memory_turns * 2 :]
        if not self.persist_memory or self.memory_file is None:
            return
        try:
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            with self.memory_file.open("a", encoding="utf-8") as fh:
                fh.write(f"- rumor: {entry}\n")
        except OSError as e:
            print(f"[memory write failed] {self.role}: {e}")

    def _generate_with_optional_lease(self, system_prompt: str, user_prompt: str) -> str:
        """Lease an account per utterance when account_pool is configured (Pass 4 stub)."""
        pool = self.account_pool
        if pool is None:
            return self.backend.generate(system_prompt, user_prompt)  # type: ignore[union-attr]

        from service.account_pool import (  # noqa: WPS433 — lazy import keeps dry-run deps light
            AccountAllocationRequest,
            AccountPoolScenario,
            lease_account,
        )

        request = AccountAllocationRequest(
            pool_id=pool.pool_id,
            requester=f"brain:{self.role}",
            purpose="engage_player",
            scenario_id=AccountPoolScenario.ONE_POOL_ONE_ACCOUNT.value,
        )
        with lease_account(pool, request) as _lease:
            return self.backend.generate(system_prompt, user_prompt)  # type: ignore[union-attr]

    def _system_prompt(self) -> str:
        """Constrain free-form character prompts to the bridge's HUD-safe JSON reply."""
        base = self.system_prompt or (
            f"You are the {self.role} agent in the Virtual Agent Office. "
            "Stay in character and answer briefly."
        )
        return (
            f"{base}\n\n"
            "Return ONLY valid JSON with this shape: {\"reply\":\"short line\"}. "
            f"The reply must be under {MAX_REPLY_CHARS} characters, one or two short "
            "sentences, no markdown, no stage directions."
        )

    def _user_prompt(self, player_text: str) -> str:
        """Build the per-turn prompt from the player utterance, profile knowledge, and memory."""
        event = player_text or "The player approached your desk. Greet them and ask what they need."
        recent = "\n".join(f"{speaker}: {text}" for speaker, text in self.memory[-self.max_memory_turns * 2:])
        knowledge = json.dumps(self.knowledge, ensure_ascii=True, sort_keys=True)
        return (
            f"Role: {self.role}\n"
            f"Knowledge policy: {knowledge}\n"
            f"Recent memory:\n{recent or '(none)'}\n\n"
            f"Player: {event}\n"
            "Agent reply JSON:"
        )

    def _extract_reply(self, raw: str) -> str:
        """Accept llm-play JSON replies, JSON strings, or plain text, then clamp for HUD use."""
        text = _strip_fences(raw).strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                for key in ("reply", "say", "text"):
                    value = data.get(key)
                    if isinstance(value, str) and value.strip():
                        return _compact_reply(value)
            if isinstance(data, str):
                return _compact_reply(data)
        except json.JSONDecodeError:
            pass
        return _compact_reply(text)

    def _scripted_reply(self, player_text: str) -> str:
        opener = profile_opener(self.role)
        if player_text:
            return _compact_reply(f"{opener} I heard you: {player_text}")
        return _compact_reply(opener)

    def _resolve_memory_file(
        self,
        value: Optional[str],
        repo_root: Path | str,
        *,
        tenant_id: Optional[str] = None,
    ) -> Optional[Path]:
        if not value:
            return None
        root_path = Path(repo_root)
        path = Path(value)
        if path.is_absolute():
            return path
        try:
            from service.tenant import (
                DEFAULT_TENANT_ID,
                current_tenant_id,
                normalize_tenant_id,
                resolve_tenant_state_root,
            )

            tid = normalize_tenant_id(tenant_id or current_tenant_id())
            tenant_mem_dir = resolve_tenant_state_root(tid, str(root_path)) / "memory"
            if tid != DEFAULT_TENANT_ID:
                return tenant_mem_dir / path.name
            if (tenant_mem_dir / path.name).exists() or (tenant_mem_dir / path.name).is_symlink():
                return tenant_mem_dir / path.name
        except Exception:
            pass
        return root_path / path

    def _load_memory(self) -> list[tuple[str, str]]:
        """Load the recent Markdown memory tail; corrupt or absent files simply start empty."""
        if not self.persist_memory or self.memory_file is None or not self.memory_file.exists():
            return []
        turns: list[tuple[str, str]] = []
        try:
            for line in self.memory_file.read_text(encoding="utf-8").splitlines()[-24:]:
                match = re.match(r"- (player|agent|rumor): (.*)", line.strip(), re.IGNORECASE)
                if match:
                    turns.append((match.group(1).lower(), match.group(2).strip()))
        except OSError as e:
            print(f"[memory read failed] {self.role}: {e}")
        return turns[-self.max_memory_turns * 2:]

    def _remember(self, player_text: str, reply: str) -> None:
        """Persist a tiny rolling transcript so each character has continuity between runs."""
        self.memory.extend([("player", player_text), ("agent", reply)])
        self.memory = self.memory[-self.max_memory_turns * 2:]
        if not self.persist_memory or self.memory_file is None:
            return
        try:
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            with self.memory_file.open("a", encoding="utf-8") as fh:
                fh.write(f"- player: {player_text}\n- agent: {reply}\n")
        except OSError as e:
            print(f"[memory write failed] {self.role}: {e}")


def profile_opener(role: str) -> str:
    return {
        "Director": "Stand-up's running long. What do you need?",
        "Research": "I'm mid-index — 847 files deep. Ask quickly.",
        "Security": "Badge checks out. Keep it moving.",
        "Ops": "Pipeline's green. Don't touch the deploy.",
    }.get(role, f"[{role}] …yes?")


def _strip_fences(text: str) -> str:
    """Remove common Markdown fences that local models sometimes add despite instructions."""
    stripped = (text or "").strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _compact_reply(text: str) -> str:
    """Keep bridge HUD text readable by collapsing whitespace and clamping length."""
    compact = re.sub(r"\s+", " ", (text or "").strip().strip('"'))
    if len(compact) <= MAX_REPLY_CHARS:
        return compact
    clipped = compact[:MAX_REPLY_CHARS - 3].rstrip()
    boundary = max(clipped.rfind("."), clipped.rfind("!"), clipped.rfind("?"), clipped.rfind(";"))
    if boundary >= 80:
        clipped = clipped[:boundary + 1]
    return clipped.rstrip() + "..."


# ---------------------------------------------------------------------------
# Voice (C4 / R2 — mic ASR via llm-play voice_pipeline, then stdin / env fallback)
# ---------------------------------------------------------------------------
def _llm_play_root() -> Path:
    env = os.environ.get("LLM_PLAY_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_LLM_PLAY_DIR.expanduser().resolve()


def _asr_from_mic() -> Optional[str]:
    """Mic → Whisper via llm-play ``voice_pipeline/asr.py``. Best-effort; never raises."""
    if os.environ.get("AGENT_OFFICE_ASR", "1").strip().lower() in ("0", "false", "no", "off"):
        return None
    # Prefer an explicit WAV (tests / Kit push-to-talk dump) before live mic.
    wav_env = os.environ.get("AGENT_OFFICE_ASR_WAV", "").strip()
    root = _llm_play_root()
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    try:
        from voice_pipeline.asr import ASRUnavailable, listen_and_transcribe, transcribe  # type: ignore
    except Exception as exc:  # noqa: BLE001
        print(f"[asr] voice_pipeline import failed: {exc}")
        return None
    try:
        if wav_env:
            text = transcribe(Path(wav_env))
            cleaned = " ".join((text or "").split()).strip()
            if cleaned:
                print(f"[asr] wav→ {cleaned}")
            return cleaned or None
        text = listen_and_transcribe()
        if text:
            print(f"[asr] mic→ {text}")
        return text
    except ASRUnavailable as exc:
        print(f"[asr] unavailable: {exc}")
        return None
    except Exception as exc:  # noqa: BLE001 — ASR must never break engage
        print(f"[asr] failed: {exc}")
        return None


def listen_player() -> Optional[str]:
    """Return a player utterance for the current engagement.

    Priority:
    1. ``AGENT_OFFICE_UTTERANCE`` env (one-shot scripts / Kit)
    2. Mic → Whisper ASR (``voice_pipeline/asr.py``; ``AGENT_OFFICE_ASR_WAV`` or live mic)
    3. Non-blocking stdin line when ``AGENT_OFFICE_STDIN=1``
    4. None → brain uses the approach opener (HUD still works)
    """
    env_line = os.environ.get("AGENT_OFFICE_UTTERANCE", "").strip()
    if env_line:
        return env_line
    asr_line = _asr_from_mic()
    if asr_line:
        return asr_line
    if os.environ.get("AGENT_OFFICE_STDIN", "").strip() not in ("1", "true", "yes", "on"):
        return None
    if sys.stdin is None or not sys.stdin.isatty():
        return None
    try:
        print("you> ", end="", flush=True)
        line = sys.stdin.readline()
    except OSError:
        return None
    return line.strip() or None


def speak(voice_slug: str, text: str) -> None:
    """Best-effort character TTS. Prefer Office Service spatial_tts; else macOS say."""
    cleaned = (text or "").strip()
    if not cleaned:
        return
    try:
        from service.spatial_tts import (  # noqa: WPS433
            macos_say_fallback_enabled,
            spatial_tts_enabled,
            try_macos_say_async,
        )

        if spatial_tts_enabled() and macos_say_fallback_enabled():
            if try_macos_say_async(cleaned):
                return
    except Exception as exc:  # noqa: BLE001 — voice must never break engage
        print(f"[speak] spatial_tts fallback skipped: {exc}")
    if os.environ.get("AGENT_OFFICE_DIRECTOR_SAY", "").strip() in ("1", "true", "yes", "on"):
        if sys.platform == "darwin":
            try:
                import subprocess

                subprocess.Popen(
                    ["say", cleaned],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=False,
                    start_new_session=True,
                )
            except OSError as exc:
                print(f"[speak] macos say failed: {exc}")
    _ = voice_slug


# ---------------------------------------------------------------------------
# Director
# ---------------------------------------------------------------------------
@dataclass
class Engagement:
    chrnum: int
    engaged: bool = False
    presence_seeded: bool = False


class OfficeDirector:
    def __init__(
        self,
        brains: dict[str, AgentBrain],
        client: Optional[BridgeClient],
        service: Optional[Any] = None,
        role_ids: Optional[dict[str, str]] = None,
        input_provider: InputProvider = listen_player,
        repo_root: Path | str | None = None,
    ) -> None:
        self.brains = brains          # role -> brain
        self.client = client
        self.state: dict[int, Engagement] = {}
        # C3: optional Office Service — engaging an agent dispatches a Task into the
        # control plane (VISION §6). role_ids maps a role ("Ops") to a service agent id.
        self.service = service
        self.role_ids = {**ROLE_TO_AGENT_ID, **(role_ids or {})}
        self.repo_root = Path(repo_root) if repo_root else REPO_ROOT
        self.last_task: dict[str, str] = {}   # role -> last dispatched task id
        self.input_provider = input_provider
        self._seen_rumor_ids: set[str] = set()

    @staticmethod
    def _office_for_stage(stage: Any) -> str:
        try:
            st_int = int(stage)
            if st_int == 132:  # 0x84 Carrington Institute
                return "ci"
        except (TypeError, ValueError):
            pass
        return "g5"

    def _agent_billboard(self, role: str) -> Optional[str]:
        """Project live OfficeService task/approval or attached Antigravity live agent state into a compact in-world billboard."""
        if self.service is None or not hasattr(self.service, "agent_monitor"):
            return None
        aid = self.role_ids.get(role)
        if not aid:
            return None
        try:
            mon = self.service.agent_monitor(aid)
        except KeyError:
            return None
        pending = int(mon.get("pending_approvals") or 0)
        cur = mon.get("current_task")
        attached = mon.get("antigravity_live_agent")
        state = str(mon.get("state") or "idle")
        if pending > 0:
            return f"{role}: {state} ({pending} approval pending)"
        if isinstance(cur, dict) and cur.get("intent"):
            return f"{role}: {state} — {str(cur['intent'])[:48]}"
        if isinstance(attached, dict) and attached.get("billboard"):
            return str(attached["billboard"])
        return None

    def _post_act(self, act: dict[str, Any]) -> None:
        if not self.client:
            return
        try:
            self.client.act(act)
        except Exception as e:  # noqa: BLE001
            print(f"[act failed] {e}")

    def _presence_act(
        self,
        chrnum: int,
        status: str,
        *,
        face_player: bool = False,
        role: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build an /act payload that sets office presence (work/idle/talk) + optional billboard."""
        body: dict[str, Any] = {"chrnum": chrnum, "status": status}
        if face_player:
            body["face_player"] = True
        if role:
            billboard = self._agent_billboard(role)
            if billboard:
                body["billboard"] = billboard
        return {"agents": [body]}

    def _tick_social_bus(self, obs: dict[str, Any], agents: list[AgentView]) -> list[dict[str, Any]]:
        """R7 live background ticker: route cross-office rumors/guard reports to floor agents."""
        acts: list[dict[str, Any]] = []
        if self.service is None or not hasattr(self.service, "social"):
            return acts
        office_key = self._office_for_stage(obs.get("stage"))
        role_to_chrnum = {ag.role: ag.chrnum for ag in agents}
        feed_items = getattr(self.service.social, "_feed", [])
        for rumor in list(feed_items):
            if rumor.id in self._seen_rumor_ids:
                continue
            if rumor.to_office != office_key:
                continue
            self._seen_rumor_ids.add(rumor.id)
            target_role = None
            if rumor.to_agent_id:
                target_role = AGENT_ID_TO_ROLE_NAME.get(rumor.to_agent_id.lower())
            if not target_role:
                target_role = {
                    "guard_report": "Security",
                    "handoff": "Director",
                    "rumor": "Comms",
                }.get(rumor.kind, "Comms")
            brain = self.brains.get(target_role)
            if brain is not None:
                brain.ingest_rumor(rumor.kind, rumor.from_office, rumor.text)
            chrnum = role_to_chrnum.get(target_role)
            if chrnum is not None:
                act = {
                    "agents": [{
                        "chrnum": chrnum,
                        "status": "talk",
                        "say": _compact_reply(f"[{rumor.kind.upper()}] {rumor.text}"),
                        "billboard": f"R7 {rumor.from_office.upper()}->{rumor.to_office.upper()}: {rumor.text[:60]}",
                    }]
                }
                acts.append(act)
                self._post_act(act)
        return acts

    def _persist_proximity_dm(
        self,
        role: str,
        human_text: Optional[str],
        agent_reply: str,
    ) -> None:
        """Append proximity engage lines to the shared dm_threads sidecar (Pass 9)."""
        aid = self.role_ids.get(role)
        if not aid or not agent_reply.strip():
            return
        try:
            from service.dm_threads import (  # noqa: WPS433 — optional Office Service seam
                DmThreadAppendStatus,
                dm_thread_append_outcome,
            )

            utterance = (human_text or "").strip() or "[proximity approach]"
            human_outcome = dm_thread_append_outcome(
                aid,
                from_role="human",
                text=utterance,
                repo_root=str(self.repo_root),
                stub_reply=False,
            )
            if human_outcome.status != DmThreadAppendStatus.APPENDED:
                print(f"[dm append skipped] {role}: {human_outcome.status}")
                return
            agent_outcome = dm_thread_append_outcome(
                aid,
                from_role="agent",
                text=agent_reply.strip(),
                repo_root=str(self.repo_root),
                stub_reply=False,
            )
            if agent_outcome.status != DmThreadAppendStatus.APPENDED:
                print(f"[dm agent line skipped] {role}: {agent_outcome.status}")
        except Exception as e:  # noqa: BLE001 — DM persistence must not break engage loop
            print(f"[dm append failed] {role}: {e}")

    def step(self, obs: dict[str, Any]) -> list[dict[str, Any]]:
        """One perceive→engage→act cycle. Returns act payloads (also POSTed if live)."""
        player, agents = parse_observation(obs)
        acts: list[dict[str, Any]] = []
        acts.extend(self._tick_social_bus(obs, agents))
        if not player:
            return acts
        for ag in agents:
            st = self.state.setdefault(ag.chrnum, Engagement(ag.chrnum))
            # R1: seed ambient typing/work once so the floor reads as occupied.
            if not st.presence_seeded and not st.engaged:
                st.presence_seeded = True
                work = self._presence_act(ag.chrnum, "work", role=ag.role)
                acts.append(work)
                self._post_act(work)
            near = ag.player_dist < ENGAGE_RANGE
            far = ag.player_dist > DISENGAGE_RANGE
            if near and not st.engaged:
                st.engaged = True
                # Interrupt work: turn to face the visitor before speaking.
                talk = self._presence_act(ag.chrnum, "talk", face_player=True, role=ag.role)
                acts.append(talk)
                self._post_act(talk)
                brain = self.brains.get(ag.role)
                if brain:
                    said = self.input_provider()
                    line = brain.respond(said)
                    speak(brain.voice_slug, line)
                    agent_act_body: dict[str, Any] = {
                        "chrnum": ag.chrnum,
                        "say": line,
                        "face_player": True,
                        "status": "talk",
                    }
                    billboard = self._agent_billboard(ag.role)
                    if billboard:
                        agent_act_body["billboard"] = billboard
                    act = {"agents": [agent_act_body]}
                    acts.append(act)
                    self._post_act(act)
                    # Pass 9: share proximity engage with Z-target DM threads.
                    self._persist_proximity_dm(ag.role, said, line)
                    # C3: turn the engagement into a control-plane Task.
                    if self.service is not None:
                        aid = self.role_ids.get(ag.role)
                        if aid:
                            intent = said or "greet: player approached"
                            context = {
                                "role": ag.role,
                                "chrnum": ag.chrnum,
                                "player_dist": ag.player_dist,
                                "agent_reply": line,
                            }
                            try:
                                task = self.service.dispatch(
                                    aid, intent, context=context, created_by="human"
                                )
                                self.last_task[ag.role] = task.id
                            except Exception as e:  # noqa: BLE001
                                print(f"[dispatch failed] {e}")
                    print(f"→ {ag.role} ({ag.player_dist:.0f}u): {line}")
            elif far and st.engaged:
                st.engaged = False
                # Resume typing at the desk once the visitor leaves.
                work = self._presence_act(ag.chrnum, "work", role=ag.role)
                acts.append(work)
                self._post_act(work)
                print(f"· left {ag.role} — back to work")
        return acts

    def run(self, poll: float = 1.0 / TICK_HZ) -> None:
        assert self.client, "run() needs a live bridge; use step() for dry runs"
        print("Office Director live. Walk up to an agent…")
        while True:
            try:
                self.step(self.client.observe())
            except Exception as e:  # noqa: BLE001
                print(f"[observe failed] {e}")
            time.sleep(poll)


# ---------------------------------------------------------------------------
# Loading + CLI
# ---------------------------------------------------------------------------
def make_llm_backend(name: str, llm_play_dir: Optional[Path] = None) -> BrainBackend:
    """Load llm-play's backend factory from the sibling project on demand."""
    root = (llm_play_dir or DEFAULT_LLM_PLAY_DIR).expanduser().resolve()
    if not root.exists():
        raise RuntimeError(f"llm-play project not found at {root}")
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    from game_llm.engine.orchestrator import choose_backend  # type: ignore

    return choose_backend(name)


def load_brains(
    chars_dir: Path,
    *,
    backend: Optional[BrainBackend] = None,
    repo_root: Path = REPO_ROOT,
    persist_memory: bool = True,
    account_pool: Optional[Any] = None,
    tenant_id: Optional[str] = None,
) -> dict[str, AgentBrain]:
    brains: dict[str, AgentBrain] = {}
    for bj in sorted(chars_dir.glob("*/brain.json")):
        profile = json.loads(bj.read_text())
        brains[profile.get("role", profile["slug"])] = AgentBrain(
            profile,
            backend=backend,
            repo_root=repo_root,
            persist_memory=persist_memory,
            account_pool=account_pool,
            tenant_id=tenant_id,
        )
    return brains


DRY_FIXTURE = {
    "tick": 1200, "stage": 131,
    "players": [{"id": 0, "team": 0, "pos": {"x": 2600.0, "y": 35.0, "z": -300.0}, "facing_deg": 119.0}],
    "agents": [
        {"chrnum": 0x36, "role": "Security", "role_hint": 5,
         "pos": {"x": 2294.0, "y": 50.0, "z": -192.0},
         "facing_deg": 20.0, "player_dist": 360.0, "status": "work", "talking": False},
        {"chrnum": 0x31, "role": "Director", "role_hint": 0,
         "pos": {"x": 2888.0, "y": 35.0, "z": -458.0},
         "facing_deg": 270.0, "player_dist": 340.0, "status": "work", "talking": False},
    ],
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Virtual Agent Office — LLM conversation director")
    ap.add_argument("--url", default=None, help="bridge URL, e.g. http://127.0.0.1:8780")
    ap.add_argument("--dry-run", action="store_true", help="run one cycle against a bundled fixture")
    ap.add_argument("--characters", default=None, help="characters dir (default: ./characters)")
    ap.add_argument("--llm", action="store_true", help="use llm-play's local backend for brain replies")
    ap.add_argument("--backend", default="auto", help="llm-play backend: auto, ollama, or mlx")
    ap.add_argument("--llm-play-dir", default=None, help=f"llm-play project dir (default: {DEFAULT_LLM_PLAY_DIR})")
    ap.add_argument("--utterance", default=None, help="text input fallback for the current engagement")
    ap.add_argument("--persist-memory", action="store_true", help="persist character memory during dry-run")
    args = ap.parse_args()

    dry_mode = bool(args.dry_run or not args.url)
    chars_dir = Path(args.characters) if args.characters else Path(__file__).parent / "characters"
    backend = None
    account_pool = None
    if args.llm:
        backend = make_llm_backend(
            args.backend,
            Path(args.llm_play_dir) if args.llm_play_dir else None,
        )
        print(f"LLM enabled: {backend.name}")

    # Pass 4: optional account pool — disabled unless AGENT_OFFICE_ACCOUNT_POOL=1.
    if os.environ.get("AGENT_OFFICE_ACCOUNT_POOL", "").strip():
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from service.account_pool import bootstrap_llm_pool_from_env  # noqa: WPS433

        account_pool = bootstrap_llm_pool_from_env(run_id="director-cli")
        if account_pool is not None:
            print(f"Account pool enabled: {account_pool.pool_id}")
        else:
            print("[account pool] AGENT_OFFICE_ACCOUNT_POOL set but no credentials discovered")

    brains = load_brains(
        chars_dir,
        backend=backend,
        persist_memory=(args.persist_memory or not dry_mode),
        account_pool=account_pool,
    )
    print(f"Loaded {len(brains)} brain(s): {', '.join(brains) or '(none — add characters/<slug>/brain.json)'}")
    input_provider: InputProvider = (lambda: args.utterance) if args.utterance is not None else listen_player

    if dry_mode:
        director = OfficeDirector(brains, client=None, input_provider=input_provider)
        acts = director.step(DRY_FIXTURE)
        print(f"\nDry run produced {len(acts)} act payload(s):")
        for a in acts:
            print("  " + json.dumps(a))
        if not args.dry_run and not args.url:
            print("\n(no --url given; ran dry. Pass --url once the engine bridge is extended.)")
        return

    OfficeDirector(brains, BridgeClient(args.url), input_provider=input_provider).run()


if __name__ == "__main__":
    main()
