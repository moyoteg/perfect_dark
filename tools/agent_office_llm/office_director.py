#!/usr/bin/env python3
"""Office Director — proximity-driven, per-character LLM conversation for the
Virtual Agent Office.

SCAFFOLD (phase C0/C1/C2). This is deliberately dependency-light and runnable:

    # Dry run against a bundled fixture (no game needed) — proves the proximity
    # + brain + dispatch wiring end to end:
    python3 tools/agent_office_llm/office_director.py --dry-run

    # Live, once the engine emits observe.agents[] and accepts act.agents[].say
    # (see journal/agent_office/LLM_CONVERSATION_LAYER.md §3):
    python3 tools/agent_office_llm/office_director.py --url http://127.0.0.1:8780

What works now: perception parsing, proximity engine with hysteresis + view-cone,
per-agent brain dispatch, and act payload construction. What's stubbed (clearly
marked TODO): the /observe agents[] pass (engine §3a), act injection (§3b), the
real LLM brain (§4.4), and voice in/out (§4.3/§4.5).
"""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# Must match tools/pdmap/agent_office.py CHR_AGENT_FIRST and GREET_RANGE.
CHR_AGENT_FIRST = 0x31
ENGAGE_RANGE = 400.0     # start a conversation inside this (world units)
DISENGAGE_RANGE = 650.0  # end it past this (hysteresis so it doesn't flicker)
VIEW_CONE_DOT = 0.5      # player must be facing the agent (cos ~60°)
TICK_HZ = 6.0

# Role order matches VIRTUAL_AGENTS in tools/pdmap/agent_office.py (chrnum = base+offset).
ROLE_ORDER = ["Director", "Orchestrator", "Research", "Code", "QA", "Security", "Ops", "Comms"]


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

    def __init__(self, profile: dict[str, Any]) -> None:
        self.slug = profile["slug"]
        self.role = profile.get("role", self.slug)
        self.system_prompt = profile.get("system_prompt", "")
        self.voice_slug = profile.get("voice_slug", self.slug)
        self.memory: list[str] = []

    def respond(self, player_said: Optional[str]) -> str:
        """Return one in-character line.

        C2 scaffold: canned. C3: swap for an llm-play AdapterOrchestrator call
        (system_prompt + rolling self.memory + player_said). See spec §4.4.
        """
        # TODO(C3): backend = OllamaBackend(); return backend.generate(self.system_prompt, prompt)
        opener = profile_opener(self.role)
        if player_said:
            self.memory.append(f"player: {player_said}")
            return f"{opener} (You said: {player_said!r}. — brain stub)"
        return opener


def profile_opener(role: str) -> str:
    return {
        "Director": "Stand-up's running long. What do you need?",
        "Research": "I'm mid-index — 847 files deep. Ask quickly.",
        "Security": "Badge checks out. Keep it moving.",
        "Ops": "Pipeline's green. Don't touch the deploy.",
    }.get(role, f"[{role}] …yes?")


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
    def __init__(self, brains: dict[str, AgentBrain], client: Optional[BridgeClient]) -> None:
        self.brains = brains          # role -> brain
        self.client = client
        self.state: dict[int, Engagement] = {}

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
                    said = listen_player()
                    line = brain.respond(said)
                    speak(brain.voice_slug, line)
                    act = {"agents": [{"chrnum": ag.chrnum, "say": line, "face_player": True}]}
                    acts.append(act)
                    if self.client:
                        try:
                            self.client.act(act)
                        except Exception as e:  # noqa: BLE001
                            print(f"[act failed] {e}")
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
def load_brains(chars_dir: Path) -> dict[str, AgentBrain]:
    brains: dict[str, AgentBrain] = {}
    for bj in sorted(chars_dir.glob("*/brain.json")):
        profile = json.loads(bj.read_text())
        brains[profile.get("role", profile["slug"])] = AgentBrain(profile)
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
    args = ap.parse_args()

    chars_dir = Path(args.characters) if args.characters else Path(__file__).parent / "characters"
    brains = load_brains(chars_dir)
    print(f"Loaded {len(brains)} brain(s): {', '.join(brains) or '(none — add characters/<slug>/brain.json)'}")

    if args.dry_run or not args.url:
        director = OfficeDirector(brains, client=None)
        acts = director.step(DRY_FIXTURE)
        print(f"\nDry run produced {len(acts)} act payload(s):")
        for a in acts:
            print("  " + json.dumps(a))
        if not args.dry_run and not args.url:
            print("\n(no --url given; ran dry. Pass --url once the engine bridge is extended.)")
        return

    OfficeDirector(brains, BridgeClient(args.url)).run()


if __name__ == "__main__":
    main()
