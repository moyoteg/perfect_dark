"""Main-character gallery for Animation Lab — static chr mannequins on distinct bodies.

Separate from the animation parade (district guards all use ``BODY_AREA51GUARD``).
Each entry uses retail ``BODY_*`` / ``HEAD_*`` from ``constants.h`` and loops a
neutral stand animation (``ANIM_TWO_GUN_HOLD`` by default).

Pads and chrnums are allocated *after* parade grid + tour + all StdObject props.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .anim_catalog import (
    PARADE_CHARACTERS_CENTER_X,
    PARADE_CHARACTERS_CENTER_Z,
    PARADE_CHARACTERS_COLOUR,
    PARADE_CHARACTERS_COLS,
    PARADE_CHARACTERS_HALF,
    PARADE_CHARACTERS_PITCH,
    PARADE_CHARACTERS_ROOM,
    _hex_to_floor_colour,
)
from .anim_parade import (
    AILIST_TOUR_BASE,
    CHR_SPECIAL_TOUR,
    SPAWNFLAG_BASICGUARD,
    TEAM_ENEMY,
    SQUADRON_01,
    _build_single_anim_loop_ailist,
    _tour_ailist_chunks,
)
from .anim_props import PARADE_PROPS_PAD_FIRST, all_parade_prop_specs
from .core import MapDef
from .props import Chr

# --- Body / head IDs (src/include/constants.h) --------------------------------
BODY_DARK_COMBAT = 0x56
BODY_DARK_TRENCH = 0x62
BODY_DARK_FROCK = 0x61
BODY_DARKSNOW = 0x89
BODY_DARKLAB = 0x8A
BODY_DARK_AF1 = 0x86
BODY_ELVIS1 = 0x57
BODY_THEKING = 0x67
BODY_CARRINGTON = 0x5A
BODY_JONATHAN = 0x91
BODY_CASSANDRA = 0x66
BODY_DRCAROLL = 0x6B
BODY_MAIAN_SOLDIER = 0x83
BODY_TRENT = 0x5D
BODY_MRBLONDE = 0x5B
BODY_DDSHOCK = 0x5E
BODY_SKEDAR = 0x5C
BODY_SKEDARKING = 0x93
BODY_PRESIDENT = 0x79
BODY_BIOTECH = 0x71
BODY_AREA51GUARD = 0x58
BODY_NSA_LACKEY = 0x7C
BODY_G5_GUARD = 0x7F
BODY_PELAGIC_GUARD = 0x80

HEAD_RANDOM = 0xFFFF
HEAD_DARK_COMBAT = 0x04
HEAD_DARK_FROCK = 0x0C
HEAD_DARK_SNOW = 0x3C
HEAD_ELVIS = 0x05
HEAD_THEKING = 0x0F
HEAD_CARRINGTON = 0x07
HEAD_JONATHAN = 0x28
HEAD_CASSANDRA = 0x0E
HEAD_MAIAN_S = 0x29
HEAD_TRENT = 0x09
HEAD_MRBLONDE = 0x08
HEAD_DDSHOCK = 0x0A
HEAD_PRESIDENT = 0x3D
HEAD_BIOTECH = 0x1D

CHRFLAG0_SKIPSAFETYCHECKS = 0x00002000
CHRFLAG0_HOLD_POSITION = 0x04000000

# ANIM_TWO_GUN_HOLD — looping weapon-hold idle used by simulant stand poses.
_ANIM_IDLE_STAND = 1

PARADE_CHARACTERS_FLOOR_COLOUR = _hex_to_floor_colour(PARADE_CHARACTERS_COLOUR)


@dataclass(frozen=True)
class CharacterGalleryEntry:
    """One mannequin in the character gallery wing."""

    id: str
    label: str
    body: int
    head: int
    group: str
    hint: str
    idle_anim: int = _ANIM_IDLE_STAND


# Canonical story / MP roster — Joanna outfits, allies, villains, faction guards.
MAIN_CHARACTER_ENTRIES: tuple[CharacterGalleryEntry, ...] = (
    CharacterGalleryEntry(
        "joanna_combat",
        "Joanna — combat",
        BODY_DARK_COMBAT,
        HEAD_DARK_COMBAT,
        "joanna",
        "Default Joanna Dark combat suit",
    ),
    CharacterGalleryEntry(
        "joanna_trench",
        "Joanna — trench",
        BODY_DARK_TRENCH,
        HEAD_DARK_COMBAT,
        "joanna",
        "CI trench coat disguise",
    ),
    CharacterGalleryEntry(
        "joanna_frock",
        "Joanna — frock",
        BODY_DARK_FROCK,
        HEAD_DARK_FROCK,
        "joanna",
        "Villa / social frock outfit",
    ),
    CharacterGalleryEntry(
        "joanna_snow",
        "Joanna — snow",
        BODY_DARKSNOW,
        HEAD_DARK_SNOW,
        "joanna",
        "Alaska snow gear",
    ),
    CharacterGalleryEntry(
        "joanna_lab",
        "Joanna — lab",
        BODY_DARKLAB,
        HEAD_DARK_COMBAT,
        "joanna",
        "Infiltration lab coat",
    ),
    CharacterGalleryEntry(
        "joanna_af1",
        "Joanna — AF1",
        BODY_DARK_AF1,
        HEAD_DARK_COMBAT,
        "joanna",
        "Air Force One mission outfit",
    ),
    CharacterGalleryEntry(
        "elvis",
        "Elvis",
        BODY_ELVIS1,
        HEAD_ELVIS,
        "allies",
        "Maian protector Elvis",
    ),
    CharacterGalleryEntry(
        "the_king",
        "The King",
        BODY_THEKING,
        HEAD_THEKING,
        "allies",
        "Elvis as The King",
    ),
    CharacterGalleryEntry(
        "carrington",
        "Carrington",
        BODY_CARRINGTON,
        HEAD_CARRINGTON,
        "allies",
        "Daniel Carrington",
    ),
    CharacterGalleryEntry(
        "jonathan",
        "Jonathan",
        BODY_JONATHAN,
        HEAD_JONATHAN,
        "allies",
        "Jonathan Darkstein",
    ),
    CharacterGalleryEntry(
        "cassandra",
        "Cassandra",
        BODY_CASSANDRA,
        HEAD_CASSANDRA,
        "allies",
        "Cassandra de Vries",
    ),
    CharacterGalleryEntry(
        "dr_caroll",
        "Dr. Caroll",
        BODY_DRCAROLL,
        HEAD_RANDOM,
        "allies",
        "Dr. Caroll (datadyne AI)",
    ),
    CharacterGalleryEntry(
        "maian",
        "Maian soldier",
        BODY_MAIAN_SOLDIER,
        HEAD_MAIAN_S,
        "allies",
        "Maian military",
    ),
    CharacterGalleryEntry(
        "trent",
        "Trent Easton",
        BODY_TRENT,
        HEAD_TRENT,
        "allies",
        "Trent Easton",
    ),
    CharacterGalleryEntry(
        "mr_blonde",
        "Mr. Blonde",
        BODY_MRBLONDE,
        HEAD_MRBLONDE,
        "villains",
        "Trent's enforcer",
    ),
    CharacterGalleryEntry(
        "dd_shock",
        "DD Shock",
        BODY_DDSHOCK,
        HEAD_DDSHOCK,
        "villains",
        "dataDyne shock trooper",
    ),
    CharacterGalleryEntry(
        "skedar",
        "Skedar",
        BODY_SKEDAR,
        HEAD_RANDOM,
        "villains",
        "Skedar warrior (head embedded in body rig)",
    ),
    CharacterGalleryEntry(
        "skedar_king",
        "Skedar King",
        BODY_SKEDARKING,
        HEAD_RANDOM,
        "villains",
        "Skedar ruler",
    ),
    CharacterGalleryEntry(
        "president",
        "President",
        BODY_PRESIDENT,
        HEAD_PRESIDENT,
        "villains",
        "US President",
    ),
    CharacterGalleryEntry(
        "biotech",
        "Biotech",
        BODY_BIOTECH,
        HEAD_BIOTECH,
        "villains",
        "dataDyne biotech guard",
    ),
    CharacterGalleryEntry(
        "a51_guard",
        "Area 51 guard",
        BODY_AREA51GUARD,
        HEAD_RANDOM,
        "guards",
        "Area 51 security",
    ),
    CharacterGalleryEntry(
        "nsa_lackey",
        "NSA lackey",
        BODY_NSA_LACKEY,
        HEAD_RANDOM,
        "guards",
        "NSA operative",
    ),
    CharacterGalleryEntry(
        "g5_guard",
        "G5 guard",
        BODY_G5_GUARD,
        HEAD_RANDOM,
        "guards",
        "G5 Building security",
    ),
    CharacterGalleryEntry(
        "pelagic_guard",
        "Pelagic guard",
        BODY_PELAGIC_GUARD,
        HEAD_RANDOM,
        "guards",
        "Deep sea lab guard",
    ),
)


def _character_pad_first() -> int:
    """First pad index after parade tour + all static props."""
    return PARADE_PROPS_PAD_FIRST + len(all_parade_prop_specs())


def _character_chr_first() -> int:
    """First chr slot after parade grid guards + full-tour cycler."""
    return CHR_SPECIAL_TOUR + 1


def character_ailist_base() -> int:
    """First ailist id for character idle loops (after parade + tour chains)."""
    tour = _tour_ailist_chunks()
    if tour:
        return tour[-1][1] + 1
    return AILIST_TOUR_BASE


def _grid_xy(index: int) -> tuple[float, float]:
    """Pack gallery entries in a cols×rows grid centred on the wing."""
    col = index % PARADE_CHARACTERS_COLS
    row = index // PARADE_CHARACTERS_COLS
    rows = max(1, (len(MAIN_CHARACTER_ENTRIES) + PARADE_CHARACTERS_COLS - 1) // PARADE_CHARACTERS_COLS)
    x = PARADE_CHARACTERS_CENTER_X + (col - (PARADE_CHARACTERS_COLS - 1) / 2.0) * PARADE_CHARACTERS_PITCH
    z = PARADE_CHARACTERS_CENTER_Z + (row - (rows - 1) / 2.0) * PARADE_CHARACTERS_PITCH
    return x, z


def character_gallery_markers(*, pad_y: float = 10.0) -> list[dict[str, Any]]:
    """UI / layout markers for each gallery chr."""
    pad_first = _character_pad_first()
    chr_first = _character_chr_first()
    rows: list[dict[str, Any]] = []
    for i, entry in enumerate(MAIN_CHARACTER_ENTRIES):
        x, z = _grid_xy(i)
        rows.append(
            {
                "pad": pad_first + i,
                "chr": chr_first + i,
                "chrHex": f"0x{chr_first + i:02X}",
                "id": entry.id,
                "label": entry.label,
                "body": entry.body,
                "bodyHex": f"0x{entry.body:02X}",
                "head": entry.head,
                "headHex": "random" if entry.head == HEAD_RANDOM else f"0x{entry.head:02X}",
                "group": entry.group,
                "x": x,
                "z": z,
                "y": pad_y,
                "room": PARADE_CHARACTERS_ROOM,
                "idleAnim": entry.idle_anim,
                "hint": entry.hint,
                "floorColour": PARADE_CHARACTERS_FLOOR_COLOUR,
            }
        )
    return rows


def character_gallery_layout_payload() -> dict[str, Any]:
    """Character gallery summary for docs and ``anim_lab.html``."""
    markers = character_gallery_markers()
    by_group: dict[str, list[dict[str, Any]]] = {}
    for m in markers:
        by_group.setdefault(str(m["group"]), []).append(m)
    return {
        "id": "characters",
        "label": "Character gallery",
        "centerX": PARADE_CHARACTERS_CENTER_X,
        "centerZ": PARADE_CHARACTERS_CENTER_Z,
        "half": PARADE_CHARACTERS_HALF,
        "floorColour": PARADE_CHARACTERS_FLOOR_COLOUR,
        "pitch": PARADE_CHARACTERS_PITCH,
        "cols": PARADE_CHARACTERS_COLS,
        "count": len(markers),
        "characters": markers,
        "byGroup": by_group,
        "padFirst": _character_pad_first(),
        "chrFirst": _character_chr_first(),
        "chrFirstHex": f"0x{_character_chr_first():02X}",
    }


def _chr_prop(*, chrnum: int, pad: int, body: int, head: int, ailist: int) -> Chr:
    return Chr(
        spawnflags=SPAWNFLAG_BASICGUARD,
        chrnum=chrnum,
        pad=pad,
        body=body,
        head=head,
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


def character_chr_props() -> list[Chr]:
    """Static gallery mannequins — one per ``MAIN_CHARACTER_ENTRIES`` row."""
    pad_first = _character_pad_first()
    chr_first = _character_chr_first()
    base_ailist = character_ailist_base()
    props: list[Chr] = []
    for i, entry in enumerate(MAIN_CHARACTER_ENTRIES):
        props.append(
            _chr_prop(
                chrnum=chr_first + i,
                pad=pad_first + i,
                body=entry.body,
                head=entry.head,
                ailist=base_ailist + i,
            )
        )
    return props


def character_ailist_chunks() -> list[tuple[bytes, int]]:
    """Per-character idle loop ailists (placed after tour chain)."""
    base = character_ailist_base()
    chunks: list[tuple[bytes, int]] = []
    for i, entry in enumerate(MAIN_CHARACTER_ENTRIES):
        code = _build_single_anim_loop_ailist(entry.idle_anim)
        chunks.append((code, base + i))
    return chunks


def add_character_gallery_pads(mapdef: MapDef, *, pad_y: float = 10.0) -> None:
    """Register gallery pads on *mapdef* (chr props come from ``character_chr_props()``)."""
    pad_first = _character_pad_first()
    for i, entry in enumerate(MAIN_CHARACTER_ENTRIES):
        x, z = _grid_xy(i)
        mapdef.add_pad(
            index=pad_first + i,
            x=x,
            y=pad_y,
            z=z,
            room=PARADE_CHARACTERS_ROOM,
            dir_x=0.0,
            dir_y=0.0,
            dir_z=-1.0,
        )
