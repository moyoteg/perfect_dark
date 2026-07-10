"""Animation parade setup — guards on a data-driven grid, each looping one animation.

Grid slot *N* always plays showcase animation *N* (``parade_showcase()[N-1]``).
A separate **full-tour** guard cycles every named animation sequentially via
chained ailists (label budget limits chunk size).

Guards are split into north-walkable **zones** (≤ ``PARADE_MAX_CHR_PER_ZONE`` per
tile room) so ``cdCollectGeoForCyl`` never overflows its ``propnums[256]`` stack
buffer during spawn or movement.

Showcase set and grid layout come from ``anim_catalog`` (``parade_showcase()``,
``parade_grid_dims()``, ``parade_tour_indices()``).
"""

from __future__ import annotations

import struct

from .anim_catalog import PARADE_MAX_CHR_PER_ZONE, PARADE_TOUR_CHUNK_SIZE, parade_showcase, parade_tour_indices
from .props import Chr

SHOWCASE_ANIMS: list[tuple[str, int]] = parade_showcase()
TOUR_ANIM_INDICES: list[int] = parade_tour_indices()
NUM_GRID_SLOTS = len(SHOWCASE_ANIMS)
NUM_SLOTS = NUM_GRID_SLOTS + 1  # grid + full-tour cycler

# --- Setup / chr constants (match src/include/constants.h) -------------------
SPAWNFLAG_BASICGUARD = 0x00000200
BODY_AREA51GUARD = 0x58
HEAD_RANDOM = -1
GAILIST_IDLE = 0x0000

CHRFLAG0_SKIPSAFETYCHECKS = 0x00002000
CHRFLAG0_HOLD_POSITION = 0x04000000
# Radial ground shadows call gfxRenderRadialShadow → tex pool lookups; disable on
# lab guards to avoid texFindInPool SIGSEGV when many chr render at once.
CHRCFLAG_NOSHADOW = 0x00002000
CHRCFLAG_NEVERSLEEP = 0x00040000
# Do not set CHRCFLAG_NEVERSLEEP: it forces chraiExecute every frame for all
# parade guards (570+) and pegs CPU. Ailists yield + CHRANIMFLAG_SLOWUPDATE suffice.
_PARADE_CHR_FLAGS = CHRCFLAG_NOSHADOW

TEAM_ENEMY = 0x02
SQUADRON_01 = 0x01
CHR_SELF = 0xFD
CHR_P1 = 0x00

AILIST_MP_INIT = 0x1000
AILIST_PARADE_BASE = 0x0401
AILIST_TOUR_BASE = 0x0401 + NUM_GRID_SLOTS

CHR_PARADE_FIRST = 0x50
PAD_PARADE_FIRST = 1
PAD_SPECIAL_TOUR = PAD_PARADE_FIRST + NUM_GRID_SLOTS
CHR_SPECIAL_TOUR = CHR_PARADE_FIRST + NUM_GRID_SLOTS

# chr_do_animation: start/end 0xffff → first frame / natural end (aiChrDoAnimation)
_START_FIRST = 0xFFFF
_END_NATURAL = 0xFFFF
CHRANIMFLAG_SLOWUPDATE = 0x10
CHRANIMFLAG_LOCKPOS = 0x40
# Pad-locked parade guards: slow tick + lock root so abs-trans death anims stay put.
_PARADE_ANIM_FLAGS = CHRANIMFLAG_SLOWUPDATE | CHRANIMFLAG_LOCKPOS


def _align4(data: bytes) -> bytes:
    while len(data) % 4:
        data += b"\x00"
    return data


def _cmd_chr_do_animation(anim: int, *, speed: int = 2) -> bytes:
    return struct.pack(
        ">HHHHBBBb",
        0x000B,
        anim & 0xFFFF,
        _START_FIRST,
        _END_NATURAL,
        _PARADE_ANIM_FLAGS,
        16,
        CHR_SELF,
        speed,
    )


def _cmd_if_chr_stopped(label: int) -> bytes:
    return struct.pack(">HB", 0x0032, label & 0xFF)


def _cmd_label(label: int) -> bytes:
    return struct.pack(">HB", 0x0002, label & 0xFF)


def _cmd_yield() -> bytes:
    return struct.pack(">H", 0x0003)


def _cmd_goto_first(label: int) -> bytes:
    return struct.pack(">HB", 0x0001, label & 0xFF)


def _cmd_endlist() -> bytes:
    return struct.pack(">H", 0x0004)


