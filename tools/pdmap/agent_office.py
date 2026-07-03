"""Virtual agent office — dataDyne G5 (depo) retail geometry with lobby-hub NPCs.

Pre-mission lobby hub (retail guard-foyer pads at Y≈35): eight friendly virtual
agents stand in an open briefing circle reachable without opening doors. Z-target
any agent for a throttled status line; use (Z) on the tagged PD console in the
west lobby (PAD_DEPO_0006) for a room overview. Player spawns on the retail lobby
patrol pad (PAD_DEPO_0080).

Uses the same setup packing pattern as ``anim_parade`` (custom ailists + MP init
0x1000). Examine ailists reuse unused ``LANGBANK_DEPO`` string slots (see
``src/assets/ntsc-final/lang/depo.json``).
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
from .depo_retail_doors import agent_office_depo_doors, depo_door_inventory
from .props import Chr, MultiMonitor, Tag

# --- Retail model / flag constants (src/include/constants.h) -----------------
MODEL_PD_CONSOLE = 0x00B2

OBJFLAG_FALL = 0x00000001
OBJFLAG_XTOPADBOUNDS = 0x00000020
OBJFLAG_YTOPADBOUNDS = 0x00000040
OBJFLAG_ZTOPADBOUNDS = 0x00000080
OBJFLAG_00000100 = 0x00000100
OBJFLAG_IGNOREFLOORCOLOUR = 0x00000400
OBJFLAG2_IMMUNETOANTI = 0x00004000
OBJFLAG3_INTERACTABLE = 0x00010000

BODY_OFFICEWORKER = 0x63
BODY_OFFICEWORKER2 = 0x64
BODY_G5_GUARD = 0x7F
BODY_DARK_COMBAT = 0x56
BODY_JONATHAN = 0x91
BODY_CARRINGTON = 0x5A
BODY_TRENT = 0x5D
HEAD_RANDOM = 0xFFFF

CHRFLAG1_DOINGIDLEANIMATION = 0x00000100
SPAWNFLAG_DONTSHOOTME = 0x00000800
TEAM_NONCOMBAT = 0x80

# Chr refs for ailist examine / console scripts (constants.h).
CHR_P1P2 = 0xF2
CHR_ANY = 0xF3

# Setup object tag for the meeting-room doorway console (if_chr_activated_object).
OBJ_AGENT_CONSOLE = 0x20

# NTSC-final animation indices (animations.json order).
ANIM_IDLE = 0
ANIM_TALKING_003D = 61
ANIM_STANDING_TYPE_ONE_HAND = 175
ANIM_OPERATE_0204 = 516
ANIM_OPERATE_0205 = 517
ANIM_OPERATE_0206 = 518
ANIM_OPERATE_0221 = 545
ANIM_SITTING_TYPING = 507
ANIM_SITTING_DORMANT = 551
ANIM_TALKING_0231 = 561

# Player + agent chrnums (avoid retail depo mission chr slots 0x02–0x17).
CHR_AGENT_FIRST = 0x31

AILIST_AGENT_BASE = 0x0401
AILIST_CONSOLE_MONITOR = 0x1002

# Retail depo lobby — open foyer before the holograph meeting wing (Y≈35).
# Doors stay deactivated for CPU; briefing happens in the walkable lobby ring.
PAD_LOBBY_PATROL = 0x0080  # Retail guard patrol — mission lobby hub (2612, 35, 340)
PAD_LOBBY_NORTH = 0x0009  # Intro corridor (2312, 35, 440)
PAD_LOBBY_WEST_A = 0x0060  # (2077, 35, -320)
PAD_LOBBY_WEST_B = 0x007E  # (2072, 35, -340)
PAD_LOBBY_WEST_C = 0x0006  # West console alcove (1953, 35, -456)
PAD_LOBBY_SOUTH_A = 0x0061  # (2535, 35, -320)
PAD_LOBBY_SOUTH_B = 0x007F  # (2472, 35, -340)
PAD_LOBBY_SOUTH_C = 0x009E  # (2294, 50, -192)
PAD_LOBBY_EAST = 0x0008  # (2692, 35, -466)
PAD_LOBBY_NE = 0x00BE  # (2888, 35, -458)

# MP quick-start picks among every intro Spawn — all lobby Y≈35 (no door transit).
# SPEC_AUDIT F1: spawn pads must NOT reuse any agent pad, or the player materializes
# on top of an agent. Old alts 0x09/0x61 were the Orchestrator/Ops desks — repointed.
# The only clear Y=35 lobby-floor pad is 0x0007 (2301,35,-458, south ring); entrance-
# side pads near 0x80 are Y=27 (lower level, unsafe). So: entrance + one clear ring pad.
PAD_LOBBY_SPAWN_CLEAR = 0x0007  # (2301,35,-458) empty south-ring pad — no agent here
PAD_PLAYER_SPAWN = PAD_LOBBY_PATROL          # 0x80 primary — entrance (2612,35,340)
PAD_PLAYER_SPAWN_ALT = PAD_LOBBY_SPAWN_CLEAR # clear ring pad (verify walkable — V-1)
PAD_PLAYER_SPAWN_LOBBY = PAD_PLAYER_SPAWN    # 2nd entrance spawn (safe; avoids agent pads)
PAD_BRIEFING_ENTRY = PAD_PLAYER_SPAWN

# Tagged PD console — west lobby (reachable from spawn without doors).
PAD_INTERACT_CONSOLE = PAD_LOBBY_WEST_C

# Briefing circle centre for layout docs / facing notes.
TABLE_CENTER_X = 2450
TABLE_CENTER_Z = 50

# LANGBANK_DEPO (0x0c) string indices — unused retail slots + one thematic reuse.
LANGBANK_DEPO = 0x0C
L_DEPO_004 = (LANGBANK_DEPO << 9) | 4
L_DEPO_005 = (LANGBANK_DEPO << 9) | 5
L_DEPO_006 = (LANGBANK_DEPO << 9) | 6
L_DEPO_007 = (LANGBANK_DEPO << 9) | 7
L_DEPO_008 = (LANGBANK_DEPO << 9) | 8
L_DEPO_053 = (LANGBANK_DEPO << 9) | 53
L_DEPO_061 = (LANGBANK_DEPO << 9) | 61
L_DEPO_066 = (LANGBANK_DEPO << 9) | 66
L_DEPO_067 = (LANGBANK_DEPO << 9) | 67

# Examine cooldown — ~3 s at 60 Hz (matches setupdepo msg ailists).
EXAMINE_COOLDOWN_TICKS = 180

# Proximity greeting range (world units). When an agent has a greet_text, it fires
# a one-shot line the moment the player crosses inside GREET_RANGE, then latches
# until the player leaves the volume — no repeat spam while standing next to them.
# This is the seam where the live LLM/voice layer replaces the static line (see
# journal/agent_office/LLM_CONVERSATION_LAYER.md).
GREET_RANGE = 400

# Parade-style anim flags: slow tick + lock root at pad.
CHRANIMFLAG_SLOWUPDATE = 0x10
CHRANIMFLAG_LOCKPOS = 0x40
_AGENT_ANIM_FLAGS = CHRANIMFLAG_SLOWUPDATE | CHRANIMFLAG_LOCKPOS
_START_FIRST = 0xFFFF
_END_NATURAL = 0xFFFF


@dataclass(frozen=True)
class VirtualAgentSpec:
    """One virtual agent at a retail depo meeting-room pad."""

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


# Lobby briefing ring — retail foyer pads at Y≈35 (no holograph-room doors needed).
VIRTUAL_AGENTS: tuple[VirtualAgentSpec, ...] = (
    VirtualAgentSpec(
        "Director",
        PAD_LOBBY_NE,
        BODY_CARRINGTON,
        HEAD_RANDOM,
        ANIM_TALKING_0231,
        L_DEPO_004,
        facing_note="NE lobby — faces briefing circle",
    ),
    VirtualAgentSpec(
        "Orchestrator",
        PAD_LOBBY_NORTH,
        BODY_JONATHAN,
        HEAD_RANDOM,
        ANIM_STANDING_TYPE_ONE_HAND,
        L_DEPO_005,
        facing_note="north corridor — coordinates threads",
    ),
    VirtualAgentSpec(
        "Research",
        PAD_LOBBY_EAST,
        BODY_OFFICEWORKER,
        HEAD_RANDOM,
        ANIM_OPERATE_0204,
        L_DEPO_006,
        facing_note="east wing — analysis terminal",
    ),
    VirtualAgentSpec(
        "Code",
        PAD_LOBBY_WEST_A,
        BODY_OFFICEWORKER2,
        HEAD_RANDOM,
        ANIM_OPERATE_0205,
        L_DEPO_007,
        facing_note="west inner — implementation lane",
    ),
    VirtualAgentSpec(
        "QA",
        PAD_LOBBY_WEST_B,
        BODY_DARK_COMBAT,
        HEAD_RANDOM,
        ANIM_OPERATE_0206,
        L_DEPO_008,
        facing_note="west outer — verification harness",
    ),
    VirtualAgentSpec(
        "Security",
        PAD_LOBBY_SOUTH_C,
        BODY_G5_GUARD,
        HEAD_RANDOM,
        ANIM_IDLE,
        L_DEPO_066,
        doing_idle=True,
        facing_note="south entry — guard stand",
        # Entrance greeter: fires a one-shot line when the player walks up (reuses
        # its own status string — swap for a dedicated greeting/VO line, or the
        # live LLM utterance, without touching the ailist).
        greet_text=L_DEPO_066,
    ),
    VirtualAgentSpec(
        "Ops",
        PAD_LOBBY_SOUTH_A,
        BODY_TRENT,
        HEAD_RANDOM,
        ANIM_SITTING_TYPING,
        L_DEPO_067,
        doing_idle=True,
        facing_note="south inner — deploy pipeline",
    ),
    VirtualAgentSpec(
        "Comms",
        PAD_LOBBY_SOUTH_B,
        BODY_OFFICEWORKER2,
        HEAD_RANDOM,
        ANIM_TALKING_003D,
        L_DEPO_053,
        facing_note="south outer — comms / status channel",
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
    """Loop one briefing animation; Z-target shows a throttled HUD status line.

    When ``greet_text`` is set, the agent also fires a one-shot proximity line the
    moment the player crosses inside ``GREET_RANGE``, latching in a "wait until far"
    loop until the player leaves before it can greet again. When ``greet_text`` is
    ``None`` the emitted bytecode is byte-for-byte identical to the examine-only
    build (verified in tests/test_agent_office_ailist.py) — existing agents are
    unchanged.
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
        # One-shot greeting: show the line, then hold in a "wait until the player
        # leaves GREET_RANGE" loop that re-arms by jumping back to wait_lbl.
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
    """Background 10xx ailist — player (Z) use on tagged doorway console."""
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


