"""Virtual agent office — Carrington Institute (dish) retail geometry with lobby-hub NPCs.

Pre-mission lobby hub (retail room 0x0014, Y≈35): eight friendly virtual agents
stand in an open briefing circle on the CI foyer pads — the same walkable area
Bond uses before entering training wings. Z-target any agent for a throttled HUD
status line; use (Z) on the tagged CI hub console in the north lobby for a room
overview. Player spawns on PAD_DISH_000E (604, 35, 317).

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
ANIM_TALKING_0231 = 561

CHR_AGENT_FIRST = 0x31

AILIST_AGENT_BASE = 0x0401
AILIST_CONSOLE_MONITOR = 0x1002

# CI lobby hub — retail dish room 0x0014 (``setupdish.c`` "lobby outside holo room").
# All pads at Y≈35; upper sofa lounge (Y=460) and corridor doors stay unreachable.
PAD_LOBBY_CENTRE = 0x000E  # Primary hub (604, 35, 317)
PAD_LOBBY_SOUTH = 0x0000  # (611, 35, 134)
PAD_LOBBY_NORTH = 0x0001  # (611, 35, -158)
PAD_LOBBY_WEST = 0x000F  # (130, 35, 338)
PAD_LOBBY_WEST_INNER = 0x000D  # (104, 35, 121)
PAD_LOBBY_EAST = 0x0010  # (1288, 35, 341)
PAD_LOBBY_EAST_INNER = 0x0011  # (1295, 35, 594)
PAD_LOBBY_NW = 0x0012  # (130, 35, 572)
PAD_LOBBY_CONSOLE = 0x0017  # North lobby console alcove (-100, 35, 128)
PAD_LOBBY_NE = 0x0003  # (217, 35, -172)

# MP quick-start picks among every intro Spawn — lobby Y≈35 only.
# SPEC_AUDIT F1: old alts 0x00/0x10 were the Orchestrator/Director desks — the player
# spawned on top of an agent. Repointed to a clear foyer pad + a 2nd centre spawn.
PAD_LOBBY_SPAWN_CLEAR = 0x0002  # (1019,35,-158) empty foyer pad — no agent here
PAD_PLAYER_SPAWN = PAD_LOBBY_CENTRE          # 0x0E primary — foyer centre (604,35,317)
PAD_PLAYER_SPAWN_ALT = PAD_LOBBY_SPAWN_CLEAR # clear foyer pad (verify walkable — V-1)
PAD_PLAYER_SPAWN_LOBBY = PAD_PLAYER_SPAWN    # 2nd centre spawn (safe; avoids agent pads)
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

EXAMINE_COOLDOWN_TICKS = 180

# One-shot proximity greeting range (world units); see agent_office.py GREET_RANGE
# and journal/agent_office/LLM_CONVERSATION_LAYER.md. Opt-in via VirtualAgentSpec.greet_text.
GREET_RANGE = 400

CHRANIMFLAG_SLOWUPDATE = 0x10
CHRANIMFLAG_LOCKPOS = 0x40
_AGENT_ANIM_FLAGS = CHRANIMFLAG_SLOWUPDATE | CHRANIMFLAG_LOCKPOS
_START_FIRST = 0xFFFF
_END_NATURAL = 0xFFFF


@dataclass(frozen=True)
class VirtualAgentSpec:
    role: str
    pad: int
    body: int
    head: int
    anim_index: int
    status_text: int
    doing_idle: bool = False
    facing_note: str = ""
    # Optional one-shot proximity line (lang id). None → examine-only (unchanged).
    greet_text: int | None = None


VIRTUAL_AGENTS: tuple[VirtualAgentSpec, ...] = (
    VirtualAgentSpec(
        "Director",
        PAD_LOBBY_EAST,
        BODY_CARRINGTON,
        HEAD_RANDOM,
        ANIM_TALKING_0231,
        L_DISH_000,
        facing_note="east lobby — faces briefing circle",
    ),
    VirtualAgentSpec(
        "Orchestrator",
        PAD_LOBBY_SOUTH,
        BODY_JONATHAN,
        HEAD_RANDOM,
        ANIM_STANDING_TYPE_ONE_HAND,
        L_DISH_001,
        facing_note="south foyer — coordinates agent threads",
    ),
    VirtualAgentSpec(
        "Research",
        PAD_LOBBY_WEST,
        BODY_CILABTECH,
        HEAD_RANDOM,
        ANIM_OPERATE_0204,
        L_DISH_002,
        facing_note="west outer — analysis terminal",
    ),
    VirtualAgentSpec(
        "Code",
        PAD_LOBBY_WEST_INNER,
        BODY_CILABTECH,
        HEAD_RANDOM,
        ANIM_OPERATE_0205,
        L_DISH_003,
        facing_note="west inner — implementation lane",
    ),
    VirtualAgentSpec(
        "QA",
        PAD_LOBBY_NORTH,
        BODY_CIFEMTECH,
        HEAD_RANDOM,
        ANIM_OPERATE_0206,
        L_DISH_004,
        facing_note="north foyer — verification harness",
    ),
    VirtualAgentSpec(
        "Security",
        PAD_LOBBY_NW,
        BODY_CISOLDIER,
        HEAD_RANDOM,
        ANIM_IDLE,
        L_DISH_005,
        doing_idle=True,
        facing_note="NW corner — watches lobby entry",
        # Entrance greeter (mirrors G5): one-shot line on approach, reusing its own
        # status string. Swap for a dedicated greeting/VO or the live LLM utterance.
        greet_text=L_DISH_005,
    ),
    VirtualAgentSpec(
        "Ops",
        PAD_LOBBY_EAST_INNER,
        BODY_TRENT,
        HEAD_RANDOM,
        ANIM_SITTING_TYPING,
        L_DISH_006,
        doing_idle=True,
        facing_note="east inner — deploy pipeline",
    ),
    VirtualAgentSpec(
        "Comms",
        PAD_LOBBY_NE,
        BODY_CIFEMTECH,
        HEAD_RANDOM,
        ANIM_TALKING_003D,
        L_DISH_007,
        facing_note="NE alcove — status channel",
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


def _cmd_agent_chr_do_animation(anim_index: int) -> bytes:
    return struct.pack(
        ">HHHHBBBb",
        0x000B,
        anim_index & 0xFFFF,
        _START_FIRST,
        _END_NATURAL,
        _AGENT_ANIM_FLAGS,
        16,
        CHR_SELF,
        2,
    )


def _build_agent_briefing_ailist(
    anim_index: int, status_text: int, greet_text: int | None = None
) -> bytes:
    """Loop a briefing animation; Z-target shows a throttled status line.

    When ``greet_text`` is None the bytecode is byte-identical to the examine-only
    build (existing CI agents unchanged). When set, adds a one-shot proximity
    greeting that latches until the player leaves GREET_RANGE — mirrors
    agent_office.py; see journal/agent_office/LLM_CONVERSATION_LAYER.md.
    """
    code = bytearray()
    code += _cmd_set_self_chrflag(0)

    outer = 0x10
    wait_lbl = 0x11
    next_lbl = 0x12
    msg_lbl = 0x20
    cooldown_lbl = 0x21
    greet_lbl = 0x30
    greet_wait_far_lbl = 0x31

    code += _cmd_label(outer)
    code += _cmd_agent_chr_do_animation(anim_index)
    code += _cmd_label(wait_lbl)
    code += _cmd_chr_toggle_p1p2(CHR_SELF)
    code += _cmd_set_target_chr(CHR_P1P2)
    code += _cmd_if_target_aiming_at_me(msg_lbl)
    if greet_text is not None:
        code += _cmd_if_distance_to_target_lt(GREET_RANGE, greet_lbl)
    code += _cmd_if_chr_stopped(next_lbl)
    code += _cmd_yield()
    code += _cmd_goto_first(wait_lbl)
    code += _cmd_label(next_lbl)
    code += _cmd_goto_first(outer)

    code += _cmd_label(msg_lbl)
    code += _cmd_show_hudmsg(CHR_P1P2, status_text)
    code += _cmd_restart_timer()
    code += _cmd_label(cooldown_lbl)
    code += _cmd_if_timer_gt(EXAMINE_COOLDOWN_TICKS, wait_lbl)
    code += _cmd_yield()
    code += _cmd_goto_first(cooldown_lbl)

    if greet_text is not None:
        code += _cmd_label(greet_lbl)
        code += _cmd_show_hudmsg(CHR_P1P2, greet_text)
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
        props.append(
            Chr(
                spawnflags=SPAWNFLAG_BASICGUARD | SPAWNFLAG_DONTSHOOTME,
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
                chair=0xFFFF,
                convtalk=0,
                tude=0,
                naturalanim=0,
                yvisang=0,
                teamscandist=0,
            )
        )
    return props


def agent_office_ci_std_props() -> list:
    std_flags = (
        OBJFLAG_FALL
        | OBJFLAG_XTOPADBOUNDS
        | OBJFLAG_YTOPADBOUNDS
        | OBJFLAG_ZTOPADBOUNDS
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
        (
            _build_agent_briefing_ailist(spec.anim_index, spec.status_text, spec.greet_text),
            base + offset,
        )
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
            "Carrington Institute pre-mission lobby — eight virtual agents in an open "
            "briefing circle on retail foyer pads (room 0x0014, no doors required). "
            "Z-target any agent for a status line; use (Z) on the CI hub console in "
            "the north lobby for a room overview."
        ),
        "tableCenter": {"x": TABLE_CENTER_X, "z": TABLE_CENTER_Z},
        "lobbyBriefingPads": [
            PAD_LOBBY_CENTRE,
            PAD_LOBBY_SOUTH,
            PAD_LOBBY_NORTH,
            PAD_LOBBY_WEST,
            PAD_LOBBY_WEST_INNER,
            PAD_LOBBY_EAST,
            PAD_LOBBY_EAST_INNER,
            PAD_LOBBY_NW,
            PAD_LOBBY_NE,
        ],
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
                "sibling cleared, OBJFLAG_DEACTIVATED"
            ),
            "models": _door_model_summary(),
        },
        "retailLifts": {
            "count": 2,
            "source": "src/setups/setupdish.c — two MODEL_CI_LIFT assemblies with car doors",
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
