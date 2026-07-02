"""Progressive learn-curriculum maps — one tiny test map per verified topic.

Each step is deterministic JSON → level module → validate → optional deploy-as uff.
Regenerate with ``pdmap learn curriculum generate``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from ..core import ROOT
from ..from_json import EditorMapSpec, validate_level_name
from ..level_codegen import render_level_module
from ..pipeline import build_from_spec
from ..validate import validate_mapdef

LEARN_DIR = os.path.join(ROOT, "journal", "map_learn")
MAPS_DIR = os.path.join(LEARN_DIR, "maps")
LEVELS_DIR = os.path.join(ROOT, "src", "levels")
CURRICULUM_MD = os.path.join(LEARN_DIR, "CURRICULUM.md")

# Shared box arena defaults (collision from tiles; seg optional / empty mode).
_BOX_SMALL: dict[str, float] = {"box_half": 2500, "box_height": 2000}
_BOX_LARGE: dict[str, float] = {"box_half": 5000, "box_height": 3000}


def _spawn(idx: int, x: float, z: float, *, y: float = 10) -> dict[str, Any]:
    return {"index": idx, "type": "spawn", "x": x, "y": y, "z": z, "room": 1}


def _weapon(idx: int, x: float, z: float, weapon: int) -> dict[str, Any]:
    return {"index": idx, "type": "weapon", "x": x, "y": 10, "z": z, "room": 1, "weapon": weapon}


def _ammo(idx: int, x: float, z: float, ammo_type: int, quantity: int = 200) -> dict[str, Any]:
    return {
        "index": idx,
        "type": "ammo",
        "x": x,
        "y": 10,
        "z": z,
        "room": 1,
        "ammoType": ammo_type,
        "quantity": quantity,
    }


def _scenario(idx: int, x: float, z: float, scenario: str, team: int = 0, *, room: int = 1) -> dict[str, Any]:
    return {
        "index": idx,
        "type": "scenario",
        "x": x,
        "y": 10,
        "z": z,
        "room": room,
        "scenario": scenario,
        "team": team,
    }


@dataclass(frozen=True)
class CurriculumStep:
    """One curriculum step: JSON spec + player-facing metadata."""

    step: int
    slug: str  # e.g. "spawn" → learn_01_spawn
    title: str
    tests: str
    expected: str
    scenario: int  # pd --scenario-N (0=combat, 4=hill, 5=ctf)
    seg_mode: str = "empty"  # PDMAP_SEG_MODE for validate / play-learn-step
    fact_tags: tuple[str, ...] = ()
    seg_script_basename: str | None = None  # optional SEG_SCRIPT under scripts/
    covers: tuple[tuple[float, float], ...] = ()  # (x, z) AI cover points
    json_body: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return f"learn_{self.step:02d}_{self.slug}"

    @property
    def json_path(self) -> str:
        return os.path.join(MAPS_DIR, f"{self.name}.json")

    @property
    def level_path(self) -> str:
        return os.path.join(LEVELS_DIR, f"{self.name}.py")

    def full_json(self) -> dict[str, Any]:
        body = dict(self.json_body)
        body["name"] = self.name
        if self.covers and "covers" not in body:
            body["covers"] = [{"x": x, "z": z} for x, z in self.covers]
        return body


def _curriculum_registry() -> list[CurriculumStep]:
    """Ordered steps — each adds one concept on top of prior knowledge."""
    s = 1500.0
    return [
        CurriculumStep(
            step=1,
            slug="spawn",
            title="Single spawn (Y=10)",
            tests="Spawn pad above floor; empty box arena; pad indices 0..N-1",
            expected="Player spawns at center, stands on flat floor, no fall-through.",
            scenario=0,
            fact_tags=("pads", "collision", "tiles"),
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, 0, 0)],
            },
        ),
        CurriculumStep(
            step=2,
            slug="four_spawns",
            title="Four corner spawns",
            tests="Multiple Spawn intro commands; contiguous pad indices",
            expected="Quick-team places up to four players at corners (±1500).",
            scenario=0,
            fact_tags=("pads", "mkpads"),
            json_body={
                **_BOX_SMALL,
                "pads": [
                    _spawn(0, -s, -s),
                    _spawn(1, s, -s),
                    _spawn(2, -s, s),
                    _spawn(3, s, s),
                ],
            },
        ),
        CurriculumStep(
            step=3,
            slug="weapon",
            title="Floor weapon pickup",
            tests="Weapon pad + add_floor_weapons; weaponnum id on pad",
            expected="CMP150 (or configured weapon) visible at map center; pickup works.",
            scenario=0,
            fact_tags=("intro", "loadout"),
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, 0, -s), _weapon(1, 0, 0, 10)],  # WEAPON_CMP150=0x0A
            },
        ),
        CurriculumStep(
            step=4,
            slug="ammo",
            title="Ammo crate",
            tests="Ammo pad + add_ammo_row; ammoType quantity",
            expected="Ammo crate at +X; picking up refills matching ammo type.",
            scenario=0,
            fact_tags=("intro", "loadout"),
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, 0, 0), _ammo(1, s, 0, 3)],  # AMMOTYPE_RIFLE
            },
        ),
        CurriculumStep(
            step=5,
            slug="loadout",
            title="Loadout intro / ailist 0x1000",
            tests="add_loadout_intro; mp_init_simulants ailist id 0x1000",
            expected="Combat start: default loadout weapons (Falcon2, CMP150, …) in hand.",
            scenario=0,
            fact_tags=("bots", "setup", "intro"),
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, 0, 0)],
            },
        ),
        CurriculumStep(
            step=6,
            slug="waypoints",
            title="Symmetric waypoints / bot spawn",
            tests="Waypoint graph auto-generated from spawns; bidirectional edges",
            expected="Add 1–4 simulants in Combat Simulator; bots move without crashing.",
            scenario=0,
            fact_tags=("bots", "waypoints"),
            json_body={
                **_BOX_LARGE,
                "pads": [
                    _spawn(0, -2000, -2000),
                    _spawn(1, 2000, -2000),
                    _spawn(2, -2000, 2000),
                    _spawn(3, 2000, 2000),
                ],
            },
        ),
        CurriculumStep(
            step=7,
            slug="hill",
            title="King of the Hill anchor",
            tests="Hill scenario pad + intro Hill command",
            expected="Launch with --scenario-4; green hill zone at +Z with dark ring boundary; KOTH scoring only inside hill room.",
            scenario=4,
            fact_tags=("scenario", "hill_visual"),
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, 0, 0), _scenario(1, 0, 1500, "hill", room=2)],
            },
        ),
        CurriculumStep(
            step=8,
            slug="ctf_case",
            title="Case + CaseRespawn (CTF pair)",
            tests="Case/CaseRespawn team pairing; validate_mapdef CTF rules",
            expected=(
                "Launch with --scenario-5; briefcase at -Z, respawn at +Z (team 0). "
                "Bright red delivery square + dark ring at +Z (CaseRespawn); muted red "
                "marker at -Z (Case). Steal enemy case and touch home pad to score instantly. "
                "No hold countdown (that is --scenario-1 Hold Briefcase only)."
            ),
            scenario=5,
            fact_tags=("scenario", "ctf", "case_respawn", "ctf_visual"),
            json_body={
                **_BOX_SMALL,
                "pads": [
                    _spawn(0, 0, 0),
                    _scenario(1, 0, -500, "case", 0),
                    _scenario(2, 0, 500, "case_respawn", 0),
                ],
            },
        ),
        CurriculumStep(
            step=9,
            slug="deploy_uff",
            title="Deploy-as uff / --test-map slot",
            tests="STAGE_TEST_UFF boot via bg_uff.*; --test-map chrslots=0x01",
            expected="Same empty box; confirms play-learn-step deploys into uff test slot.",
            scenario=0,
            fact_tags=("test-map", "uff"),
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, 0, 0)],
            },
        ),
        CurriculumStep(
            step=10,
            slug="full_arena",
            title="Composite (my_arena-like)",
            tests="Spawns + weapons + ammo + CTF pair + hill in one map",
            expected="All features together: pickups, KOTH anchor, CTF pair, four spawns.",
            scenario=0,
            fact_tags=("level-module", "my_arena"),
            json_body={
                "box_half": 2500,
                "box_height": 2000,
                "pads": [
                    _spawn(0, -2000, -2000),
                    _spawn(1, 2000, -2000),
                    _spawn(2, -2000, 2000),
                    _spawn(3, 2000, 2000),
                    _weapon(4, 0, -1500, 0x11),
                    _weapon(5, 0, 1500, 0x13),
                    _ammo(6, 0, 0, 4),  # shotgun
                    _scenario(7, 0, -500, "case", 0),
                    _scenario(8, 0, 500, "case_respawn", 0),
                    _scenario(9, 500, 0, "hill", room=2),
                ],
            },
        ),
        CurriculumStep(
            step=11,
            slug="y_autocorrect",
            title="Pad Y auto-correction (Y=0 → 10)",
            tests="EditorMapSpec.from_json corrects Y<=0 to spawn_y",
            expected="Player still spawns safely despite JSON Y=0 on pad (pipeline fix).",
            scenario=0,
            fact_tags=("from-json", "validate"),
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, 0, 0, y=0)],
            },
        ),
        # --- Phase 2: engine / fixture / seg topics not covered by steps 1–11 ---
        CurriculumStep(
            step=12,
            slug="testarena_fixture",
            title="Registered testarena layout (minimal_map.json)",
            tests="Full 4-team CTF + hill; mirrors editor fixture and registered testarena module",
            expected=(
                "Launch with --scenario-5. Layout matches registered STAGE_TESTARENA / "
                "minimal_map.json fixture (four spawns, weapon, ammo, hill, 4× Case pairs). "
                "Combat Sim menu shows 'Test Arena' label (textid 0x7FFC) when played from menu — manual."
            ),
            scenario=5,
            seg_mode="ctf",
            fact_tags=("fixture", "minimal_map.json", "testarena", "env", "lang", "stagetable"),
            json_body={
                "box_half": 5000,
                "box_height": 3000,
                "pads": [
                    _spawn(0, -4000, -4000),
                    _spawn(1, 4000, -4000),
                    _spawn(2, -4000, 4000),
                    _spawn(3, 4000, 4000),
                    _weapon(4, 0, 0, 10),
                    _ammo(5, 1500, 0, 3),
                    _scenario(6, 0, 1500, "hill", room=2),
                    _scenario(7, -4200, -4200, "case", 0),
                    _scenario(8, -4200, -4000, "case_respawn", 0),
                    _scenario(9, 4200, -4200, "case", 1),
                    _scenario(10, 4200, -4000, "case_respawn", 1),
                    _scenario(11, -4200, 4200, "case", 2),
                    _scenario(12, -4200, 4000, "case_respawn", 2),
                    _scenario(13, 4200, 4200, "case", 3),
                    _scenario(14, 4200, 4000, "case_respawn", 3),
                ],
            },
        ),
        CurriculumStep(
            step=13,
            slug="fixture_compact",
            title="Compact fixture (minimal_map 2.json)",
            tests="Two spawns + weapon + ammo + hill; smaller box than testarena",
            expected="Launch with --scenario-4; hill at +Z; weapon/ammo pickups work in 5000 box.",
            scenario=4,
            seg_mode="hill",
            fact_tags=("fixture", "minimal_map 2.json"),
            json_body={
                "box_half": 5000,
                "box_height": 3000,
                "pads": [
                    _spawn(0, -2000, -2000),
                    _spawn(1, 2000, 2000),
                    _weapon(2, 0, 0, 10),
                    _ammo(3, 1500, 0, 4),
                    _scenario(4, 0, 1500, "hill", room=2),
                ],
            },
        ),
        CurriculumStep(
            step=14,
            slug="procedural_seg",
            title="Procedural box seg (PDMAP_SEG_MODE=full)",
            tests="BOX_HALF+BOX_HEIGHT → procedural box seg; no SEG_SCRIPT in module",
            expected=(
                "Build with --seg-mode full: visible box walls from procedural generator. "
                "Collision still from tiles; seg is visual. May show near-plane clip in FPS — "
                "contrast with step 15 empty mode."
            ),
            scenario=0,
            seg_mode="full",
            fact_tags=("pipeline", "seg", "box", "SEG_SCRIPT"),
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, 0, 0)],
            },
        ),
        CurriculumStep(
            step=15,
            slug="seg_empty",
            title="Empty seg mode (PDMAP_SEG_MODE=empty)",
            tests="Default empty seg avoids viewport near-plane sheet in FPS",
            expected="Launch with --seg-mode empty: no visible seg walls; flat grey floor from tiles only.",
            scenario=0,
            seg_mode="empty",
            fact_tags=("rendering", "seg"),
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, 0, 0)],
            },
        ),
        CurriculumStep(
            step=16,
            slug="my_arena_registered",
            title="Registered my_arena layout",
            tests="my_arena module pattern: 4 spawns, dual weapons, ammo, 4-team CTF, hill",
            expected=(
                "Launch with --scenario-5. Layout matches registered STAGE_MY_ARENA. "
                "Combat Sim menu shows 'My Arena' (textid 0x7FFD) when played from menu — manual."
            ),
            scenario=5,
            seg_mode="ctf",
            fact_tags=("lang", "my_arena", "env"),
            json_body={
                "box_half": 5000,
                "box_height": 3000,
                "pads": [
                    _spawn(0, -4000, -4000),
                    _spawn(1, 4000, -4000),
                    _spawn(2, -4000, 4000),
                    _spawn(3, 4000, 4000),
                    _weapon(4, 0, -1500, 0x11),
                    _weapon(5, 0, 1500, 0x13),
                    _ammo(6, -1500, 0, 3),
                    _ammo(7, 1500, 0, 4),
                    _scenario(8, -4200, -4200, "case", 0),
                    _scenario(9, -4200, -4000, "case_respawn", 0),
                    _scenario(10, 4200, -4200, "case", 1),
                    _scenario(11, 4200, -4000, "case_respawn", 1),
                    _scenario(12, -4200, 4200, "case", 2),
                    _scenario(13, -4200, 4000, "case_respawn", 2),
                    _scenario(14, 4200, 4200, "case", 3),
                    _scenario(15, 4200, 4000, "case_respawn", 3),
                    _scenario(16, 500, 0, "hill", room=2),
                ],
            },
        ),
        CurriculumStep(
            step=17,
            slug="from_json_cli",
            title="from-json CLI canonical path",
            tests="pdmap from-json is the canonical entry for deterministic box maps",
            expected="Same spawn box; validates via from-json → build_from_spec without level module edits.",
            scenario=0,
            fact_tags=("cli", "from-json"),
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, 0, 0)],
            },
        ),
        CurriculumStep(
            step=18,
            slug="register_scratch",
            title="Registration probe target (learn_scratch pattern)",
            tests="Minimal map for register --apply e2e dry-run / live probes",
            expected=(
                "Automated: pdmap register --apply learn_scratch dry-run passes (probe_register_apply_e2e). "
                "Live stage registration requires make rebuild — manual smoke only."
            ),
            scenario=0,
            fact_tags=("e2e", "live", "registration"),
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, 0, 0)],
            },
        ),
        # --- Phase 3: scenarios 1–3, overlaps, loadout namespace, bot cap ---
        CurriculumStep(
            step=19,
            slug="hold_briefcase",
            title="Hold the Briefcase (scenario 1)",
            tests="Two spawns; no Case intro — stock Hold scenario",
            expected=(
                "Launch with --scenario-1. Pick up briefcase; green 30s countdown while holding; "
                "score on timer expiry. No CTF Case/CaseRespawn pads required."
            ),
            scenario=1,
            fact_tags=("scenario", "hold"),
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, -s, 0), _spawn(1, s, 0)],
            },
        ),
        CurriculumStep(
            step=20,
            slug="overlap_pads",
            title="Cross-type pad overlap (spawn + weapon + ammo)",
            tests="Same XZ for spawn, weapon, ammo — editor allows cross-type overlap",
            expected=(
                "Launch with --scenario-0. Marker seg (grey floor, no walls): "
                "bright green centre square (~5 m) marks the overlap point. Player spawns "
                "on that square with AR34 pickup and shotgun ammo crate at the same spot — "
                "look down at your feet; all three function (stock uff pattern)."
            ),
            scenario=0,
            seg_mode="marker",
            fact_tags=("pads", "overlap"),
            json_body={
                **_BOX_SMALL,
                "center_marker": True,
                "pads": [
                    _spawn(0, 0, 0),
                    _weapon(1, 0, 0, 0x11),  # AR34 weaponnum
                    _ammo(2, 0, 0, 4),  # shotgun ammo
                ],
            },
        ),
        CurriculumStep(
            step=21,
            slug="hacker_central",
            title="Hacker Central (scenario 2)",
            tests="HTM bank pads (2× multi-ammo); floor pad up=+Y; download timer",
            expected=(
                "Launch with --scenario-2. Two multi-ammo crates feed the HTM bank; "
                "terminal (MODEL_GOODPC) stands upright on floor pads (up=+Y). Pick up "
                "Data Uplink, interact with terminal — download progress bar runs ~20s."
            ),
            scenario=2,
            fact_tags=("scenario", "hacker"),
            json_body={
                **_BOX_SMALL,
                "pads": [
                    _spawn(0, -s, 0),
                    _spawn(1, s, 0),
                    _ammo(2, 0, 0, 3),  # MODEL_MULTI_AMMO_CRATE — uplink/HTM bank pad
                    _ammo(3, 0, 500, 4),  # second HTM bank pad (terminal pool)
                ],
            },
        ),
        CurriculumStep(
            step=22,
            slug="pop_a_cap",
            title="Pop a Cap (scenario 3)",
            tests="Four spawns; Pop-a-Cap scoring",
            expected=(
                "Launch with --scenario-3. Solo (--num-sims 0): you are always the victim — "
                "green 1:00 countdown at top center is the survival timer (+1 point each "
                "minute alive; not match start, kill limit, or time limit). "
                "Pop-a-cap scoring works with spawns only — no special pads."
            ),
            scenario=3,
            fact_tags=("scenario", "pop_cap"),
            json_body={
                **_BOX_SMALL,
                "pads": [
                    _spawn(0, -s, -s),
                    _spawn(1, s, -s),
                    _spawn(2, -s, s),
                    _spawn(3, s, s),
                ],
            },
        ),
        CurriculumStep(
            step=23,
            slug="bot_four_cap",
            title="Bot count cap (stock 4 simulants)",
            tests="Large box + four spawns + waypoints; --num-sims 8",
            expected=(
                "Launch with --scenario-0 --num-sims 8. Only 4 bots spawn (stock MP cap without "
                "MPFEATURE_8BOTS). Bots pathfind without crash."
            ),
            scenario=0,
            fact_tags=("bots", "chrslots"),
            json_body={
                **_BOX_LARGE,
                "pads": [
                    _spawn(0, -2000, -2000),
                    _spawn(1, 2000, -2000),
                    _spawn(2, -2000, 2000),
                    _spawn(3, 2000, 2000),
                ],
            },
        ),
        CurriculumStep(
            step=24,
            slug="mpweapon_loadout",
            title="MPWEAPON CLI loadout namespace",
            tests="Single spawn; --loadout uses MPWEAPON ids not weaponnum",
            expected=(
                "Launch with --scenario-0 --loadout 1,9,16,4,0,37. Starting weapons: Falcon2, "
                "CMP150, AR34, MagSec4, empty, Shield (MPWEAPON space — distinct from floor "
                "weaponnum 0x11 for AR34 props in learn_03_weapon)."
            ),
            scenario=0,
            fact_tags=("intro", "loadout"),
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, 0, 0)],
            },
        ),
        CurriculumStep(
            step=25,
            slug="boot_stage",
            title="Boot registered stage (my_arena)",
            tests="Same layout as learn_16; boot via --boot-stage not --test-map",
            expected=(
                "Manual: build+deploy my_arena assets, then "
                "./build/pd.arm64 --boot-stage STAGE_MY_ARENA --skip-intro --moddir mods/mod_allinone "
                "--scenario-5. Loads bg_my_arena.* (not uff test slot)."
            ),
            scenario=5,
            seg_mode="ctf",
            fact_tags=("my_arena", "env", "stagetable"),
            json_body={
                "box_half": 5000,
                "box_height": 3000,
                "pads": [
                    _spawn(0, -4000, -4000),
                    _spawn(1, 4000, -4000),
                    _spawn(2, -4000, 4000),
                    _spawn(3, 4000, 4000),
                    _weapon(4, 0, -1500, 0x11),
                    _weapon(5, 0, 1500, 0x13),
                    _ammo(6, -1500, 0, 3),
                    _ammo(7, 1500, 0, 4),
                    _scenario(8, -4200, -4200, "case", 0),
                    _scenario(9, -4200, -4000, "case_respawn", 0),
                    _scenario(10, 4200, -4200, "case", 1),
                    _scenario(11, 4200, -4000, "case_respawn", 1),
                    _scenario(12, -4200, 4200, "case", 2),
                    _scenario(13, -4200, 4000, "case_respawn", 2),
                    _scenario(14, 4200, 4200, "case", 3),
                    _scenario(15, 4200, 4000, "case_respawn", 3),
                    _scenario(16, 500, 0, "hill", room=2),
                ],
            },
        ),
        CurriculumStep(
            step=26,
            slug="solo_ctf",
            title="Solo human CTF (no simulants)",
            tests="Minimal CTF pair; --num-sims 0",
            expected=(
                "Launch with --scenario-5 --num-sims 0. Human-only: pick up case at -Z, return to "
                "+Z CaseRespawn; instant score without bots."
            ),
            scenario=5,
            seg_mode="ctf",
            fact_tags=("scenario", "ctf", "case_respawn"),
            json_body={
                **_BOX_SMALL,
                "pads": [
                    _spawn(0, 0, 0),
                    _scenario(1, 0, -500, "case", 1),
                    _scenario(2, 0, 500, "case", 0),
                    _scenario(3, 0, 500, "case_respawn", 0),
                    _scenario(4, 0, -500, "case_respawn", 1),
                ],
            },
        ),
        CurriculumStep(
            step=27,
            slug="multi_weapon",
            title="Multiple floor weapons (weaponnum namespace)",
            tests="AR34, CMP150, shotgun at distinct pads; weaponnum ids 0x11, 0x0A, 0x13",
            expected=(
                "Launch with --scenario-0. Three floor pickups at -X, center, +X each grant "
                "the correct weapon (weaponnum space — contrast learn_24 MPWEAPON loadout)."
            ),
            scenario=0,
            fact_tags=("intro", "loadout"),
            json_body={
                **_BOX_SMALL,
                "pads": [
                    _spawn(0, 0, 0),
                    _weapon(1, -800, 0, 0x11),  # AR34
                    _weapon(2, 0, 0, 0x0A),  # CMP150
                    _weapon(3, 800, 0, 0x13),  # shotgun
                ],
            },
        ),
        CurriculumStep(
            step=28,
            slug="hill_collision",
            title="Hill room-1 collision mirror (no fall-through)",
            tests="Hill pad room=2; floor_box_with_hill_zone duplicates quad in room 1",
            expected=(
                "Launch with --scenario-4. Walk the dark ring boundary around the green hill "
                "square at +Z — floor solid everywhere; no void fall-through at hill edge."
            ),
            scenario=4,
            seg_mode="hill",
            fact_tags=("scenario", "hill_visual", "tiles"),
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, 0, 0), _scenario(1, 0, 1500, "hill", room=2)],
            },
        ),
        CurriculumStep(
            step=29,
            slug="custom_seg_script",
            title="Custom SEG_SCRIPT seg generator",
            tests="Level module sets SEG_SCRIPT; script writes bg_<name>.seg",
            expected=(
                "Build with level module SEG_SCRIPT (not procedural-only). Visible box seg "
                "from scripts/learn_29_seg_build.py; G_VTX loads ≤16; no relinkPtr crash. "
                "Walk to each coloured wall — solid perimeter collision (tiles), not seg geometry."
            ),
            scenario=0,
            seg_mode="full",
            fact_tags=("seg", "SEG_SCRIPT", "pipeline"),
            seg_script_basename="learn_29_seg_build.py",
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, 0, 0)],
            },
        ),
        CurriculumStep(
            step=30,
            slug="mod_hygiene",
            title="Deploy hygiene / external asset load",
            tests="from-json deploy-as uff; confirm mod_allinone bg_uff.* updated",
            expected=(
                "Launch with --scenario-0. stderr/log shows bg_uff tiles/pads/seg/setup "
                "'loaded externally' from mods/mod_allinone (not ROM embedded). Re-deploy "
                "after every edit — stale assets cause silent regressions."
            ),
            scenario=0,
            fact_tags=("deploy", "from-json", "e2e"),
            json_body={
                **_BOX_SMALL,
                "pads": [_spawn(0, 0, 0)],
            },
        ),
        CurriculumStep(
            step=31,
            slug="cover_points",
            title="AI cover points (add_cover)",
            tests="MapDef.add_cover emits cover JSON in pads pack; bots may use cover",
            expected=(
                "Launch with --scenario-0 --num-sims 2. Two cover points at X=±800; "
                "bright green floor squares (~5 m) with dark rings mark each cover pad "
                "(same style as step 20 centre marker). Bots spawn at ±X=2000 and "
                "pathfind; cover behaviour is AI-only — markers are visual only."
            ),
            scenario=0,
            seg_mode="marker",
            fact_tags=("bots", "waypoints"),
            covers=((-800.0, 0.0), (800.0, 0.0)),
            json_body={
                **_BOX_LARGE,
                "cover_markers": True,
                "covers": [
                    {"x": -800, "z": 0},
                    {"x": 800, "z": 0},
                ],
                "pads": [
                    _spawn(0, -2000, 0),
                    _spawn(1, 2000, 0),
                ],
            },
        ),
    ]


def curriculum_steps() -> list[CurriculumStep]:
    return _curriculum_registry()


def step_by_number(n: int) -> CurriculumStep | None:
    for step in curriculum_steps():
        if step.step == n:
            return step
    return None


def _write_json(step: CurriculumStep) -> None:
    os.makedirs(MAPS_DIR, exist_ok=True)
    with open(step.json_path, "w", encoding="utf-8") as fp:
        json.dump(step.full_json(), fp, indent=2)
        fp.write("\n")


def _write_level_module(step: CurriculumStep, spec: EditorMapSpec) -> None:
    os.makedirs(LEVELS_DIR, exist_ok=True)
    content = render_level_module(spec)
    if step.covers:
        cover_lines = "".join(
            f"    g.add_cover(x={x}, z={z}, y=SPAWN_Y)\n" for x, z in step.covers
        )
        content = content.replace(
            "    add_loadout_intro(g)",
            f"{cover_lines}    add_loadout_intro(g)",
        )
    if step.covers and step.seg_mode == "marker":
        content = content.replace(
            "    floor_box_tiles,",
            "    cover_markers_from_mapdef,\n    floor_box_with_cover_markers,",
        )
        content = content.replace(
            f'    return floor_box_tiles("{step.name}", half=BOX_HALF, y=0.0, room_index=1)',
            f'''    g = build()
    return floor_box_with_cover_markers(
        "{step.name}", half=BOX_HALF, y=0.0,
        markers=cover_markers_from_mapdef(g),
    )''',
        )
        if "SEG_MODE" not in content:
            content = content.replace(
                "def build() -> MapDef:",
                'SEG_MODE = "marker"\n\n\ndef build() -> MapDef:',
            )
    if step.seg_script_basename:
        content += (
            "\nimport os\n\n"
            f'SEG_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "{step.seg_script_basename}")\n'
        )
    with open(step.level_path, "w", encoding="utf-8") as fp:
        fp.write(content)
    if step.seg_script_basename:
        _write_seg_script(step)


def _write_seg_script(step: CurriculumStep) -> None:
    """Emit a minimal seg builder under scripts/ for SEG_SCRIPT curriculum steps."""
    scripts_dir = os.path.join(ROOT, "scripts")
    script_path = os.path.join(scripts_dir, step.seg_script_basename or "")
    if not step.seg_script_basename:
        return
    half = step.json_body.get("box_half", 2500.0)
    height = step.json_body.get("box_height", 2000.0)
    body = f'''#!/usr/bin/env python3
"""Seg builder for {step.name} — curriculum SEG_SCRIPT demo."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.pdmap.seg import write_box_seg