def agent_office_ailist_base() -> int:
    return AILIST_AGENT_BASE


def agent_chr_props() -> list[Chr]:
    """Friendly non-combat agents in a war-room briefing around the table."""
    props: list[Chr] = []
    base_ailist = agent_office_ailist_base()
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


def agent_office_std_props() -> list:
    """Tagged interactable console in the west lobby briefing ring."""
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
            image1=3,
            image2=3,
            image3=3,
            image4=3,
            scale=0x0100,
            model=MODEL_PD_CONSOLE,
            pad=PAD_INTERACT_CONSOLE,
            flags=std_flags,
            flags2=OBJFLAG2_IMMUNETOANTI,
            flags3=OBJFLAG3_INTERACTABLE,
            maxdamage=1000,
        ),
    ]


def agent_ailist_chunks() -> list[tuple[bytes, int]]:
    base = agent_office_ailist_base()
    chunks: list[tuple[bytes, int]] = [
        (
            _build_agent_briefing_ailist(spec.anim_index, spec.status_text, spec.greet_text),
            base + offset,
        )
        for offset, spec in enumerate(VIRTUAL_AGENTS)
    ]
    chunks.append((_build_console_monitor_ailist(L_DEPO_061), AILIST_CONSOLE_MONITOR))
    return chunks


