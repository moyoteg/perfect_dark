"""Virtual agent office — dataDyne G5 (depo) retail geometry with holograph meeting room.

Eight friendly virtual agents stand in the retail holograph briefing room (south wing,
Y≈27) where Cassandra's meeting takes place in the single-player mission. Z-target any
agent for a throttled status line; use (Z) on the tagged PD console at the meeting-room
doorway (PAD_DEPO_0062) for a room overview. Player spawns on the corridor pads leading
into the meeting room (PAD_DEPO_003D / 003E).

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
from .depo_retail_office_props import (
    agent_office_depo_office_props,
    meeting_furniture_inventory,
)
from .props import Chr, MultiMonitor, SingleMonitor, Tag

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
SPAWNFLAG_FIXEDHEIGHT = 0x00004000
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

# Meeting-room corridor — player spawns leading into holograph briefing (Y≈27).
PAD_MEETING_CORRIDOR_W = 0x003D  # West corridor into meeting room (2403, 27, 3165)
PAD_MEETING_CORRIDOR_E = 0x003E  # East approach corridor (3131, 27, 3160)
PAD_MEETING_CORRIDOR_S = 0x008F  # South approach corridor (2646, 27, 1990)

# Legacy lobby pads (retail setupdepo.c intro[] — not used for Agent Office player spawn).
PAD_LOBBY_ENTRY = 0x0083  # Retail intro spawn (2605, 35, -1243)
PAD_LOBBY_GRID_A = 0x0002  # Entrance foyer grid (2694, 35, -1368)
PAD_LOBBY_EAST = 0x0080  # East lobby connector (2612, 35, 340)

# Holograph meeting room — agent briefing pads (Y≈27, south wing).
PAD_MEETING_CONSOLE = 0x0062  # Doorway PD console (2971, 27, 2880)

PAD_MEETING_DIRECTOR = 0x0088  # (2971, 27, 2811)
PAD_MEETING_ORCHESTRATOR = 0x0089  # (3080, 27, 2749)
PAD_MEETING_RESEARCH = 0x0064  # (2971, 27, 2520)
PAD_MEETING_CODE = 0x0063  # (2971, 27, 2720)
PAD_MEETING_QA = 0x008A  # (2524, 27, 2807)
PAD_MEETING_SECURITY = 0x008B  # (2389, 27, 2753)
# Ops chr pad — retail cinema north chr (Blonde 0x0087); chair tag 0x4a → G5BIGCHAIR @ 0x00F8.
PAD_MEETING_OPS = 0x0087  # (2651, 27, 3115)
PAD_MEETING_OPS_CHAIR = 0x00F8  # (2754, 27, 3070) — furniture pad only (tag 0x4a)
PAD_MEETING_OPS_CONSOLE = 0x0087  # PD console co-located with Ops chr pad
# Comms moved off Ops chr pad to east corridor approach (was 0x0087).
PAD_MEETING_COMMS = 0x003E  # (3131, 27, 3160)

PAD_PLAYER_SPAWN = PAD_MEETING_CORRIDOR_W
PAD_PLAYER_SPAWN_ALT = PAD_MEETING_CORRIDOR_E
PAD_PLAYER_SPAWN_LOBBY = PAD_MEETING_CORRIDOR_S
PAD_BRIEFING_ENTRY = PAD_PLAYER_SPAWN

PAD_INTERACT_CONSOLE = PAD_MEETING_CONSOLE

TABLE_CENTER_X = 2750
TABLE_CENTER_Z = 2850

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
# Pass 10: dedicated Security proximity greet (distinct from L_DEPO_066 examine/status).
L_DEPO_068 = (LANGBANK_DEPO << 9) | 68

# Examine cooldown — ~3 s at 60 Hz (matches setupdepo msg ailists).
EXAMINE_COOLDOWN_TICKS = 180

# Proximity greeting range (world units). When an agent has a greet_text, it fires
# a one-shot line the moment the player crosses inside GREET_RANGE, then latches
# until the player leaves the volume — no repeat spam while standing next to them.
# This is the seam where the live LLM/voice layer replaces the static line (see
# journal/agent_office/LLM_CONVERSATION_LAYER.md).
GREET_RANGE = 400

CHRANIMFLAG_PAUSEATEND = 0x04
CHRANIMFLAG_SLOWUPDATE = 0x10
CHRANIMFLAG_LOCKPOS = 0x40
_AGENT_ANIM_FLAGS = CHRANIMFLAG_SLOWUPDATE | CHRANIMFLAG_LOCKPOS
# Retail GAILIST_BUSY sitting — root motion snaps to chair tag (no LOCKPOS).
_SITTING_ANIM_FLAGS = CHRANIMFLAG_PAUSEATEND | CHRANIMFLAG_SLOWUPDATE
_START_FIRST = 0xFFFF
_END_NATURAL = 0xFFFF

IDLEACTION_STANDING = 0x01
IDLEACTION_SITTING_TYPING = 0x02
IDLEACTION_SITTING_DORMANT = 0x03
SPECIALDIE_ONCHAIR = 0x06

# Retail cinema chair tags (setupdepo.c Cassandra / Blonde colleagues).
CHAIR_TAG_G5_BIG = 0x4A


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
    fixed_height: bool = False
    chair: int = 0xFFFF
    naturalanim: int = 0
    anim_flags: int = _AGENT_ANIM_FLAGS
    anim_speed: int = 16
    facing_note: str = ""
    # Optional one-shot proximity line (lang id). None → examine-only (unchanged).
    greet_text: int | None = None


# Holograph meeting room — retail mission pads with mixed briefing animations.
VIRTUAL_AGENTS: tuple[VirtualAgentSpec, ...] = (
    VirtualAgentSpec(
        "Director",
        PAD_MEETING_DIRECTOR,
        BODY_CARRINGTON,
        HEAD_RANDOM,
        ANIM_TALKING_0231,
        L_DEPO_004,
        facing_note="meeting table — executive briefing",
    ),
    VirtualAgentSpec(
        "Orchestrator",
        PAD_MEETING_ORCHESTRATOR,
        BODY_JONATHAN,
        HEAD_RANDOM,
        ANIM_STANDING_TYPE_ONE_HAND,
        L_DEPO_005,
        facing_note="east side — coordinates threads",
    ),
    VirtualAgentSpec(
        "Research",
        PAD_MEETING_RESEARCH,
        BODY_OFFICEWORKER,
        HEAD_RANDOM,
        ANIM_OPERATE_0204,
        L_DEPO_006,
        facing_note="south terminal — analysis lane",
    ),
    VirtualAgentSpec(
        "Code",
        PAD_MEETING_CODE,
        BODY_OFFICEWORKER2,
        HEAD_RANDOM,
        ANIM_OPERATE_0205,
        L_DEPO_007,
        facing_note="centre terminal — implementation",
    ),
    VirtualAgentSpec(
        "QA",
        PAD_MEETING_QA,
        BODY_DARK_COMBAT,
        HEAD_RANDOM,
        ANIM_OPERATE_0206,
        L_DEPO_008,
        facing_note="west side — verification harness",
    ),
    VirtualAgentSpec(
        "Security",
        PAD_MEETING_SECURITY,
        BODY_G5_GUARD,
        HEAD_RANDOM,
        ANIM_STANDING_TYPE_ONE_HAND,
        L_DEPO_066,
        doing_idle=True,
        fixed_height=True,
        naturalanim=IDLEACTION_STANDING,
        facing_note="west entry — guard stand",
        greet_text=L_DEPO_068,
    ),
    VirtualAgentSpec(
        "Ops",
        PAD_MEETING_OPS,
        BODY_TRENT,
        HEAD_RANDOM,
        ANIM_SITTING_TYPING,
        L_DEPO_067,
        doing_idle=True,
        fixed_height=True,
        chair=CHAIR_TAG_G5_BIG,
        naturalanim=IDLEACTION_SITTING_TYPING,
        anim_flags=_SITTING_ANIM_FLAGS,
        anim_speed=0,
        facing_note="north desk — deploy pipeline (chair 0x4a @ 0x00F8)",
    ),
    VirtualAgentSpec(
        "Comms",
        PAD_MEETING_COMMS,
        BODY_OFFICEWORKER2,
        HEAD_RANDOM,
        ANIM_TALKING_003D,
        L_DEPO_053,
        facing_note="north-east — comms / status channel",
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
    """Loop a briefing animation; Z-target shows a throttled HUD status line.

    When ``spec.greet_text`` is set, the agent also fires a one-shot proximity line the
    moment the player crosses inside ``GREET_RANGE``, latching in a "wait until far"
    loop until the player leaves before it can greet again. When ``greet_text`` is
    ``None`` the emitted bytecode is byte-for-byte identical to the examine-only
    build (verified in tests/test_agent_office_ailist.py) — existing agents are
    unchanged.
    """
    code = bytearray()
    code += _cmd_set_self_chrflag(0)
    if spec.chair != 0xFFFF:
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
        # One-shot greeting: show the line, then hold in a "wait until the player
        # leaves GREET_RANGE" loop that re-arms by jumping back to wait_lbl.
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


def agent_office_meeting_terminal_props() -> list:
    """PD consoles at operate / typing chr pads (retail geometry has chairs only)."""
    std_flags = (
        OBJFLAG_FALL
        | OBJFLAG_00000100
        | OBJFLAG_IGNOREFLOORCOLOUR
    )
    return [
        SingleMonitor(
            image=3,
            scale=0x0100,
            model=MODEL_PD_CONSOLE,
            pad=PAD_MEETING_CODE,
            flags=std_flags,
        ),
        SingleMonitor(
            image=3,
            scale=0x0100,
            model=MODEL_PD_CONSOLE,
            pad=PAD_MEETING_RESEARCH,
            flags=std_flags,
        ),
        SingleMonitor(
            image=3,
            scale=0x0100,
            model=MODEL_PD_CONSOLE,
            pad=PAD_MEETING_QA,
            flags=std_flags,
        ),
        SingleMonitor(
            image=3,
            scale=0x0100,
            model=MODEL_PD_CONSOLE,
            pad=PAD_MEETING_OPS_CONSOLE,
            flags=std_flags,
        ),
    ]


def agent_office_std_props() -> list:
    """Tagged interactable console at the meeting-room doorway."""
    # Do not use TOPADBOUNDS here: PAD_DEPO_0062 has a generic 200 u bbox, which
    # setupCreateObject stretches to a huge console. Retail uses PAD_DEPO_00D0 with
    # a console-sized pad; we keep scale 0x0100 only at the meeting-room pad.
    std_flags = (
        OBJFLAG_FALL
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
        (_build_agent_briefing_ailist(spec), base + offset)
        for offset, spec in enumerate(VIRTUAL_AGENTS)
    ]
    chunks.append((_build_console_monitor_ailist(L_DEPO_061), AILIST_CONSOLE_MONITOR))
    return chunks


def pack_agent_office_setup(mapdef) -> bytes:
    """Full MP setup: retail doors + virtual agents + MP simulant init."""
    props = (
        list(mapdef.props)
        + agent_office_depo_doors()
        + agent_office_depo_office_props()
        + agent_office_meeting_terminal_props()
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
            "dataDyne G5 — player spawns on meeting-room corridor pads "
            "(PAD_DEPO_003D / 003E / 008F, Y≈27); eight virtual agents in the holograph "
            "briefing room. Z-target any agent for a status line; use (Z) on the PD console "
            "at the meeting-room doorway."
        ),
        "tableCenter": {"x": TABLE_CENTER_X, "z": TABLE_CENTER_Z},
        "meetingRoomPads": [
            PAD_MEETING_DIRECTOR,
            PAD_MEETING_ORCHESTRATOR,
            PAD_MEETING_RESEARCH,
            PAD_MEETING_CODE,
            PAD_MEETING_QA,
            PAD_MEETING_SECURITY,
            PAD_MEETING_OPS,
            PAD_MEETING_COMMS,
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
                "src/setups/setupdepo.c — all retail doors, mp_unlock + sibling remapped "
                "(closed at init; normal doorTick; open/close via Z)"
            ),
            "models": _door_model_summary(),
        },
        "retailMeetingFurniture": {
            "count": len(meeting_furniture_inventory()),
            "source": (
                "src/setups/setupdepo.c — G5SMALLCHAIR/G5BIGCHAIR @ pads 0x00F2–0x00F8 "
                "+ chair tags 0x4a/0x4b (cinema briefing)"
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
    """Model → count for layout / docs metadata."""
    from collections import Counter

    return dict(Counter(row["model"] for row in depo_door_inventory()))