def _cmd_set_self_chrflag(flag: int) -> bytes:
    return struct.pack(">HI", 0x00A4, flag & 0xFFFFFFFF)


def _cmd_set_ailist(ailist_id: int, chr: int = CHR_SELF) -> bytes:
    return struct.pack(">HBH", 0x0005, chr & 0xFF, ailist_id & 0xFFFF)


def _cmd_if_chr_activated_object(chr: int, tag_id: int, fail_label: int) -> bytes:
    return struct.pack(">HBBB", 0x0063, chr & 0xFF, tag_id & 0xFF, fail_label & 0xFF)


def _cmd_chr_begin_or_end_teleport(pad_id: int, chr: int) -> bytes:
    return struct.pack(">HHB", 0x01BF, pad_id & 0xFFFF, chr & 0xFF)


def _cmd_if_chr_teleport_full_white(chr: int, fail_label: int) -> bytes:
    return struct.pack(">HBB", 0x01C0, fail_label & 0xFF, chr & 0xFF)


def _cmd_if_chr_distance_to_pad_lt(chr: int, distance: int, pad: int, label: int) -> bytes:
    return struct.pack(">H B H H B", 0x0054, chr & 0xFF, int(distance / 10) & 0xFFFF, pad & 0xFFFF, label & 0xFF)


def _cmd_if_chr_distance_to_pad_gt(chr: int, distance: int, pad: int, label: int) -> bytes:
    return struct.pack(">H B H H B", 0x0055, chr & 0xFF, int(distance / 10) & 0xFFFF, pad & 0xFFFF, label & 0xFF)


def _cmd_show_hudmsg(chr: int, text: int) -> bytes:
    return struct.pack(">H B H", 0x00CB, chr & 0xFF, text & 0xFFFF)


def _build_portal_teleport_ailist(mapdef) -> bytes:
    from .anim_props import _HUB_PORTAL_TAGS, _RETURN_PORTAL_TAGS
    code = bytearray()
    outer = 0x10
    code += _cmd_label(outer)
    
    # 1. Generate return portal checks (Wing -> Hub)
    for tag_id, gate in _RETURN_PORTAL_TAGS:
        fail_lbl = (tag_id + 0x40) & 0xFF
        wait_lbl = (tag_id + 0x50) & 0xFF
        success_lbl = (tag_id + 0x60) & 0xFF
        
        code += _cmd_if_chr_activated_object(CHR_P1, tag_id, fail_lbl)
        code += _cmd_chr_begin_or_end_teleport(0, CHR_P1)  # Return to player spawn pad 0
        code += _cmd_label(wait_lbl)
        code += _cmd_if_chr_teleport_full_white(CHR_P1, success_lbl)
        code += _cmd_yield()
        code += _cmd_goto_first(wait_lbl)
        code += _cmd_label(success_lbl)
        code += _cmd_goto_first(outer)
        code += _cmd_label(fail_lbl)

    # 2. Generate hub portal checks (Hub -> Wing)
    portal_landing_pads = getattr(mapdef, "portal_landing_pads", {})
    
    for tag_id, sign in _HUB_PORTAL_TAGS:
        fail_lbl = (tag_id + 0x10) & 0xFF
        compass = sign["compass"]
        target_pad = portal_landing_pads.get(compass, 0)
        
        wait_lbl = (tag_id + 0x20) & 0xFF
        success_lbl = (tag_id + 0x30) & 0xFF
        
        # Operation check
        code += _cmd_if_chr_activated_object(CHR_P1, tag_id, fail_lbl)
        code += _cmd_chr_begin_or_end_teleport(target_pad, CHR_P1)
        code += _cmd_label(wait_lbl)
        code += _cmd_if_chr_teleport_full_white(CHR_P1, success_lbl)
        code += _cmd_yield()
        code += _cmd_goto_first(wait_lbl)
        code += _cmd_label(success_lbl)
        code += _cmd_goto_first(outer)
        code += _cmd_label(fail_lbl)
        
    code += _cmd_yield()
    code += _cmd_goto_first(outer)
    code += _cmd_endlist()
    return bytes(code)