def pack_agent_office_setup(mapdef) -> bytes:
    """Full MP setup: retail doors + virtual agents + MP simulant init."""
    props = (
        list(mapdef.props)
        + agent_office_depo_doors()
        + agent_office_std_props()
        + agent_chr_props()
    )
    props_bin = b"".join(p.pack() for p in props) + struct.pack(">I", 0x34)
    intro_bin = b"".join(cmd.pack() for cmd in mapdef.intro) + struct.pack(">I", 12)

    ailist_chunks: list[tuple[bytes, int]] = [(_mp_init_ailist(), AILIST_MP_INIT)]
    ailist_chunks.extend(agent_ailist_chunks())

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


def agent_office_layout_payload() -> dict:
    """Editor / docs metadata for the virtual agent office."""
    return {
        "id": "agent_office",
        "label": "Virtual Agent Office",
        "stage": "STAGE_G5BUILDING",
        "retailGeometry": "depo",
        "description": (
            "dataDyne G5 pre-mission lobby — eight virtual agents in an open briefing "
            "circle on retail foyer pads (no doors required). Z-target any agent for a "
            "status line; use (Z) on the PD console in the west lobby for a room overview."
        ),
        "tableCenter": {"x": TABLE_CENTER_X, "z": TABLE_CENTER_Z},
        "lobbyBriefingPads": [
            PAD_LOBBY_PATROL,
            PAD_LOBBY_NORTH,
            PAD_LOBBY_WEST_A,
            PAD_LOBBY_WEST_B,
            PAD_LOBBY_SOUTH_A,
            PAD_LOBBY_SOUTH_B,
            PAD_LOBBY_SOUTH_C,
            PAD_LOBBY_EAST,
            PAD_LOBBY_NE,
        ],
        "playerSpawnPads": [
            PAD_BRIEFING_ENTRY,
            PAD_PLAYER_SPAWN_ALT,
            PAD_PLAYER_SPAWN_LOBBY,
        ],
        "interactConsolePad": PAD_INTERACT_CONSOLE,
        "retailDoors": {
            "count": len(depo_door_inventory()),
            "source": (
                "src/setups/setupdepo.c — all retail doors, sibling cleared, "
                "OBJFLAG_DEACTIVATED (static render; doorTick skipped)"
            ),
            "models": _door_model_summary(),
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
    """Model → count for layout / docs metadata."""
    from collections import Counter

    return dict(Counter(row["model"] for row in depo_door_inventory()))