NAME = "{step.name}"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"bg_{{NAME}}.seg")


def main():
    write_box_seg(OUT, half={half}, height={height})
    print(f"wrote {{OUT}} ({{os.path.getsize(OUT)}} bytes)")


if __name__ == "__main__":
    main()
'''
    os.makedirs(scripts_dir, exist_ok=True)
    with open(script_path, "w", encoding="utf-8") as fp:
        fp.write(body)
    os.chmod(script_path, 0o755)
    # Remove legacy co-located copy if present (probe would treat it as a level module).
    legacy = os.path.join(LEVELS_DIR, step.seg_script_basename)
    if os.path.isfile(legacy):
        os.remove(legacy)


def generate_all(*, write_levels: bool = True) -> list[CurriculumStep]:
    """Write JSON sources and optional level modules for every step."""
    steps = curriculum_steps()
    for step in steps:
        validate_level_name(step.name)
        _write_json(step)
        spec = EditorMapSpec.from_json(step.full_json(), deploy_name=step.name)
        if write_levels:
            _write_level_module(step, spec)
    return steps


@dataclass
class StepResult:
    step: int
    name: str
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_curriculum(*, verbose: bool = False) -> list[StepResult]:
    """Validate every curriculum map (MapDef + optional build dry-run)."""
    results: list[StepResult] = []
    for step in curriculum_steps():
        if not os.path.exists(step.json_path):
            results.append(StepResult(step.step, step.name, False, ["JSON missing — run generate"]))
            continue
        with open(step.json_path, encoding="utf-8") as fp:
            data = json.load(fp)
        try:
            spec = EditorMapSpec.from_json(data, deploy_name=step.name)
        except ValueError as exc:
            results.append(StepResult(step.step, step.name, False, [str(exc)]))
            continue
        room_count = spec.tiles_room_count()
        pre = validate_mapdef(spec.mapdef, tiles_room_count=room_count)
        if pre:
            results.append(StepResult(step.step, step.name, False, pre))
            continue
        errors, warnings = build_from_spec(
            spec,
            deploy=False,
            want_seg=True,
            seg_mode=step.seg_mode,
            skip_validate=False,
            verbose=verbose,
        )
        ok = not errors
        results.append(StepResult(step.step, step.name, ok, errors, warnings))
    return results


def build_curriculum(*, deploy: bool = False, mod_key: str = "mod_allinone") -> list[StepResult]:
    """Build all curriculum maps (deploy-as own name, not uff — use play script for uff)."""
    from ..play import MOD_CHOICES

    mod_dirs = None
    if deploy:
        mod_path = os.path.join(ROOT, MOD_CHOICES[mod_key], "files", "bgdata")
        mod_dirs = [mod_path]

    results: list[StepResult] = []
    for step in curriculum_steps():
        with open(step.json_path, encoding="utf-8") as fp:
            data = json.load(fp)
        spec = EditorMapSpec.from_json(data, deploy_name=step.name)
        errors, warnings = build_from_spec(
            spec,
            deploy=deploy,
            want_seg=True,
            seg_mode=step.seg_mode,
            mod_dirs=mod_dirs,
            verbose=False,
        )
        results.append(StepResult(step.step, step.name, not errors, errors, warnings))
    return results


def _boot_command(step: CurriculumStep) -> str:
    rel = os.path.relpath(step.json_path, ROOT)
    scen = f" --scenario-{step.scenario}" if step.scenario else ""
    return (
        f"./scripts/play-learn-step.sh {step.step}"
        f"\n# or:\n"
        f"python3 tools/pdmap.py from-json {rel} --deploy-as uff --deploy --play{scen}"
    )


def emit_curriculum_md(path: str = CURRICULUM_MD) -> str:
    """Write human-readable curriculum index."""
    steps = curriculum_steps()
    lines = [
        "# Map learn curriculum",
        "",
        "_Auto-generated by `pdmap learn curriculum emit-doc`. "
        "Regenerate maps with `pdmap learn curriculum generate`._",
        "",
        "Progressive test maps — one concept per step. **No stage registration** "
        "(20+ stages would bloat `setup.c`). Each step deploys into the **uff test slot** "
        "via `--deploy-as uff` + `--test-map`.",
        "",
        "## Quick start",
        "",
        "```bash",
        "# Generate / refresh all learn JSON + level modules",
        "python3 tools/pdmap.py learn curriculum generate",
        "",
        "# Validate every step (0 errors required)",
        "python3 tools/pdmap.py learn curriculum validate",
        "",
        "# Play step N (build, deploy-as uff, launch pd)",
        "./scripts/play-learn-step.sh 1",
        "./scripts/play-learn-step.sh 6    # bots / waypoints",
        "./scripts/play-learn-step.sh 10   # full composite",
        "```",
        "",
        "## Steps",
        "",
        "| Step | Map | Tests | Scenario | Expected result |",
        "|------|-----|-------|----------|-----------------|",
    ]
    for step in steps:
        scen_label = {0: "Combat", 4: "KOTH", 5: "CTF"}.get(step.scenario, str(step.scenario))
        lines.append(
            f"| {step.step} | `{step.name}` | {step.title} | {scen_label} | {step.expected} |"
        )

    lines.extend([
        "",
        "## Boot commands (examples)",
        "",
        "### Step 1 — single spawn",
        "",
        "```bash",
        _boot_command(steps[0]),
        "```",
        "",
        "### Step 6 — waypoints / bots (middle)",
        "",
        "```bash",
        _boot_command(steps[5]),
        "```",
        "",
        "### Step 10 — full composite (last core step)",
        "",
        "```bash",
        _boot_command(steps[9]),
        "```",
        "",
        "## Artifacts",
        "",
        f"- Editor JSON: `{os.path.relpath(MAPS_DIR, ROOT)}/learn_XX_<topic>.json`",
        f"- Level modules: `{os.path.relpath(LEVELS_DIR, ROOT)}/learn_XX_<topic>.py`",
        "",
        "## Facts not yet covered by a dedicated map",
        "",
    ])

    uncovered = facts_without_maps()
    if uncovered:
        for item in uncovered:
            lines.append(f"- {item}")
    else:
        lines.append("_All actionable invariant/pipeline topics have a curriculum step._")

    lines.append("")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines))
        fp.write("\n")
    return path


def facts_without_maps() -> list[str]:
    """Knowledge topics with no matching curriculum step (for next iteration)."""
    try:
        from .engine import KNOWLEDGE_PATH
        from .facts import load_knowledge

        facts = load_knowledge(KNOWLEDGE_PATH)
    except Exception as exc:
        return [f"(could not load knowledge.json: {exc})"]

    covered_tags: set[str] = set()
    for step in curriculum_steps():
        covered_tags.update(step.fact_tags)

    gaps: list[str] = []
    # Engine / doc facts that are not player-testable via a single map.
    skip_tags = {"doc-coverage", "metric", "claim-metric", "registration", "files.h", "menu", "codegen"}
    skip_categories = {"doc"}

    for fact in facts.values():
        if fact.category in skip_categories:
            continue
        if fact.confidence < 0.9:
            continue
        fact_tags = set(fact.tags) - skip_tags
        if not fact_tags:
            continue
        if fact_tags <= covered_tags:
            continue
        # Only report if no overlap with curriculum tags.
        if not (fact_tags & covered_tags):
            gaps.append(f"[{fact.category}] {fact.claim} (tags: {', '.join(sorted(fact_tags))})")

    # Residual non-map topics — only when no curriculum step covers them.
    if "registration" not in covered_tags:
        gaps.append(
            "[engine] Stage registration (pdmap register --apply) — dry-run probes only; "
            "live apply needs make smoke"
        )
    if "rendering" not in covered_tags:
        gaps.append(
            "[engine] PDMAP_SEG_MODE=empty — build flag; all steps use empty seg via play script"
        )
    if "SEG_SCRIPT" not in covered_tags:
        gaps.append("[engine] Custom SEG_SCRIPT seg generators — no modules in repo yet")
    return gaps