def _build_portal_message_ailist(mapdef) -> bytes:
    from .anim_props import _HUB_PORTAL_TAGS
    code = bytearray()
    outer = 0x10
    code += _cmd_label(outer)
    
    portal_entrance_pads = getattr(mapdef, "portal_entrance_pads", {})
    
    for tag_id, sign in _HUB_PORTAL_TAGS:
        compass = sign["compass"]
        ent_pad = portal_entrance_pads.get(compass, 0)
        near_lbl = (tag_id + 0x40) & 0xFF
        
        # Proximity check
        code += _cmd_if_chr_distance_to_pad_lt(CHR_P1, 250, ent_pad, near_lbl)
        
    code += _cmd_yield()
    code += _cmd_goto_first(outer)
    
    # Proximity message display sub-routines
    for i, (tag_id, sign) in enumerate(_HUB_PORTAL_TAGS):
        compass = sign["compass"]
        ent_pad = portal_entrance_pads.get(compass, 0)
        near_lbl = (tag_id + 0x40) & 0xFF
        loop_lbl = (tag_id + 0x50) & 0xFF
        text_id = 127 + i
        
        code += _cmd_label(near_lbl)
        code += _cmd_show_hudmsg(CHR_P1, text_id)
        code += _cmd_label(loop_lbl)
        code += _cmd_yield()
        code += _cmd_if_chr_distance_to_pad_lt(CHR_P1, 350, ent_pad, loop_lbl)
        code += _cmd_goto_first(outer)
        
    code += _cmd_endlist()
    return bytes(code)


def _build_single_anim_loop_ailist(anim_index: int, *, never_sleep: bool = False) -> bytes:
    """One guard's loop — replay the same animation forever."""
    code = bytearray()
    flags = _PARADE_CHR_FLAGS
    if never_sleep:
        flags |= CHRCFLAG_NEVERSLEEP
    code += _cmd_set_self_chrflag(flags)

    outer = 0x10
    wait_lbl = 0x11
    next_lbl = 0x12

    code += _cmd_label(outer)
    code += _cmd_chr_do_animation(anim_index)
    code += _cmd_label(wait_lbl)
    code += _cmd_if_chr_stopped(next_lbl)
    code += _cmd_yield()
    code += _cmd_goto_first(wait_lbl)
    code += _cmd_label(next_lbl)
    code += _cmd_goto_first(outer)
    code += _cmd_endlist()
    return bytes(code)


def _build_tour_chunk_ailist(
    anim_indices: list[int],
    *,
    next_ailist: int | None,
    loop_ailist: int,
    never_sleep: bool = False,
) -> bytes:
    """Sequential anim chain; jumps to *next_ailist* or loops to *loop_ailist*."""
    code = bytearray()
    flags = _PARADE_CHR_FLAGS
    if never_sleep:
        flags |= CHRCFLAG_NEVERSLEEP
    code += _cmd_set_self_chrflag(flags)

    outer = 0x10
    code += _cmd_label(outer)

    for step, anim in enumerate(anim_indices):
        wait_lbl = 0x20 + step
        next_lbl = 0x30 + step
        code += _cmd_chr_do_animation(anim)
        code += _cmd_label(wait_lbl)
        code += _cmd_if_chr_stopped(next_lbl)
        code += _cmd_yield()
        code += _cmd_goto_first(wait_lbl)
        code += _cmd_label(next_lbl)

    if next_ailist is not None:
        code += _cmd_set_ailist(next_ailist)
    else:
        code += _cmd_set_ailist(loop_ailist)
    code += _cmd_endlist()
    return bytes(code)


def _tour_ailist_chunks() -> list[tuple[bytes, int]]:
    """Split full tour into chained ailists (u8 label budget per chunk)."""
    chunks: list[list[int]] = []
    indices = TOUR_ANIM_INDICES
    size = max(1, PARADE_TOUR_CHUNK_SIZE)
    for offset in range(0, len(indices), size):
        chunks.append(indices[offset : offset + size])

    if not chunks:
        chunks = [[0]]

    result: list[tuple[bytes, int]] = []
    first_id = AILIST_TOUR_BASE
    for i, chunk in enumerate(chunks):
        aid = AILIST_TOUR_BASE + i
        next_id = AILIST_TOUR_BASE + i + 1 if i + 1 < len(chunks) else None
        code = _build_tour_chunk_ailist(
            chunk,
            next_ailist=next_id,
            loop_ailist=first_id,
            never_sleep=(i == 0),
        )
        result.append((code, aid))
    return result


def _mp_init_ailist(mapdef=None) -> bytes:
    return bytes([
        0x01, 0x85,
        0x01, 0x45,
        0x01, 0x46,
        0x00, 0x05, 0xFD, 0x00, 0x00,
        0x00, 0x04,
    ])


