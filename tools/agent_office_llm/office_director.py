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

What works now: perception parsing, proximity engine with hysteresis + view-cone,
per-agent live-brain dispatch via llm-play backends, Office Service task dispatch,
and act payload construction. What's still stubbed (clearly marked TODO): voice
in/out (§4.3/§4.5).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

# Must match tools/pdmap/agent_office.py CHR_AGENT_FIRST and GREET_RANGE.
CHR_AGENT_FIRST = 0x31
ENGAGE_RANGE = 400.0     # start a conversation inside this (world units)
DISENGAGE_RANGE = 650.0  # end it past this (hysteresis so it doesn't flicker)
VIEW_CONE_DOT = 0.5      # player must be facing the agent (cos ~60°)
TICK_HZ = 6.0

# Role order matches VIRTUAL_AGENTS in tools/pdmap/agent_office.py (chrnum = base+offset).
ROLE_ORDER = ["Director", "Orchestrator", "Research", "Code", "QA", "Security", "Ops", "Comms"]
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
# Perception
# ---------------------------------------------------------------------------
@dataclass
class AgentView:
    chrnum: int
    role: str
    pos: tuple[float, float, float]
    facing_deg: float
    player_dist: float


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
            role = a.get("role") or _role_for(chrnum)
            p = a["pos"]
            agents.append(
                AgentView(
                    chrnum=chrnum,
                    role=role,
                    pos=(p["x"], p["y"], p["z"]),
                    facing_deg=float(a.get("facing_deg", 0.0)),
                    player_dist=float(a.get("player_dist", _dist(player, p) if player else 1e9)),
                )
            )
    else:
        # Fallback: office agents not yet in observe — scan actors[] by chrnum.
        for a in obs.get("actors", []):
            cid = int(a.get("id", -1))
            if cid >= CHR_AGENT_FIRST and a.get("kind") not in ("player", "bot"):
                p = a["pos"]
                agents.append(
                    AgentView(cid, _role_for(cid), (p["x"], p["y"], p["z"]),
                              float(a.get("facing_deg", 0.0)),
                              _dist(player, p) if player else 1e9)
                )
    return player, agents


def _role_for(chrnum: int) -> str:
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
    ) -> None:
        self.slug = profile["slug"]
        self.role = profile.get("role", self.slug)
        self.system_prompt = profile.get("system_prompt", "")
        self.voice_slug = profile.get("voice_slug", self.slug)
        self.knowledge = profile.get("knowledge", {})
        self.backend = backend
        self.max_memory_turns = max_memory_turns
        self.persist_memory = persist_memory
        self.memory_file = self._resolve_memory_file(profile.get("memory_file"), repo_root)
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
                raw = self.backend.generate(self._system_prompt(), self._user_prompt(player_text))
                line = self._extract_reply(raw)
            except Exception as e:  # noqa: BLE001 - live brain failures fall back visibly in logs
                print(f"[brain failed] {self.role}: {e}")
                line = self._scripted_reply(player_text)
        else:
            line = self._scripted_reply(player_text)

        self._remember(player_text or "[approach]", line)
        return line

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

    def _resolve_memory_file(self, value: Optional[str], repo_root: Path) -> Optional[Path]:
        if not value:
            return None
        path = Path(value)
        return path if path.is_absolute() else repo_root / path

    def _load_memory(self) -> list[tuple[str, str]]:
        """Load the recent Markdown memory tail; corrupt or absent files simply start empty."""
        if not self.persist_memory or self.memory_file is None or not self.memory_file.exists():
            return []
        turns: list[tuple[str, str]] = []
        try:
            for line in self.memory_file.read_text(encoding="utf-8").splitlines()[-24:]:
                match = re.match(r"- (player|agent): (.*)", line.strip(), re.IGNORECASE)
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
# Voice (stubs — wire to voice_pipeline/, spec §4.3 / §4.5)
# ---------------------------------------------------------------------------
def listen_player() -> Optional[str]:
    # TODO(C4): voice_pipeline/asr.py Whisper transcript, or stdin fallback.
    return None


def speak(voice_slug: str, text: str) -> None:
    # TODO(C4): voice_pipeline TTS for voice_slug, gated by asr.py intelligibility.
    pass


# ---------------------------------------------------------------------------
# Director
# ---------------------------------------------------------------------------
@dataclass
class Engagement:
    chrnum: int
    engaged: bool = False


class OfficeDirector:
    def __init__(
        self,
        brains: dict[str, AgentBrain],
        client: Optional[BridgeClient],
        service: Optional[Any] = None,
        role_ids: Optional[dict[str, str]] = None,
        input_provider: InputProvider = listen_player,
    ) -> None:
        self.brains = brains          # role -> brain
        self.client = client
        self.state: dict[int, Engagement] = {}
        # C3: optional Office Service — engaging an agent dispatches a Task into the
        # control plane (VISION §6). role_ids maps a role ("Ops") to a service agent id.
        self.service = service
        self.role_ids = role_ids or {}
        self.last_task: dict[str, str] = {}   # role -> last dispatched task id
        self.input_provider = input_provider

    def step(self, obs: dict[str, Any]) -> list[dict[str, Any]]:
        """One perceive→engage→act cycle. Returns act payloads (also POSTed if live)."""
        player, agents = parse_observation(obs)
        acts: list[dict[str, Any]] = []
        if not player:
            return acts
        for ag in agents:
            st = self.state.setdefault(ag.chrnum, Engagement(ag.chrnum))
            near = ag.player_dist < ENGAGE_RANGE and player_faces(player, ag)
            far = ag.player_dist > DISENGAGE_RANGE
            if near and not st.engaged:
                st.engaged = True
                brain = self.brains.get(ag.role)
                if brain:
                    said = self.input_provider()
                    line = brain.respond(said)
                    speak(brain.voice_slug, line)
                    act = {"agents": [{"chrnum": ag.chrnum, "say": line, "face_player": True}]}
                    acts.append(act)
                    if self.client:
                        try:
                            self.client.act(act)
                        except Exception as e:  # noqa: BLE001
                            print(f"[act failed] {e}")
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
                print(f"· left {ag.role}")
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
) -> dict[str, AgentBrain]:
    brains: dict[str, AgentBrain] = {}
    for bj in sorted(chars_dir.glob("*/brain.json")):
        profile = json.loads(bj.read_text())
        brains[profile.get("role", profile["slug"])] = AgentBrain(
            profile, backend=backend, repo_root=repo_root, persist_memory=persist_memory
        )
    return brains


DRY_FIXTURE = {
    "tick": 1200, "stage": 131,
    "players": [{"id": 0, "team": 0, "pos": {"x": 2600.0, "y": 35.0, "z": -300.0}, "facing_deg": 119.0}],
    "agents": [
        {"chrnum": 0x36, "role": "Security", "pos": {"x": 2294.0, "y": 50.0, "z": -192.0},
         "facing_deg": 20.0, "player_dist": 360.0},
        {"chrnum": 0x31, "role": "Director", "pos": {"x": 2888.0, "y": 35.0, "z": -458.0},
         "facing_deg": 270.0, "player_dist": 340.0},
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
    if args.llm:
        backend = make_llm_backend(
            args.backend,
            Path(args.llm_play_dir) if args.llm_play_dir else None,
        )
        print(f"LLM enabled: {backend.name}")

    brains = load_brains(chars_dir, backend=backend, persist_memory=(args.persist_memory or not dry_mode))
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
