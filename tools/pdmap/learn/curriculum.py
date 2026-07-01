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
    fact_tags: tuple[str, ...] = ()
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
    with open(step.level_path, "w", encoding="utf-8") as fp:
        fp.write(render_level_module(spec))


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
        pre = validate_mapdef(spec.mapdef, tiles_room_count=2)
        if pre:
            results.append(StepResult(step.step, step.name, False, pre))
            continue
        errors, warnings = build_from_spec(
            spec,
            deploy=False,
            want_seg=True,
            seg_mode="empty",
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
            seg_mode="empty",
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

    # Explicit non-map topics.
    gaps.extend([
        "[engine] Stage registration (pdmap register --apply) — dry-run probes only; live apply needs make smoke",
        "[engine] PDMAP_SEG_MODE=empty — build flag; all steps use empty seg via play script",
        "[engine] Custom SEG_SCRIPT seg generators — no modules in repo yet",
    ])
    return gaps