def _chr_prop(*, chrnum: int, pad: int, ailist: int) -> Chr:
    return Chr(
        spawnflags=SPAWNFLAG_BASICGUARD,
        chrnum=chrnum,
        pad=pad,
        body=BODY_AREA51GUARD,
        head=0xFFFF,  # HEAD_RANDOM
        function=ailist,
        padpreset=0xFFFF,
        chrpreset=0xFFFF,
        hear_scale=1000,
        view_dist=100,
        flags=CHRFLAG0_SKIPSAFETYCHECKS | CHRFLAG0_HOLD_POSITION,
        flags2=0,
        team=TEAM_ENEMY,
        squadron=SQUADRON_01,
        chair=0xFFFF,
        convtalk=0,
        tude=0,
        naturalanim=0,
        yvisang=0,
        teamscandist=0,
    )


def parade_chr_props(mapdef) -> list[Chr]:
    """Grid guards (one anim each) plus the full-tour cycler."""
    props: list[Chr] = []
    max_pads = len(mapdef.pads)
    for slot in range(NUM_GRID_SLOTS):
        pad_idx = PAD_PARADE_FIRST + slot
        if pad_idx >= max_pads:
            break
        props.append(
            _chr_prop(
                chrnum=CHR_PARADE_FIRST + slot,
                pad=pad_idx,
                ailist=AILIST_PARADE_BASE + slot,
            )
        )
    if PAD_SPECIAL_TOUR < max_pads:
        tour_chunks = _tour_ailist_chunks()
        tour_entry = tour_chunks[0][1] if tour_chunks else AILIST_TOUR_BASE
        props.append(
            _chr_prop(
                chrnum=CHR_SPECIAL_TOUR,
                pad=PAD_SPECIAL_TOUR,
                ailist=tour_entry,
            )
        )
    return props


def pack_anim_parade_setup(mapdef) -> bytes:
    """Full setup binary: grid loop ailists + chained tour ailists + character gallery + portals + MP init."""
    from .anim_characters import character_ailist_chunks, character_chr_props, _character_pad_first
    from .anim_catalog import hub_signpost_entries
    from .anim_characters import character_ailist_base

    # Portal trigger characters helper
    def _portal_chr_props() -> list[Chr]:
        from .anim_characters import MAIN_CHARACTER_ENTRIES, _character_chr_first
        chr_id = _character_chr_first() + len(MAIN_CHARACTER_ENTRIES)
        aid = character_ailist_base() + len(MAIN_CHARACTER_ENTRIES)
        pad_id = getattr(mapdef, "portal_guard_pad", None)
        if pad_id is None or pad_id >= len(mapdef.pads):
            return []
        return [
            _chr_prop(
                chrnum=chr_id,
                pad=pad_id,
                ailist=aid,
            ),
            _chr_prop(
                chrnum=chr_id + 1,
                pad=pad_id,
                ailist=aid + 1,
            )
        ]

    # Portal AI lists helper
    def _portal_ailist_chunks() -> list[tuple[bytes, int]]:
        from .anim_characters import MAIN_CHARACTER_ENTRIES
        aid = character_ailist_base() + len(MAIN_CHARACTER_ENTRIES)
        code_teleport = _build_portal_teleport_ailist(mapdef)
        code_message = _build_portal_message_ailist(mapdef)
        return [
            (code_teleport, aid),
            (code_message, aid + 1)
        ]

    char_props = []
    if len(mapdef.pads) > _character_pad_first():
        char_props = character_chr_props()

    props = list(mapdef.props) + parade_chr_props(mapdef) + char_props + _portal_chr_props()
    props_bin = b"".join(p.pack() for p in props) + struct.pack(">I", 0x34)

    intro_bin = b"".join(cmd.pack() for cmd in mapdef.intro) + struct.pack(">I", 12)

    ailist_chunks: list[tuple[bytes, int]] = [(_mp_init_ailist(mapdef), AILIST_MP_INIT)]
    for slot in range(NUM_GRID_SLOTS):
        if PAD_PARADE_FIRST + slot >= len(mapdef.pads):
            break
        anim_index = SHOWCASE_ANIMS[slot][1]
        ailist_chunks.append(
            (_build_single_anim_loop_ailist(anim_index), AILIST_PARADE_BASE + slot)
        )
    if PAD_SPECIAL_TOUR < len(mapdef.pads):
        ailist_chunks.extend(_tour_ailist_chunks())
    if len(mapdef.pads) > _character_pad_first():
        ailist_chunks.extend(character_ailist_chunks())
    pad_id = getattr(mapdef, "portal_guard_pad", None)
    if pad_id is not None and pad_id < len(mapdef.pads):
        ailist_chunks.extend(_portal_ailist_chunks())

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
