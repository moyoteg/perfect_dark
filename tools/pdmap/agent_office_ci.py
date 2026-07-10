"""Virtual agent office — Carrington Institute (dish) retail geometry with office-desk NPCs.

Eight friendly virtual agents sit or work at retail CI office desks/chairs — the
same ``setupdish.c`` chr pads colleagues use (Y≈49–416), not the Y≈35 foyer ring.
Z-target any agent for a throttled HUD status line; use (Z) on the tagged CI hub
console in the north lobby (PAD_DISH_0017) for a room overview. Player spawns on
walkable corridor pads (Y≈35) near the office wings.

Uses ``LANGBANK_DISH`` slots ``L_DISH_000``–``007`` and ``125`` (unused in retail
``setupdish.c``). Strings live in ``dish.json`` and must be latin-1 (rebuild
``LdishE`` via ``mklang`` after edits).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .anim_parade import (
    AILIST_MP_INIT,
    CHRFLAG0_HOLD_POSITION,
    CHRFLAG0_SKIPSAFETYCHECKS,
    SPAWNFLAG_BASICGUARD,
    SQUADRON_01,
    CHR_SELF,
    _align4,
    _cmd_chr_do_animation,
    _cmd_endlist,
    _cmd_goto_first,
    _cmd_if_chr_stopped,
    _cmd_label,
    _cmd_set_self_chrflag,
    _cmd_yield,
    _mp_init_ailist,
)
from .ci_retail_doors import agent_office_ci_doors, dish_door_inventory
from .ci_retail_lifts import agent_office_ci_lifts
from .ci_retail_office_props import agent_office_ci_office_props, office_furniture_inventory
from .props import Chr, MultiMonitor, Tag

MODEL_CIHUB = 0x01AA

OBJFLAG_FALL = 0x00000001
OBJFLAG_XTOPADBOUNDS = 0x00000020
OBJFLAG_YTOPADBOUNDS = 0x00000040
OBJFLAG_ZTOPADBOUNDS = 0x00000080
OBJFLAG_00000100 = 0x00000100
OBJFLAG_IGNOREFLOORCOLOUR = 0x00000400
OBJFLAG2_IMMUNETOANTI = 0x00004000
OBJFLAG3_INTERACTABLE = 0x00010000

BODY_CILABTECH = 0x8E
BODY_CIFEMTECH = 0x8F
BODY_CISOLDIER = 0x92
BODY_CARRINGTON = 0x5A
BODY_JONATHAN = 0x91
BODY_TRENT = 0x5D
HEAD_RANDOM = 0xFFFF

CHRFLAG1_DOINGIDLEANIMATION = 0x00000100
SPAWNFLAG_DONTSHOOTME = 0x00000800
SPAWNFLAG_FIXEDHEIGHT = 0x00004000
TEAM_NONCOMBAT = 0x80

CHR_P1P2 = 0xF2
CHR_ANY = 0xF3

OBJ_AGENT_CONSOLE = 0x20

ANIM_IDLE = 0
ANIM_TALKING_003D = 61
ANIM_STANDING_TYPE_ONE_HAND = 175
ANIM_OPERATE_0204 = 516
ANIM_OPERATE_0205 = 517
ANIM_OPERATE_0206 = 518
ANIM_SITTING_TYPING = 507
ANIM_SITTING_DORMANT = 551
ANIM_TALKING_0231 = 561

CHR_AGENT_FIRST = 0x31

AILIST_AGENT_BASE = 0x0401
AILIST_CONSOLE_MONITOR = 0x1002

# CI foyer / corridor (Y≈35) — player spawns and north-lobby console only.
PAD_LOBBY_CENTRE = 0x000E  # Foyer centre (604, 35, 317)
PAD_LOBBY_CONSOLE = 0x0017  # North lobby console alcove (-100, 35, 128)
PAD_CORRIDOR_WEST_HUB = 0x002F  # West office-wing junction (-1395, 35, 86)
PAD_CORRIDOR_EAST_HUB = 0x0015  # East corridor toward Carrington wing (739, 35, 1151)
PAD_CORRIDOR_WEST_CONNECT = 0x0018  # West lobby connector (-260, 35, 409)

# Retail office chr pads — ``setupdish.c`` colleagues at desks/chairs (Y≈49–416).
PAD_OUTSIDE_JO_OFFICE = 0x0053  # Outside Jo's office door (684, 460, 322) — setupdish.c
PAD_OFFICE_JO_DESK = 0x00F5  # Retail intro spawn / Jo desk (637, 360, 923)
PAD_OFFICE_CARRINGTON = 0x00F6  # Carrington office (1496, 360, 708)
PAD_OFFICE_WEST_LAB = 0x00F7  # Mark labtech desk (-1334, 360, 223)
PAD_OFFICE_WEST_COMMS = 0x00F8  # West femtech desk (-2213, 360, -260)
PAD_OFFICE_EAST_LAB = 0x00FA  # Christ labtech desk (1496, 49, 708)
PAD_OFFICE_EAST_SIT = 0x00FC  # Beau labtech @ chair (1481, 91, 1198)
PAD_OFFICE_WEST_SIT_QA = 0x00FE  # West femtech @ chair (-1238, 416, 568)

# MP quick-start: retail intro at Jo's desk; alts on Y≈35 corridor pads (not agent chr pads).
PAD_PLAYER_SPAWN = PAD_OFFICE_JO_DESK  # primary — Jo's office (setupdish.c intro → 0x00F5)
PAD_PLAYER_SPAWN_ALT = PAD_CORRIDOR_WEST_CONNECT  # west lobby connector (Y≈35)
PAD_PLAYER_SPAWN_LOBBY = PAD_CORRIDOR_EAST_HUB  # east corridor toward Carrington wing (Y≈35)
PAD_BRIEFING_ENTRY = PAD_PLAYER_SPAWN

PAD_INTERACT_CONSOLE = PAD_LOBBY_CONSOLE

TABLE_CENTER_X = 604
TABLE_CENTER_Z = 317

LANGBANK_DISH = 0x0E
L_DISH_000 = (LANGBANK_DISH << 9) | 0
L_DISH_001 = (LANGBANK_DISH << 9) | 1
L_DISH_002 = (LANGBANK_DISH << 9) | 2
L_DISH_003 = (LANGBANK_DISH << 9) | 3
L_DISH_004 = (LANGBANK_DISH << 9) | 4
L_DISH_005 = (LANGBANK_DISH << 9) | 5
L_DISH_006 = (LANGBANK_DISH << 9) | 6
L_DISH_007 = (LANGBANK_DISH << 9) | 7
L_DISH_125 = (LANGBANK_DISH << 9) | 125
# Pass 10: dedicated Security proximity greet (distinct from L_DISH_005 examine/status).
L_DISH_126 = (LANGBANK_DISH << 9) | 126

EXAMINE_COOLDOWN_TICKS = 180

# One-shot proximity greeting range (world units); see agent_office.py GREET_RANGE
# and journal/agent_office/LLM_CONVERSATION_LAYER.md. Opt-in via VirtualAgentSpec.greet_text.
GREET_RANGE = 400

CHRANIMFLAG_PAUSEATEND = 0x04
CHRANIMFLAG_SLOWUPDATE = 0x10
CHRANIMFLAG_LOCKPOS = 0x40
_AGENT_ANIM_FLAGS = CHRANIMFLAG_SLOWUPDATE | CHRANIMFLAG_LOCKPOS
# Retail GAILIST_BUSY sitting colleagues — allow anim root motion to snap to chair tag.
_SITTING_ANIM_FLAGS = CHRANIMFLAG_PAUSEATEND | CHRANIMFLAG_SLOWUPDATE
_START_FIRST = 0xFFFF
_END_NATURAL = 0xFFFF

# setupdish.c sitting colleagues use naturalanim=2 (typing/dormant idle actions).
IDLEACTION_STANDING = 0x01
IDLEACTION_SITTING_TYPING = 0x02
IDLEACTION_SITTING_DORMANT = 0x03
SPECIALDIE_ONCHAIR = 0x06


@dataclass(frozen=True)
class VirtualAgentSpec:
    role: str
    pad: int
    body: int
    head: int
    anim_index: int
    status_text: int
    doing_idle: bool = False
    fixed_height: bool = False
    chair: int = 0xFFFF
    naturalanim: int = 0
    anim_flags: int = _AGENT_ANIM_FLAGS
    anim_speed: int = 16
    facing_note: str = ""
    # Optional one-shot proximity line (lang id). None → examine-only (unchanged).
    greet_text: int | None = None


# Retail office desk placements — chr pads from setupdish.c (not foyer Y≈35 ring).
VIRTUAL_AGENTS: tuple[VirtualAgentSpec, ...] = (
    VirtualAgentSpec(
        "Director",
        PAD_OFFICE_CARRINGTON,
        BODY_CARRINGTON,
        HEAD_RANDOM,
        ANIM_TALKING_0231,
        L_DISH_000,
        facing_note="Carrington office — east wing executive desk",
    ),
    VirtualAgentSpec(
        "Orchestrator",
        PAD_OUTSIDE_JO_OFFICE,
        BODY_JONATHAN,
        HEAD_RANDOM,
        ANIM_STANDING_TYPE_ONE_HAND,
        L_DISH_001,
        facing_note="outside Jo's office door — player keeps retail 0x00F5 desk spawn",
    ),
    VirtualAgentSpec(
        "Research",
        PAD_OFFICE_WEST_LAB,
        BODY_CILABTECH,
        HEAD_RANDOM,
        ANIM_OPERATE_0204,
        L_DISH_002,
        facing_note="west lab wing — Mark colleague desk",
    ),
    VirtualAgentSpec(
        "Code",
        PAD_OFFICE_EAST_LAB,
        BODY_CILABTECH,
        HEAD_RANDOM,
        ANIM_OPERATE_0205,
        L_DISH_003,
        facing_note="east lab — Christ colleague terminal",
    ),
    VirtualAgentSpec(
        "QA",
        PAD_OFFICE_WEST_SIT_QA,
        BODY_CIFEMTECH,
        HEAD_RANDOM,
        ANIM_SITTING_DORMANT,
        L_DISH_004,
        doing_idle=True,
        fixed_height=True,
        chair=0x02,
        naturalanim=IDLEACTION_SITTING_DORMANT,
        anim_flags=_SITTING_ANIM_FLAGS,
        anim_speed=0,
        facing_note="west office chair — verification harness",
    ),
    VirtualAgentSpec(
        "Security",
        PAD_CORRIDOR_WEST_HUB,
        BODY_CISOLDIER,
        HEAD_RANDOM,
        ANIM_STANDING_TYPE_ONE_HAND,
        L_DISH_005,
        doing_idle=True,
        fixed_height=True,
        naturalanim=IDLEACTION_STANDING,
        facing_note="west corridor entry — watches office wing",
        # Entrance greeter: dedicated greet lang id (Pass 10) — examine stays L_DISH_005.
        greet_text=L_DISH_126,
    ),
    VirtualAgentSpec(
        "Ops",
        PAD_OFFICE_EAST_SIT,
        BODY_TRENT,
        HEAD_RANDOM,
        ANIM_SITTING_TYPING,
        L_DISH_006,
        doing_idle=True,
        fixed_height=True,
        chair=0x00,
        naturalanim=IDLEACTION_SITTING_TYPING,
        anim_flags=_SITTING_ANIM_FLAGS,
        anim_speed=0,
        facing_note="east wing chair — Beau colleague deploy desk",
    ),
    VirtualAgentSpec(
        "Comms",
        PAD_OFFICE_WEST_COMMS,
        BODY_CIFEMTECH,
        HEAD_RANDOM,
        ANIM_TALKING_003D,
        L_DISH_007,
        facing_note="far west desk — comms / status channel",
    ),
)


def _cmd_show_hudmsg(chr: int, text: int) -> bytes:
    return struct.pack(">HBH", 0x00CB, chr & 0xFF, text & 0xFFFF)


def _cmd_if_target_aiming_at_me(label: int) -> bytes:
    return struct.pack(">HB", 0x004A, label & 0xFF)


def _cmd_chr_toggle_p1p2(chr: int) -> bytes:
    return struct.pack(">HB", 0x01B3, chr & 0xFF)


def _cmd_set_target_chr(chr: int) -> bytes:
    return struct.pack(">HBBB", 0x0106, chr & 0xFF, 0, 0)


def _cmd_restart_timer() -> bytes:
    return struct.pack(">H", 0x00B6)


def _cmd_if_timer_gt(value: int, label: int) -> bytes:
    return struct.pack(">HBHB", 0x00BD, 0, value & 0xFFFF, label & 0xFF)


def _cmd_if_chr_activated_object(chr: int, obj: int, label: int) -> bytes:
    return struct.pack(">HBBH", 0x0063, chr & 0xFF, obj & 0xFF, label & 0xFF)


def _cmd_if_distance_to_target_lt(distance: int, label: int) -> bytes:
    # commands.h if_distance_to_target_lt: mkshort(0x0052), mkshort(distance/10), label.
    return struct.pack(">HHB", 0x0052, (distance // 10) & 0xFFFF, label & 0xFF)


def _cmd_if_distance_to_target_gt(distance: int, label: int) -> bytes:
    # commands.h if_distance_to_target_gt: mkshort(0x0053), mkshort(distance/10), label.
    return struct.pack(">HHB", 0x0053, (distance // 10) & 0xFFFF, label & 0xFF)


def _cmd_agent_chr_do_animation(
    anim_index: int,
    anim_flags: int = _AGENT_ANIM_FLAGS,
    anim_speed: int = 16,
) -> bytes:
    return struct.pack(
        ">HHHHBBBb",
        0x000B,
        anim_index & 0xFFFF,
        _START_FIRST,
        _END_NATURAL,
        anim_flags & 0xFF,
        anim_speed & 0xFF,
        CHR_SELF,
        2,
    )


def _cmd_set_chr_special_death_animation(chr: int, specialdie: int) -> bytes:
    return struct.pack(">HBB", 0x01A0, chr & 0xFF, specialdie & 0xFF)


def _build_agent_briefing_ailist(spec: VirtualAgentSpec) -> bytes:
    """Loop a briefing animation; Z-target shows a throttled status line.

    When ``greet_text`` is None the bytecode is byte-identical to the examine-only
    build (existing CI agents unchanged). When set, adds a one-shot proximity
    greeting that latches until the player leaves GREET_RANGE — mirrors
    agent_office.py; see journal/agent_office/LLM_CONVERSATION_LAYER.md.
    """
    code = bytearray()
    code += _cmd_set_self_chrflag(0)
    if spec.chair != 0xFFFF:
        # Match retail GAILIST_BUSY chair sit setup (setupdish.c Beau/Russ/QA).
        code += _cmd_set_chr_special_death_animation(CHR_SELF, SPECIALDIE_ONCHAIR)

    outer = 0x10
    wait_lbl = 0x11
    next_lbl = 0x12
    msg_lbl = 0x20
    cooldown_lbl = 0x21
    greet_lbl = 0x30
    greet_wait_far_lbl = 0x31

    code += _cmd_label(outer)
    code += _cmd_agent_chr_do_animation(
        spec.anim_index, spec.anim_flags, spec.anim_speed
    )
    code += _cmd_label(wait_lbl)
    code += _cmd_chr_toggle_p1p2(CHR_SELF)
    code += _cmd_set_target_chr(CHR_P1P2)
    code += _cmd_if_target_aiming_at_me(msg_lbl)
    if spec.greet_text is not None:
        code += _cmd_if_distance_to_target_lt(GREET_RANGE, greet_lbl)
    code += _cmd_if_chr_stopped(next_lbl)
    code += _cmd_yield()
    code += _cmd_goto_first(wait_lbl)
    code += _cmd_label(next_lbl)
    code += _cmd_goto_first(outer)

    code += _cmd_label(msg_lbl)
    code += _cmd_show_hudmsg(CHR_P1P2, spec.status_text)
    code += _cmd_restart_timer()
    code += _cmd_label(cooldown_lbl)
    code += _cmd_if_timer_gt(EXAMINE_COOLDOWN_TICKS, wait_lbl)
    code += _cmd_yield()
    code += _cmd_goto_first(cooldown_lbl)

    if spec.greet_text is not None:
        code += _cmd_label(greet_lbl)
        code += _cmd_show_hudmsg(CHR_P1P2, spec.greet_text)
        code += _cmd_label(greet_wait_far_lbl)
        code += _cmd_chr_toggle_p1p2(CHR_SELF)
        code += _cmd_set_target_chr(CHR_P1P2)
        code += _cmd_if_distance_to_target_gt(GREET_RANGE, wait_lbl)
        code += _cmd_yield()
        code += _cmd_goto_first(greet_wait_far_lbl)

    code += _cmd_endlist()
    return bytes(code)


def _build_console_monitor_ailist(status_text: int) -> bytes:
    code = bytearray()
    loop_lbl = 0x04
    show_lbl = 0x2C
    cooldown_lbl = 0x2D

    code += _cmd_label(loop_lbl)
    code += _cmd_if_chr_activated_object(CHR_ANY, OBJ_AGENT_CONSOLE, show_lbl)
    code += _cmd_yield()
    code += _cmd_goto_first(loop_lbl)

    code += _cmd_label(show_lbl)
    code += _cmd_show_hudmsg(CHR_P1P2, status_text)
    code += _cmd_restart_timer()
    code += _cmd_label(cooldown_lbl)
    code += _cmd_if_timer_gt(EXAMINE_COOLDOWN_TICKS, loop_lbl)
    code += _cmd_yield()
    code += _cmd_goto_first(cooldown_lbl)
    code += _cmd_endlist()
    return bytes(code)


def agent_office_ci_ailist_base() -> int:
    return AILIST_AGENT_BASE


def agent_ci_chr_props() -> list[Chr]:
    props: list[Chr] = []
    base_ailist = agent_office_ci_ailist_base()
    for offset, spec in enumerate(VIRTUAL_AGENTS):
        flags2 = CHRFLAG1_DOINGIDLEANIMATION if spec.doing_idle else 0
        spawnflags = SPAWNFLAG_BASICGUARD | SPAWNFLAG_DONTSHOOTME
        if spec.fixed_height:
            spawnflags |= SPAWNFLAG_FIXEDHEIGHT
        props.append(
            Chr(
                spawnflags=spawnflags,
                chrnum=CHR_AGENT_FIRST + offset,
                pad=spec.pad,
                body=spec.body,
                head=spec.head,
                function=base_ailist + offset,
                padpreset=0xFFFF,
                chrpreset=0xFFFF,
                hear_scale=2000,
                view_dist=100,
                flags=CHRFLAG0_SKIPSAFETYCHECKS | CHRFLAG0_HOLD_POSITION,
                flags2=flags2,
                team=TEAM_NONCOMBAT,
                squadron=SQUADRON_01,
                chair=spec.chair,
                convtalk=0,
                tude=0,
                naturalanim=spec.naturalanim,
                yvisang=0,
                teamscandist=0,
            )
        )
    return props


def agent_office_ci_std_props() -> list:
    # Do not use TOPADBOUNDS: PAD_DISH_0017 has a generic 200 u bbox (same pitfall as
    # G5 PAD_DEPO_0062). setupCreateObject scales MODEL_CIHUB to fill that volume and
    # the console hangs mid-air in the north-lobby corridor instead of sitting on the floor.
    std_flags = (
        OBJFLAG_FALL
        | OBJFLAG_00000100
        | OBJFLAG_IGNOREFLOORCOLOUR
    )
    return [
        Tag(OBJ_AGENT_CONSOLE, 1),
        MultiMonitor(
            image1=20,
            image2=20,
            image3=20,
            image4=20,
            scale=0x0100,
            model=MODEL_CIHUB,
            pad=PAD_INTERACT_CONSOLE,
            flags=std_flags,
            flags2=OBJFLAG2_IMMUNETOANTI,
            flags3=OBJFLAG3_INTERACTABLE,
            maxdamage=1000,
        ),
    ]


def agent_ci_ailist_chunks() -> list[tuple[bytes, int]]:
    base = agent_office_ci_ailist_base()
    chunks: list[tuple[bytes, int]] = [
        (_build_agent_briefing_ailist(spec), base + offset)
        for offset, spec in enumerate(VIRTUAL_AGENTS)
    ]
    chunks.append((_build_console_monitor_ailist(L_DISH_125), AILIST_CONSOLE_MONITOR))
    return chunks


def pack_agent_office_ci_setup(mapdef) -> bytes:
    """Full MP setup: retail doors/lifts + virtual agents + MP simulant init."""
    props = (
        list(mapdef.props)
        + agent_office_ci_doors()
        + agent_office_ci_lifts()
        + agent_office_ci_office_props()
        + agent_office_ci_std_props()
        + agent_ci_chr_props()
    )
    props_bin = b"".join(p.pack() for p in props) + struct.pack(">I", 0x34)
    intro_bin = b"".join(cmd.pack() for cmd in mapdef.intro) + struct.pack(">I", 12)

    ailist_chunks: list[tuple[bytes, int]] = [(_mp_init_ailist(), AILIST_MP_INIT)]
    ailist_chunks.extend(agent_ci_ailist_chunks())

    ptr_props = 0x20
    ptr_intro = ptr_props + len(props_bin)
    ptr_ailist_code = ptr_intro + len(intro_bin)

    ailist_code = bytearray()
    ailist_table = bytearray()
    for code, aid in ailist_chunks:
        abs_ptr = ptr_ailist_code + len(ailist_code)
        ailist_table += struct.pack(">Ii", abs_ptr, aid)
        ailist_code += code
    ailist_code = _align4(bytes(ailist_code))
    ailist_table += struct.pack(">Ii", 0, 0)

    ptr_ailists = ptr_ailist_code + len(ailist_code)
    ptr_paths = ptr_ailists + len(ailist_table)
    paths_term = b"\x00" * 8

    header = struct.pack(
        ">8I",
        0,
        0,
        0,
        ptr_intro,
        ptr_props,
        ptr_paths,
        ptr_ailists,
        0,
    )
    return header + props_bin + intro_bin + ailist_code + ailist_table + paths_term


def agent_office_ci_layout_payload() -> dict:
    return {
        "id": "agent_office_ci",
        "label": "Virtual Agent Office (CI)",
        "stage": "STAGE_CITRAINING",
        "retailGeometry": "dish",
        "description": (
            "Carrington Institute office wing — player spawns at retail intro pad "
            "(PAD_DISH_00F5, Jo's office). Eight virtual agents at retail desk/chair "
            "chr pads. Z-target any agent for a status line; use (Z) on the CI hub "
            "console in the north lobby for a room overview."
        ),
        "tableCenter": {"x": TABLE_CENTER_X, "z": TABLE_CENTER_Z},
        "officeAgentPads": [spec.pad for spec in VIRTUAL_AGENTS],
        "playerSpawnPads": [
            PAD_BRIEFING_ENTRY,
            PAD_PLAYER_SPAWN_ALT,
            PAD_PLAYER_SPAWN_LOBBY,
        ],
        "interactConsolePad": PAD_INTERACT_CONSOLE,
        "retailDoors": {
            "count": len(dish_door_inventory()),
            "source": (
                "src/setups/setupdish.c — retail doors (lift-car pads excluded), "
                "mp_unlock + sibling remapped (closed at init; normal doorTick; open/close via Z)"
            ),
            "models": _door_model_summary(),
        },
        "retailLifts": {
            "count": 2,
            "source": "src/setups/setupdish.c — two MODEL_CI_LIFT assemblies with car doors",
        },
        "retailOfficeFurniture": {
            "count": len(office_furniture_inventory()),
            "source": (
                "src/setups/setupdish.c — four agent desk clusters at pads "
                "0x021A–0x0225 only (excludes lobby/lift-adjacent 0x0226–0x022B, 0x022D)"
            ),
        },
        "agents": [
            {
                "label": spec.role,
                "role": spec.role,
                "pad": spec.pad,
                "padHex": f"0x{spec.pad:04X}",
                "body": spec.body,
                "animIndex": spec.anim_index,
                "statusTextHex": f"0x{spec.status_text:04X}",
                "facing": spec.facing_note,
            }
            for spec in VIRTUAL_AGENTS
        ],
    }


def _door_model_summary() -> dict[str, int]:
    from collections import Counter

    return dict(Counter(row["model"] for row in dish_door_inventory()))
