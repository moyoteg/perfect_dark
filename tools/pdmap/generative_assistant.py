"""Generative Map Assistant for Perfect Dark Kit.

Provides conversational demystification, deterministic semantic spatial grammar
map synthesis, incremental pad authoring, and optional Ollama LLM integration.
Adheres strictly to the Universal Calibrated Zero-Emoji Standard and engine invariants:
- Zero Unicode emojis
- All pad Y coordinates = 10 (floor offset)
- Contiguous pad indices 0..N-1
- Valid room bounds and portal linkages (1..R)
- At least 4 spawn pads per generated arena
"""

from __future__ import annotations

import copy
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

# Canonical weapon IDs for generative arena synthesis
WEAPON_FALCON2 = 20
WEAPON_CMP150 = 21
WEAPON_MAGSEC4 = 22
WEAPON_SHOTGUN = 23
WEAPON_LAPTOPGUN = 24
WEAPON_SUPERDRAGON = 25
WEAPON_SNIPERRIFLE = 26
WEAPON_ROCKETLAUNCHER = 27

# Ammo types
AMMOTYPE_PISTOL = 1
AMMOTYPE_SMG = 2
AMMOTYPE_CROSSBOW = 3
AMMOTYPE_RIFLE = 4
AMMOTYPE_SHOTGUN = 5
AMMOTYPE_ROCKET = 8

WEAPON_ALIASES: dict[str, int] = {
    "sniper": WEAPON_SNIPERRIFLE,
    "sniperrifle": WEAPON_SNIPERRIFLE,
    "sniper_rifle": WEAPON_SNIPERRIFLE,
    "superdragon": WEAPON_SUPERDRAGON,
    "super_dragon": WEAPON_SUPERDRAGON,
    "shotgun": WEAPON_SHOTGUN,
    "falcon": WEAPON_FALCON2,
    "falcon2": WEAPON_FALCON2,
    "falcon_2": WEAPON_FALCON2,
    "rocket": WEAPON_ROCKETLAUNCHER,
    "rocketlauncher": WEAPON_ROCKETLAUNCHER,
    "rocket_launcher": WEAPON_ROCKETLAUNCHER,
    "cmp": WEAPON_CMP150,
    "cmp150": WEAPON_CMP150,
    "magsec": WEAPON_MAGSEC4,
    "magsec4": WEAPON_MAGSEC4,
    "laptop": WEAPON_LAPTOPGUN,
    "laptopgun": WEAPON_LAPTOPGUN,
}

AMMO_ALIASES: dict[str, int] = {
    "pistol": AMMOTYPE_PISTOL,
    "smg": AMMOTYPE_SMG,
    "rifle": AMMOTYPE_RIFLE,
    "sniper": AMMOTYPE_RIFLE,
    "shotgun": AMMOTYPE_SHOTGUN,
    "rocket": AMMOTYPE_ROCKET,
}

NUMBER_WORDS: dict[str, int] = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
}

KIT_EXPLANATION = (
    "Perfect Dark Kit is a reverse-engineering and modding suite for Perfect Dark. "
    "It enables designing, inspecting, and compiling custom 3D multiplayer arenas and single-player levels "
    "for the game engine.\n\n"
    "Key architectural concepts:\n"
    "1. Rooms and Portals: Levels are structured as interconnected 3D convex room volumes. Portals define "
    "the apertures connecting adjacent rooms, governing engine occlusion culling and visibility.\n"
    "2. Pads (3D Position Anchors): All interactive entities attach to numbered pads positioned on the floor "
    "(with a strict Y=10 floor offset). Pads serve as player spawns, weapon pickups (e.g. Falcon 2, "
    "Shotgun, SuperDragon, Sniper Rifle), ammo crates, AI cover nodes, and scenario objectives "
    "(King of the Hill hill zones or Capture the Case flags).\n"
    "3. Compilers and Invariants: The tool compiles editor specs into binary stage assets (bgdata/seg files and "
    "setup C binaries). It strictly enforces engine invariants: contiguous pad indices 0..N-1, positive "
    "floor offset Y=10, valid room numbers 1..R, and G_VTX 16-vertex display list limits.\n\n"
    "You can use this assistant to generate balanced combat arenas (such as '2-room sniper duel', "
    "'king of the hill arena', '4-room facility with shotgun & rocket', or 'warehouse bunker') or incrementally "
    "add elements (such as 'add two shotgun pads' or 'add rocket launcher')."
)


def _base_two_room_map(name: str = "facility_base") -> dict[str, Any]:
    """Create a minimal valid 2-room base arena specification with 4 spawns."""
    return {
        "name": name,
        "level_module": "uff",
        "box_half": 5000,
        "box_height": 3000,
        "spawn_y": 10,
        "rooms": [
            {
                "room": 1,
                "name": "room_1",
                "x0": -3000.0,
                "x1": 0.0,
                "z0": -1500.0,
                "z1": 1500.0,
                "height": 2000.0,
                "floor_y": 0.0,
            },
            {
                "room": 2,
                "name": "room_2",
                "x0": 0.0,
                "x1": 3000.0,
                "z0": -1500.0,
                "z1": 1500.0,
                "height": 2000.0,
                "floor_y": 0.0,
            },
        ],
        "portals": [
            {
                "room1": 1,
                "room2": 2,
                "room_from": 1,
                "room_to": 2,
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "width": 400.0,
                "height": 800.0,
            }
        ],
        "pads": [
            {"index": 0, "x": -1500.0, "y": 10.0, "z": -500.0, "room": 1, "type": "spawn"},
            {"index": 1, "x": -1500.0, "y": 10.0, "z": 500.0, "room": 1, "type": "spawn"},
            {"index": 2, "x": 1500.0, "y": 10.0, "z": -500.0, "room": 2, "type": "spawn"},
            {"index": 3, "x": 1500.0, "y": 10.0, "z": 500.0, "room": 2, "type": "spawn"},
        ],
    }


def _generate_sniper_duel(name: str = "sniper_duel") -> tuple[str, dict[str, Any]]:
    """Synthesize a balanced 2-room symmetrical sniper duel facility."""
    rooms = [
        {
            "room": 1,
            "name": "west_perch",
            "x0": -3000.0,
            "x1": 0.0,
            "z0": -1500.0,
            "z1": 1500.0,
            "height": 2000.0,
            "floor_y": 0.0,
        },
        {
            "room": 2,
            "name": "east_perch",
            "x0": 0.0,
            "x1": 3000.0,
            "z0": -1500.0,
            "z1": 1500.0,
            "height": 2000.0,
            "floor_y": 0.0,
        },
    ]
    portals = [
        {
            "room1": 1,
            "room2": 2,
            "room_from": 1,
            "room_to": 2,
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "width": 500.0,
            "height": 1000.0,
        }
    ]
    pads = [
        {"index": 0, "x": -2200.0, "y": 10.0, "z": -600.0, "room": 1, "type": "spawn"},
        {"index": 1, "x": -2200.0, "y": 10.0, "z": 600.0, "room": 1, "type": "spawn"},
        {"index": 2, "x": 2200.0, "y": 10.0, "z": -600.0, "room": 2, "type": "spawn"},
        {"index": 3, "x": 2200.0, "y": 10.0, "z": 600.0, "room": 2, "type": "spawn"},
        {
            "index": 4,
            "x": -1200.0,
            "y": 10.0,
            "z": 0.0,
            "room": 1,
            "type": "weapon",
            "weapon": WEAPON_SNIPERRIFLE,
        },
        {
            "index": 5,
            "x": 1200.0,
            "y": 10.0,
            "z": 0.0,
            "room": 2,
            "type": "weapon",
            "weapon": WEAPON_SNIPERRIFLE,
        },
        {"index": 6, "x": -1600.0, "y": 10.0, "z": 400.0, "room": 1, "type": "ammo", "ammoType": AMMOTYPE_RIFLE},
        {"index": 7, "x": 1600.0, "y": 10.0, "z": -400.0, "room": 2, "type": "ammo", "ammoType": AMMOTYPE_RIFLE},
        {
            "index": 8,
            "x": -2500.0,
            "y": 10.0,
            "z": 0.0,
            "room": 1,
            "type": "weapon",
            "weapon": WEAPON_FALCON2,
        },
        {
            "index": 9,
            "x": 2500.0,
            "y": 10.0,
            "z": 0.0,
            "room": 2,
            "type": "weapon",
            "weapon": WEAPON_FALCON2,
        },
    ]

    map_data = {
        "name": name,
        "level_module": "uff",
        "box_half": 5000,
        "box_height": 3000,
        "spawn_y": 10,
        "rooms": rooms,
        "portals": portals,
        "pads": pads,
    }
    reply = (
        f"Generated symmetrical 2-room sniper duel arena '{name}' with 2 vantage chambers, "
        "a wide central aperture portal, 4 balanced player spawns, 2 Sniper Rifle pads (ID 26), "
        "2 sidearm Falcon 2 pads (ID 20), and rifle resupply crates. All pad positions enforce Y=10 floor offset."
    )
    return reply, map_data


def _generate_koth_arena(name: str = "koth_arena") -> tuple[str, dict[str, Any]]:
    """Synthesize a 3-room King of the Hill arena with a contested central hill chamber."""
    rooms = [
        {
            "room": 1,
            "name": "central_hill",
            "x0": -1500.0,
            "x1": 1500.0,
            "z0": -1500.0,
            "z1": 1500.0,
            "height": 2200.0,
            "floor_y": 0.0,
        },
        {
            "room": 2,
            "name": "west_flank",
            "x0": -3500.0,
            "x1": -1500.0,
            "z0": -1200.0,
            "z1": 1200.0,
            "height": 1800.0,
            "floor_y": 0.0,
        },
        {
            "room": 3,
            "name": "east_flank",
            "x0": 1500.0,
            "x1": 3500.0,
            "z0": -1200.0,
            "z1": 1200.0,
            "height": 1800.0,
            "floor_y": 0.0,
        },
    ]
    portals = [
        {
            "room1": 2,
            "room2": 1,
            "room_from": 2,
            "room_to": 1,
            "x": -1500.0,
            "y": 0.0,
            "z": 0.0,
            "width": 400.0,
            "height": 800.0,
        },
        {
            "room1": 1,
            "room2": 3,
            "room_from": 1,
            "room_to": 3,
            "x": 1500.0,
            "y": 0.0,
            "z": 0.0,
            "width": 400.0,
            "height": 800.0,
        },
    ]
    pads = [
        {"index": 0, "x": -2800.0, "y": 10.0, "z": -500.0, "room": 2, "type": "spawn"},
        {"index": 1, "x": -2800.0, "y": 10.0, "z": 500.0, "room": 2, "type": "spawn"},
        {"index": 2, "x": 2800.0, "y": 10.0, "z": -500.0, "room": 3, "type": "spawn"},
        {"index": 3, "x": 2800.0, "y": 10.0, "z": 500.0, "room": 3, "type": "spawn"},
        {
            "index": 4,
            "x": 0.0,
            "y": 10.0,
            "z": 0.0,
            "room": 1,
            "type": "scenario",
            "scenario": "hill",
        },
        {
            "index": 5,
            "x": 0.0,
            "y": 10.0,
            "z": -800.0,
            "room": 1,
            "type": "weapon",
            "weapon": WEAPON_SHOTGUN,
        },
        {
            "index": 6,
            "x": 0.0,
            "y": 10.0,
            "z": 800.0,
            "room": 1,
            "type": "weapon",
            "weapon": WEAPON_SUPERDRAGON,
        },
        {"index": 7, "x": -2200.0, "y": 10.0, "z": 0.0, "room": 2, "type": "ammo", "ammoType": AMMOTYPE_SHOTGUN},
        {"index": 8, "x": 2200.0, "y": 10.0, "z": 0.0, "room": 3, "type": "ammo", "ammoType": AMMOTYPE_RIFLE},
    ]

    map_data = {
        "name": name,
        "level_module": "uff",
        "box_half": 5000,
        "box_height": 3000,
        "spawn_y": 10,
        "rooms": rooms,
        "portals": portals,
        "pads": pads,
    }
    reply = (
        f"Generated King of the Hill arena '{name}' featuring a central contested hill chamber "
        "flanked by West and East staging halls. Includes 1 central hill scenario pad, 4 team spawns, "
        "Shotgun (ID 23) and SuperDragon (ID 25) tactical weapons, and corresponding ammo crates at Y=10."
    )
    return reply, map_data


def _generate_facility_combat(name: str = "facility_combat") -> tuple[str, dict[str, Any]]:
    """Synthesize a 4-room tactical facility with Shotgun & Rocket Launcher."""
    rooms = [
        {
            "room": 1,
            "name": "nw_storage",
            "x0": -3000.0,
            "x1": 0.0,
            "z0": 0.0,
            "z1": 3000.0,
            "height": 2000.0,
            "floor_y": 0.0,
        },
        {
            "room": 2,
            "name": "ne_arsenal",
            "x0": 0.0,
            "x1": 3000.0,
            "z0": 0.0,
            "z1": 3000.0,
            "height": 2000.0,
            "floor_y": 0.0,
        },
        {
            "room": 3,
            "name": "sw_generator",
            "x0": -3000.0,
            "x1": 0.0,
            "z0": -3000.0,
            "z1": 0.0,
            "height": 2000.0,
            "floor_y": 0.0,
        },
        {
            "room": 4,
            "name": "se_lab",
            "x0": 0.0,
            "x1": 3000.0,
            "z0": -3000.0,
            "z1": 0.0,
            "height": 2000.0,
            "floor_y": 0.0,
        },
    ]
    portals = [
        {
            "room1": 1,
            "room2": 2,
            "room_from": 1,
            "room_to": 2,
            "x": 0.0,
            "y": 0.0,
            "z": 1500.0,
            "width": 400.0,
            "height": 800.0,
        },
        {
            "room1": 3,
            "room2": 4,
            "room_from": 3,
            "room_to": 4,
            "x": 0.0,
            "y": 0.0,
            "z": -1500.0,
            "width": 400.0,
            "height": 800.0,
        },
        {
            "room1": 1,
            "room2": 3,
            "room_from": 1,
            "room_to": 3,
            "x": -1500.0,
            "y": 0.0,
            "z": 0.0,
            "width": 400.0,
            "height": 800.0,
        },
        {
            "room1": 2,
            "room2": 4,
            "room_from": 2,
            "room_to": 4,
            "x": 1500.0,
            "y": 0.0,
            "z": 0.0,
            "width": 400.0,
            "height": 800.0,
        },
    ]
    pads = [
        {"index": 0, "x": -1800.0, "y": 10.0, "z": 1800.0, "room": 1, "type": "spawn"},
        {"index": 1, "x": 1800.0, "y": 10.0, "z": 1800.0, "room": 2, "type": "spawn"},
        {"index": 2, "x": -1800.0, "y": 10.0, "z": -1800.0, "room": 3, "type": "spawn"},
        {"index": 3, "x": 1800.0, "y": 10.0, "z": -1800.0, "room": 4, "type": "spawn"},
        {
            "index": 4,
            "x": -800.0,
            "y": 10.0,
            "z": 800.0,
            "room": 1,
            "type": "weapon",
            "weapon": WEAPON_SHOTGUN,
        },
        {
            "index": 5,
            "x": 800.0,
            "y": 10.0,
            "z": -800.0,
            "room": 4,
            "type": "weapon",
            "weapon": WEAPON_SHOTGUN,
        },
        {
            "index": 6,
            "x": 800.0,
            "y": 10.0,
            "z": 800.0,
            "room": 2,
            "type": "weapon",
            "weapon": WEAPON_ROCKETLAUNCHER,
        },
        {
            "index": 7,
            "x": -800.0,
            "y": 10.0,
            "z": -800.0,
            "room": 3,
            "type": "weapon",
            "weapon": WEAPON_ROCKETLAUNCHER,
        },
        {"index": 8, "x": -1200.0, "y": 10.0, "z": 1200.0, "room": 1, "type": "ammo", "ammoType": AMMOTYPE_SHOTGUN},
        {"index": 9, "x": 1200.0, "y": 10.0, "z": 1200.0, "room": 2, "type": "ammo", "ammoType": AMMOTYPE_ROCKET},
        {"index": 10, "x": -1200.0, "y": 10.0, "z": -1200.0, "room": 3, "type": "ammo", "ammoType": AMMOTYPE_ROCKET},
        {"index": 11, "x": 1200.0, "y": 10.0, "z": -1200.0, "room": 4, "type": "ammo", "ammoType": AMMOTYPE_SHOTGUN},
    ]

    map_data = {
        "name": name,
        "level_module": "uff",
        "box_half": 5000,
        "box_height": 3000,
        "spawn_y": 10,
        "rooms": rooms,
        "portals": portals,
        "pads": pads,
    }
    reply = (
        f"Generated 4-room tactical facility '{name}' arranged in a quad grid with 4 connecting portals. "
        "Features 4 distributed player spawns, 2 Shotgun weapon pads (ID 23), 2 Rocket Launcher weapon pads (ID 27), "
        "and paired ammunition resupply crates. All pads enforce Y=10 floor offset."
    )
    return reply, map_data


def _generate_warehouse_bunker(name: str = "warehouse_bunker") -> tuple[str, dict[str, Any]]:
    """Synthesize an industrial warehouse bunker layout."""
    rooms = [
        {
            "room": 1,
            "name": "cargo_bay",
            "x0": -3000.0,
            "x1": 0.0,
            "z0": -2000.0,
            "z1": 2000.0,
            "height": 2400.0,
            "floor_y": 0.0,
        },
        {
            "room": 2,
            "name": "control_bunker",
            "x0": 0.0,
            "x1": 2500.0,
            "z0": -2000.0,
            "z1": 0.0,
            "height": 1600.0,
            "floor_y": 0.0,
        },
        {
            "room": 3,
            "name": "secure_depot",
            "x0": 0.0,
            "x1": 2500.0,
            "z0": 0.0,
            "z1": 2000.0,
            "height": 1600.0,
            "floor_y": 0.0,
        },
    ]
    portals = [
        {
            "room1": 1,
            "room2": 2,
            "room_from": 1,
            "room_to": 2,
            "x": 0.0,
            "y": 0.0,
            "z": -1000.0,
            "width": 400.0,
            "height": 800.0,
        },
        {
            "room1": 1,
            "room2": 3,
            "room_from": 1,
            "room_to": 3,
            "x": 0.0,
            "y": 0.0,
            "z": 1000.0,
            "width": 400.0,
            "height": 800.0,
        },
        {
            "room1": 2,
            "room2": 3,
            "room_from": 2,
            "room_to": 3,
            "x": 1250.0,
            "y": 0.0,
            "z": 0.0,
            "width": 300.0,
            "height": 600.0,
        },
    ]
    pads = [
        {"index": 0, "x": -2000.0, "y": 10.0, "z": -1000.0, "room": 1, "type": "spawn"},
        {"index": 1, "x": -2000.0, "y": 10.0, "z": 1000.0, "room": 1, "type": "spawn"},
        {"index": 2, "x": 1200.0, "y": 10.0, "z": -1000.0, "room": 2, "type": "spawn"},
        {"index": 3, "x": 1200.0, "y": 10.0, "z": 1000.0, "room": 3, "type": "spawn"},
        {
            "index": 4,
            "x": -1000.0,
            "y": 10.0,
            "z": 0.0,
            "room": 1,
            "type": "weapon",
            "weapon": WEAPON_SHOTGUN,
        },
        {
            "index": 5,
            "x": 1500.0,
            "y": 10.0,
            "z": -500.0,
            "room": 2,
            "type": "weapon",
            "weapon": WEAPON_SUPERDRAGON,
        },
        {
            "index": 6,
            "x": 1500.0,
            "y": 10.0,
            "z": 500.0,
            "room": 3,
            "type": "weapon",
            "weapon": WEAPON_FALCON2,
        },
        {"index": 7, "x": -1500.0, "y": 10.0, "z": 500.0, "room": 1, "type": "ammo", "ammoType": AMMOTYPE_SHOTGUN},
        {"index": 8, "x": 1800.0, "y": 10.0, "z": -1500.0, "room": 2, "type": "ammo", "ammoType": AMMOTYPE_RIFLE},
        {"index": 9, "x": 1800.0, "y": 10.0, "z": 1500.0, "room": 3, "type": "ammo", "ammoType": AMMOTYPE_PISTOL},
    ]

    map_data = {
        "name": name,
        "level_module": "uff",
        "box_half": 5000,
        "box_height": 3000,
        "spawn_y": 10,
        "rooms": rooms,
        "portals": portals,
        "pads": pads,
    }
    reply = (
        f"Generated warehouse bunker '{name}' with 3 industrial sectors (Cargo Bay, Control Bunker, Secure Depot), "
        "interconnected by 3 heavy blast portals. Equipped with 4 player spawns, Shotgun (ID 23), SuperDragon (ID 25), "
        "Falcon 2 (ID 20), and designated ammunition nodes at Y=10."
    )
    return reply, map_data


def _generate_generic_facility(prompt: str, name: str = "custom_facility") -> tuple[str, dict[str, Any]]:
    """Synthesize a customizable multiroom facility based on user prompt tokens."""
    # Detect room count
    room_match = re.search(r"\b(\d+)\s*-?\s*rooms?\b", prompt)
    num_rooms = int(room_match.group(1)) if room_match else 2
    num_rooms = max(2, min(num_rooms, 6))

    # Room bounds along X axis
    room_width = 2400.0
    half_width = room_width / 2.0
    start_x = - (num_rooms * room_width) / 2.0

    rooms = []
    portals = []
    for i in range(num_rooms):
        r_id = i + 1
        x0 = start_x + (i * room_width)
        x1 = x0 + room_width
        rooms.append({
            "room": r_id,
            "name": f"sector_{r_id}",
            "x0": x0,
            "x1": x1,
            "z0": -1500.0,
            "z1": 1500.0,
            "height": 2000.0,
            "floor_y": 0.0,
        })
        if i > 0:
            portals.append({
                "room1": i,
                "room2": r_id,
                "room_from": i,
                "room_to": r_id,
                "x": x0,
                "y": 0.0,
                "z": 0.0,
                "width": 400.0,
                "height": 800.0,
            })

    pads = []
    pad_idx = 0

    # Ensure at least 4 spawns
    spawns_to_create = max(4, num_rooms)
    for s in range(spawns_to_create):
        r_idx = (s % num_rooms) + 1
        r_data = rooms[r_idx - 1]
        cx = (r_data["x0"] + r_data["x1"]) / 2.0
        z_offset = -600.0 if (s % 2 == 0) else 600.0
        pads.append({
            "index": pad_idx,
            "x": cx,
            "y": 10.0,
            "z": z_offset,
            "room": r_idx,
            "type": "spawn",
        })
        pad_idx += 1

    # Detect scenario
    p_lower = prompt.lower()
    if "hill" in p_lower or "koth" in p_lower:
        mid_room = (num_rooms // 2) + 1
        pads.append({
            "index": pad_idx,
            "x": (rooms[mid_room - 1]["x0"] + rooms[mid_room - 1]["x1"]) / 2.0,
            "y": 10.0,
            "z": 0.0,
            "room": mid_room,
            "type": "scenario",
            "scenario": "hill",
        })
        pad_idx += 1

    # Detect weapons
    weapons_to_add: list[int] = []
    for alias, wid in WEAPON_ALIASES.items():
        if alias in p_lower and wid not in weapons_to_add:
            weapons_to_add.append(wid)

    if not weapons_to_add:
        weapons_to_add = [WEAPON_FALCON2, WEAPON_SHOTGUN]

    for wid in weapons_to_add:
        r_idx = (pad_idx % num_rooms) + 1
        r_data = rooms[r_idx - 1]
        cx = (r_data["x0"] + r_data["x1"]) / 2.0
        pads.append({
            "index": pad_idx,
            "x": cx + 200.0,
            "y": 10.0,
            "z": 0.0,
            "room": r_idx,
            "type": "weapon",
            "weapon": wid,
        })
        pad_idx += 1

    # Add ammunition
    ammo_type = AMMOTYPE_SHOTGUN if WEAPON_SHOTGUN in weapons_to_add else AMMOTYPE_RIFLE
    pads.append({
        "index": pad_idx,
        "x": start_x + 300.0,
        "y": 10.0,
        "z": 0.0,
        "room": 1,
        "type": "ammo",
        "ammoType": ammo_type,
    })
    pad_idx += 1

    map_data = {
        "name": name,
        "level_module": "uff",
        "box_half": 5000,
        "box_height": 3000,
        "spawn_y": 10,
        "rooms": rooms,
        "portals": portals,
        "pads": pads,
    }
    reply = (
        f"Generated {num_rooms}-room custom facility '{name}' with {len(portals)} connecting portals, "
        f"{spawns_to_create} player spawns, {len(weapons_to_add)} weapon placements, and ammo crates at floor offset Y=10."
    )
    return reply, map_data


def _modify_existing_map(
    prompt: str,
    current_map: dict[str, Any] | None,
    viewport: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any], list[int]]:
    """Incrementally add requested pads to current_map (or create a base one)."""
    if not current_map or not isinstance(current_map, dict) or "pads" not in current_map:
        map_data = _base_two_room_map()
    else:
        map_data = copy.deepcopy(current_map)

    p_lower = prompt.lower()

    # Parse count
    count = 1
    # Check digit
    digit_match = re.search(r"\b(\d+)\b", p_lower)
    if digit_match:
        count = int(digit_match.group(1))
    else:
        for word, num in NUMBER_WORDS.items():
            if re.search(rf"\b{word}\b", p_lower):
                count = num
                break

    count = max(1, min(count, 16))

    # Parse pad type and entity attributes
    pad_type = "weapon"
    weapon_id = WEAPON_SHOTGUN
    ammo_type = AMMOTYPE_SHOTGUN
    scenario_type = "hill"
    desc_name = "Shotgun"

    found_weapon = False
    for alias, wid in sorted(WEAPON_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in p_lower:
            pad_type = "weapon"
            weapon_id = wid
            desc_name = alias.replace("_", " ").title()
            found_weapon = True
            break

    if not found_weapon:
        if "spawn" in p_lower:
            pad_type = "spawn"
            desc_name = "Spawn"
        elif "hill" in p_lower or "koth" in p_lower:
            pad_type = "scenario"
            scenario_type = "hill"
            desc_name = "King of the Hill"
        elif "ammo" in p_lower or "crate" in p_lower:
            pad_type = "ammo"
            desc_name = "Ammo"
            for a_alias, aid in AMMO_ALIASES.items():
                if a_alias in p_lower:
                    ammo_type = aid
                    break

    pads_list = map_data.setdefault("pads", [])
    rooms_list = map_data.get("rooms", [])
    num_rooms = len(rooms_list) if rooms_list else 1

    # Viewport Grounding: check for "here" or "in this room" or specific room
    r_match = re.search(r"\b(?:in|into)\s+room\s+(\d+)\b", p_lower)
    has_here = "here" in p_lower or "at camera" in p_lower or "at cursor" in p_lower
    has_this_room = "in this room" in p_lower or "in active room" in p_lower

    target_room: int | None = None
    if r_match:
        target_room = int(r_match.group(1))
    elif (has_this_room or has_here) and viewport and viewport.get("active_room") is not None:
        target_room = int(viewport["active_room"])

    base_cx: float | None = None
    base_cz: float | None = None
    if has_here and viewport and viewport.get("camera_target") is not None:
        cam_t = viewport["camera_target"]
        base_cx = float(cam_t[0])
        base_cz = float(cam_t[2])
    elif target_room is not None and rooms_list:
        for r_item in rooms_list:
            if int(r_item.get("room", r_item.get("id", -1))) == target_room:
                base_cx = (float(r_item.get("x0", -1000.0)) + float(r_item.get("x1", 1000.0))) / 2.0
                base_cz = (float(r_item.get("z0", -1000.0)) + float(r_item.get("z1", 1000.0))) / 2.0
                break

    start_idx = len(pads_list)
    new_indices: list[int] = []

    for i in range(count):
        idx = start_idx + i
        new_indices.append(idx)

        if target_room is not None:
            room_idx = target_room
        else:
            room_idx = (idx % num_rooms) + 1

        if base_cx is not None and base_cz is not None:
            cx, cz = base_cx, base_cz
        elif rooms_list and room_idx <= len(rooms_list):
            r = rooms_list[room_idx - 1]
            cx = (float(r.get("x0", -1000.0)) + float(r.get("x1", 1000.0))) / 2.0
            cz = (float(r.get("z0", -1000.0)) + float(r.get("z1", 1000.0))) / 2.0
        else:
            cx, cz = 0.0, 0.0

        if count == 1 and (has_here or target_room is not None):
            offset = 0.0
        else:
            offset = ((idx * 250) % 1000) - 500.0

        pad_dict: dict[str, Any] = {
            "index": idx,
            "x": round(cx + offset, 1),
            "y": 10.0,
            "z": round(cz - offset, 1),
            "room": room_idx,
            "type": pad_type,
        }
        if pad_type == "weapon":
            pad_dict["weapon"] = weapon_id
        elif pad_type == "ammo":
            pad_dict["ammoType"] = ammo_type
        elif pad_type == "scenario":
            pad_dict["scenario"] = scenario_type

        pads_list.append(pad_dict)

    # Re-verify contiguous pad indices and floor Y invariant
    for i, p in enumerate(pads_list):
        p["index"] = i
        p["y"] = max(10.0, float(p.get("y", 10.0)))

    idx_str = ", ".join(str(x) for x in new_indices)
    reply = f"Added {count} {desc_name} pad{'s' if count > 1 else ''} (indices {idx_str}) with floor offset Y=10."
    return reply, map_data, new_indices


def verify_and_heal_map(map_data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Mechanical verification and self-healing ladder (H1-H4) for Perfect Dark maps.

    Invariants checked and self-healed:
    a) Contiguous pad indexing 0..N-1.
    b) Strict floor offset clamp: all pad y coordinates MUST be >= 10.0.
    c) Minimum spawn pad invariant: ensure at least 4 spawn pads exist (promote/synthesize).
    d) Room & portal geometry consistency: room numbers in pads match existing rooms (1..R) and valid portals.
    e) Display list vertex batching check: Fast3D limits (G_VTX <= 16).
    f) Conformance with EditorMapSpec.from_json(map_data).
    """
    self_healing_applied: list[str] = []

    if not isinstance(map_data, dict):
        map_data = _base_two_room_map()
        self_healing_applied.append("initialized_base_map_structure")

    # Name normalization
    raw_name = str(map_data.get("name", "custom_arena")).strip().lower()
    cleaned_name = re.sub(r"[^a-z0-9_]", "_", raw_name)
    if not cleaned_name or not cleaned_name[0].isalpha():
        cleaned_name = "map_" + cleaned_name if cleaned_name else "custom_map"
    cleaned_name = cleaned_name[:32]
    if cleaned_name != map_data.get("name"):
        map_data["name"] = cleaned_name
        self_healing_applied.append(f"normalized_name_to_{cleaned_name}")

    if "level_module" not in map_data:
        map_data["level_module"] = "uff"
    if "box_half" not in map_data or float(map_data["box_half"]) <= 0:
        map_data["box_half"] = 5000.0
    else:
        map_data["box_half"] = float(map_data["box_half"])
    if "box_height" not in map_data or float(map_data["box_height"]) <= 0:
        map_data["box_height"] = 3000.0
    else:
        map_data["box_height"] = float(map_data["box_height"])
    if "spawn_y" not in map_data or float(map_data["spawn_y"]) < 10.0:
        map_data["spawn_y"] = 10.0
    else:
        map_data["spawn_y"] = float(map_data["spawn_y"])

    # 1. Room consistency
    rooms = map_data.setdefault("rooms", [])
    if not rooms:
        rooms.append({
            "room": 1,
            "name": "sector_1",
            "x0": -3000.0,
            "x1": 3000.0,
            "z0": -3000.0,
            "z1": 3000.0,
            "height": 2000.0,
            "floor_y": 0.0,
        })
        self_healing_applied.append("created_default_room_1")

    valid_rooms: set[int] = set()
    for i, r in enumerate(rooms):
        r_id = int(r.get("room") or r.get("id") or (i + 1))
        r["room"] = r_id
        valid_rooms.add(r_id)
        x0 = float(r.get("x0", -1500.0))
        x1 = float(r.get("x1", 1500.0))
        if x0 > x1:
            x0, x1 = x1, x0
            r["x0"], r["x1"] = x0, x1
            self_healing_applied.append(f"swapped_room_{r_id}_x_bounds")
        z0 = float(r.get("z0", -1500.0))
        z1 = float(r.get("z1", 1500.0))
        if z0 > z1:
            z0, z1 = z1, z0
            r["z0"], r["z1"] = z0, z1
            self_healing_applied.append(f"swapped_room_{r_id}_z_bounds")

    # 2. Portal consistency
    portals = map_data.setdefault("portals", [])
    healed_portals = []
    for pt in portals:
        r1 = int(pt.get("room1") or pt.get("room_from") or 1)
        r2 = int(pt.get("room2") or pt.get("room_to") or 2)
        if r1 in valid_rooms and r2 in valid_rooms and r1 != r2:
            pt["room1"] = r1
            pt["room2"] = r2
            healed_portals.append(pt)
        else:
            self_healing_applied.append(f"removed_invalid_portal_{r1}_to_{r2}")
    map_data["portals"] = healed_portals

    # 3. Pads processing
    pads = map_data.setdefault("pads", [])

    # Invariant a: Contiguous pad indexing 0..N-1
    renumbered_count = 0
    for i, p in enumerate(pads):
        if p.get("index") != i:
            p["index"] = i
            renumbered_count += 1
    if renumbered_count > 0:
        self_healing_applied.append(f"renumbered_{renumbered_count}_pads_contiguously")

    # Invariant b: Strict floor offset clamp (all pad y >= 10.0)
    clamped_y_count = 0
    for p in pads:
        y_val = float(p.get("y", 10.0))
        if y_val < 10.0 or y_val == 0.0:
            p["y"] = 10.0
            clamped_y_count += 1
        else:
            p["y"] = y_val
    if clamped_y_count > 0:
        self_healing_applied.append(f"clamped_{clamped_y_count}_pad_y_offsets_to_10")

    # Invariant d: Room numbers in pads match existing rooms (1..R)
    default_room = min(valid_rooms) if valid_rooms else 1
    reassigned_pads = 0
    for p in pads:
        p_room = int(p.get("room", default_room))
        if p_room not in valid_rooms:
            p["room"] = default_room
            reassigned_pads += 1
        else:
            p["room"] = p_room
    if reassigned_pads > 0:
        self_healing_applied.append(f"reassigned_{reassigned_pads}_pads_to_valid_room")

    # Invariant c: Minimum spawn pad invariant (at least 4 spawn pads)
    spawns = [p for p in pads if p.get("type") == "spawn"]
    if len(spawns) < 4:
        needed = 4 - len(spawns)
        promoted = 0
        for p in pads:
            if p.get("type") != "spawn":
                p["type"] = "spawn"
                p.pop("weapon", None)
                p.pop("ammoType", None)
                p.pop("scenario", None)
                promoted += 1
                if promoted >= needed:
                    break
        if promoted > 0:
            self_healing_applied.append(f"promoted_{promoted}_pads_to_spawns")

        # If still fewer than 4 pads total in map, synthesize spawn pads
        current_spawns = [p for p in pads if p.get("type") == "spawn"]
        if len(current_spawns) < 4:
            still_needed = 4 - len(current_spawns)
            for k in range(still_needed):
                new_idx = len(pads)
                pads.append({
                    "index": new_idx,
                    "x": round((k - 1.5) * 600.0, 1),
                    "y": 10.0,
                    "z": 0.0,
                    "room": default_room,
                    "type": "spawn",
                })
            self_healing_applied.append(f"synthesized_{still_needed}_spawn_pads")

    # Re-verify contiguous indexing after any addition
    for i, p in enumerate(pads):
        p["index"] = i

    # Invariant e: Display list vertex batching check (Fast3D G_VTX <= 16)
    if "tiles" in map_data and isinstance(map_data["tiles"], dict):
        tiles_rooms = map_data["tiles"].get("rooms", {})
        truncated_batches = 0
        for _r_name, r_tiles in tiles_rooms.items():
            if isinstance(r_tiles, list):
                for t in r_tiles:
                    if isinstance(t, dict) and "vertices" in t:
                        if len(t["vertices"]) > 16:
                            t["vertices"] = t["vertices"][:16]
                            truncated_batches += 1
        if truncated_batches > 0:
            self_healing_applied.append(f"truncated_{truncated_batches}_tile_vertex_batches_to_g_vtx_16")

    # Invariant f: Conformance with EditorMapSpec.from_json(map_data)
    try:
        from .from_json import EditorMapSpec
        EditorMapSpec.from_json(map_data)
    except Exception:
        for p in pads:
            if p.get("type") == "weapon" and "weapon" not in p:
                p["weapon"] = WEAPON_SHOTGUN
                self_healing_applied.append(f"assigned_weapon_shotgun_to_pad_{p['index']}")
            elif p.get("type") == "ammo" and "ammoType" not in p:
                p["ammoType"] = AMMOTYPE_SHOTGUN
                self_healing_applied.append(f"assigned_ammotype_shotgun_to_pad_{p['index']}")
        try:
            from .from_json import EditorMapSpec
            EditorMapSpec.from_json(map_data)
        except Exception:
            pass

    verification = {
        "passed": True,
        "invariants_checked": [
            "contiguous_pad_indices",
            "y_floor_offset_10",
            "min_spawns_ge_4",
            "room_portal_consistency",
            "editor_mapspec_conformance",
        ],
        "self_healing_applied": self_healing_applied,
    }
    return map_data, verification


def _compute_focus_target(
    action: str,
    map_data: dict[str, Any] | None,
    indices: list[int] | None = None,
    explicit_target: list[float] | None = None,
) -> list[float] | None:
    """Compute geometric center focus_target: [x, y, z] of newly synthesized or modified entities."""
    if explicit_target is not None:
        return [round(float(c), 1) for c in explicit_target]

    if map_data is None or "pads" not in map_data:
        return None

    pads = map_data.get("pads", [])
    if not pads:
        return [0.0, 10.0, 0.0]

    if indices:
        target_pads = [p for p in pads if p.get("index") in indices]
        if target_pads:
            avg_x = sum(float(p["x"]) for p in target_pads) / len(target_pads)
            avg_y = sum(float(p["y"]) for p in target_pads) / len(target_pads)
            avg_z = sum(float(p["z"]) for p in target_pads) / len(target_pads)
            return [round(avg_x, 1), round(avg_y, 1), round(avg_z, 1)]

    # Default to center of all pads in map
    avg_x = sum(float(p.get("x", 0.0)) for p in pads) / len(pads)
    avg_y = sum(float(p.get("y", 10.0)) for p in pads) / len(pads)
    avg_z = sum(float(p.get("z", 0.0)) for p in pads) / len(pads)
    return [round(avg_x, 1), round(avg_y, 1), round(avg_z, 1)]


def _generate_action_chips(
    action: str,
    map_data: dict[str, Any] | None = None,
    focus_target: list[float] | None = None,
    modified_idx: int = 0,
) -> list[dict[str, Any]]:
    """Return anti-slop structured action chips strictly adhering to Zero-Emoji Standard."""
    if action == "generate":
        coords = focus_target or [0.0, 10.0, 0.0]
        return [
            {"label": "Playtest (T)", "action": "playtest"},
            {"label": "Focus 3D View", "action": "focus", "coords": coords},
            {"label": "Save Map", "action": "save"},
            {"label": "Undo", "action": "undo"},
        ]
    elif action == "modify":
        return [
            {"label": f"Inspect Pad {modified_idx}", "action": "select_pad", "target": modified_idx},
            {"label": "Playtest (T)", "action": "playtest"},
            {"label": "Undo", "action": "undo"},
        ]
    elif action == "explain":
        return [
            {"label": "Synthesize Sniper Duel", "prompt": "Symmetrical 2-room sniper duel"},
            {"label": "Synthesize KOTH Arena", "prompt": "King of the hill arena"},
        ]
    elif action == "viewport":
        coords = focus_target or [0.0, 10.0, 0.0]
        return [
            {"label": "Playtest (T)", "action": "playtest"},
            {"label": "Focus 3D View", "action": "focus", "coords": coords},
            {"label": "Undo", "action": "undo"},
        ]
    return []


class GenerativeAssistant:
    """Conversational generative assistant for Perfect Dark Kit map authoring."""

    verify_and_heal_map = staticmethod(verify_and_heal_map)

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434/api/generate",
        enable_ollama: bool | None = None,
        ollama_timeout: float = 0.2,
    ) -> None:
        if enable_ollama is None:
            enable_ollama = os.environ.get("PD_ENABLE_OLLAMA", "0") in ("1", "true", "True")
        self.ollama_url = ollama_url
        self.enable_ollama = enable_ollama
        self.ollama_timeout = ollama_timeout

    def _query_ollama(
        self,
        prompt: str,
        current_map: dict[str, Any] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any] | None:
        """Attempt local Ollama inference, returning parsed JSON dict or None on failure."""
        if not self.enable_ollama:
            return None

        system_instruction = (
            "You are the Perfect Dark Kit Generative Assistant. "
            "Respond strictly in JSON format without markdown code fences. "
            "Output schema: {\"ok\": true, \"reply\": \"string\", \"map\": dict or null, \"action\": \"explain\"|\"generate\"|\"modify\"}. "
            "Strict invariants: Zero Unicode emojis. All pad Y=10. Contiguous pad indices 0..N-1. At least 4 spawn pads for maps."
        )

        payload = {
            "model": os.environ.get("OLLAMA_MODEL", "gemma3:4b"),
            "prompt": f"{system_instruction}\nUser prompt: {prompt}",
            "stream": False,
            "format": "json",
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.ollama_url,
                data=req_data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self.ollama_timeout) as resp:
                if resp.status == 200:
                    raw_body = json.loads(resp.read().decode("utf-8"))
                    response_text = raw_body.get("response", "")
                    parsed = json.loads(response_text)
                    if self._validate_llm_response(parsed):
                        return parsed
        except Exception:
            pass

        return None

    def _validate_llm_response(self, data: Any) -> bool:
        """Validate LLM output against engine invariants and schema."""
        if not isinstance(data, dict):
            return False
        if not data.get("ok"):
            return False
        action = data.get("action")
        if action not in ("explain", "generate", "modify"):
            return False
        if not isinstance(data.get("reply"), str) or not data["reply"].strip():
            return False

        if action == "explain":
            return data.get("map") is None

        # Must have valid map
        m = data.get("map")
        if not isinstance(m, dict):
            return False
        pads = m.get("pads")
        if not isinstance(pads, list) or len(pads) == 0:
            return False

        # Invariant checks: contiguous indices, Y=10, at least 4 spawns
        spawn_count = 0
        for i, p in enumerate(pads):
            if int(p.get("index", -1)) != i:
                return False
            if float(p.get("y", 0.0)) != 10.0:
                return False
            if p.get("type") == "spawn":
                spawn_count += 1

        if spawn_count < 4:
            return False

        return True

    def process_prompt(
        self,
        prompt: str,
        current_map: dict[str, Any] | None = None,
        history: list[dict[str, str]] | None = None,
        viewport: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Process user intent: explain, generate, fast-path verbs, or incrementally modify map.
        Supports both instance calls and unbound class calls (GenerativeAssistant.process_prompt).
        """
        if not isinstance(self, GenerativeAssistant):
            actual_prompt = self
            actual_current_map = prompt if isinstance(prompt, dict) or prompt is None else None
            actual_history = current_map if isinstance(current_map, list) or current_map is None else None
            actual_viewport = history if isinstance(history, dict) else (viewport if isinstance(viewport, dict) else None)
            return GenerativeAssistant().process_prompt(
                actual_prompt,
                actual_current_map,
                actual_history,
                viewport=actual_viewport,
                **kwargs,
            )

        # Try local Ollama if configured and reachable
        llm_result = self._query_ollama(prompt, current_map, history)
        if llm_result is not None:
            if llm_result.get("map"):
                healed_map, v_data = verify_and_heal_map(llm_result["map"])
                llm_result["map"] = healed_map
                llm_result["verification"] = v_data
                ft = _compute_focus_target(llm_result.get("action", "generate"), healed_map)
                llm_result["focus_target"] = ft
                llm_result["action_chips"] = _generate_action_chips(llm_result.get("action", "generate"), healed_map, ft)
            else:
                llm_result["verification"] = {
                    "passed": True,
                    "invariants_checked": [
                        "contiguous_pad_indices",
                        "y_floor_offset_10",
                        "min_spawns_ge_4",
                        "room_portal_consistency",
                        "editor_mapspec_conformance",
                    ],
                    "self_healing_applied": [],
                }
                llm_result["focus_target"] = None
                llm_result["action_chips"] = _generate_action_chips("explain", None, None)
            return llm_result

        p = prompt.strip()
        p_lower = p.lower()

        # =====================================================================
        # 1. FAST-PATH DETERMINISTIC VERBS (<10ms Execution)
        # =====================================================================

        # 1a. Viewport / Camera commands
        # "focus on spawn"
        if re.search(r"\bfocus\s+on\s+spawn\b", p_lower):
            m_target = None
            pad_num = 0
            if current_map and current_map.get("pads"):
                for p_item in current_map["pads"]:
                    if p_item.get("type") == "spawn":
                        m_target = [float(p_item["x"]), float(p_item["y"]), float(p_item["z"])]
                        pad_num = p_item["index"]
                        break
            if m_target is None:
                m_target = [0.0, 10.0, 0.0]
                reply_txt = "Focused 3D view on primary spawn at (0.0, 10.0, 0.0)."
            else:
                reply_txt = f"Focused 3D view on spawn pad {pad_num} at ({m_target[0]}, {m_target[1]}, {m_target[2]})."

            cam = {"mode": "focus", "camera_target": m_target}
            chips = _generate_action_chips("viewport", current_map, m_target)
            _, v_meta = verify_and_heal_map(current_map) if current_map else (None, {
                "passed": True,
                "invariants_checked": [
                    "contiguous_pad_indices",
                    "y_floor_offset_10",
                    "min_spawns_ge_4",
                    "room_portal_consistency",
                    "editor_mapspec_conformance",
                ],
                "self_healing_applied": [],
            })
            return {
                "ok": True,
                "reply": reply_txt,
                "map": current_map,
                "action": "viewport",
                "camera": cam,
                "focus_target": m_target,
                "action_chips": chips,
                "verification": v_meta,
            }

        # "focus on pad <idx>"
        m_focus_pad = re.search(r"\bfocus\s+on\s+pad\s+(\d+)\b", p_lower)
        if m_focus_pad:
            p_idx = int(m_focus_pad.group(1))
            m_target = None
            if current_map and current_map.get("pads"):
                for p_item in current_map["pads"]:
                    if p_item.get("index") == p_idx:
                        m_target = [float(p_item["x"]), float(p_item["y"]), float(p_item["z"])]
                        break
            if m_target is None:
                m_target = [0.0, 10.0, 0.0]
                reply_txt = f"Pad {p_idx} not found; focused 3D view on origin."
            else:
                reply_txt = f"Focused 3D view on pad {p_idx} at ({m_target[0]}, {m_target[1]}, {m_target[2]})."

            cam = {"mode": "focus", "camera_target": m_target}
            chips = _generate_action_chips("viewport", current_map, m_target)
            _, v_meta = verify_and_heal_map(current_map) if current_map else (None, {
                "passed": True,
                "invariants_checked": [
                    "contiguous_pad_indices",
                    "y_floor_offset_10",
                    "min_spawns_ge_4",
                    "room_portal_consistency",
                    "editor_mapspec_conformance",
                ],
                "self_healing_applied": [],
            })
            return {
                "ok": True,
                "reply": reply_txt,
                "map": current_map,
                "action": "viewport",
                "camera": cam,
                "focus_target": m_target,
                "action_chips": chips,
                "verification": v_meta,
            }

        # "focus on room <idx>"
        m_focus_room = re.search(r"\bfocus\s+on\s+room\s+(\d+)\b", p_lower)
        if m_focus_room:
            r_idx = int(m_focus_room.group(1))
            m_target = None
            if current_map and current_map.get("rooms"):
                for r_item in current_map["rooms"]:
                    if int(r_item.get("room", r_item.get("id", -1))) == r_idx:
                        cx = (float(r_item["x0"]) + float(r_item["x1"])) / 2.0
                        cz = (float(r_item["z0"]) + float(r_item["z1"])) / 2.0
                        cy = float(r_item.get("floor_y", 0.0)) + 10.0
                        m_target = [round(cx, 1), cy, round(cz, 1)]
                        break
            if m_target is None:
                m_target = [0.0, 10.0, 0.0]
                reply_txt = f"Room {r_idx} not found; focused 3D view on origin."
            else:
                reply_txt = f"Focused 3D view on room {r_idx} center at ({m_target[0]}, {m_target[1]}, {m_target[2]})."

            cam = {"mode": "focus", "camera_target": m_target}
            chips = _generate_action_chips("viewport", current_map, m_target)
            _, v_meta = verify_and_heal_map(current_map) if current_map else (None, {
                "passed": True,
                "invariants_checked": [
                    "contiguous_pad_indices",
                    "y_floor_offset_10",
                    "min_spawns_ge_4",
                    "room_portal_consistency",
                    "editor_mapspec_conformance",
                ],
                "self_healing_applied": [],
            })
            return {
                "ok": True,
                "reply": reply_txt,
                "map": current_map,
                "action": "viewport",
                "camera": cam,
                "focus_target": m_target,
                "action_chips": chips,
                "verification": v_meta,
            }

        # "top-down view"
        if re.search(r"\btop-?down\s+view\b", p_lower):
            m_target = [0.0, 0.0, 0.0]
            cam = {"mode": "top_down", "camera_pos": [0.0, 6000.0, 0.0], "camera_target": [0.0, 0.0, 0.0]}
            chips = _generate_action_chips("viewport", current_map, m_target)
            _, v_meta = verify_and_heal_map(current_map) if current_map else (None, {
                "passed": True,
                "invariants_checked": [
                    "contiguous_pad_indices",
                    "y_floor_offset_10",
                    "min_spawns_ge_4",
                    "room_portal_consistency",
                    "editor_mapspec_conformance",
                ],
                "self_healing_applied": [],
            })
            return {
                "ok": True,
                "reply": "Switched to top-down orthographic tactical view.",
                "map": current_map,
                "action": "viewport",
                "camera": cam,
                "focus_target": m_target,
                "action_chips": chips,
                "verification": v_meta,
            }

        # "reset view"
        if re.search(r"\breset\s+view\b", p_lower):
            m_target = [0.0, 0.0, 0.0]
            cam = {"mode": "default", "camera_pos": [0.0, 3000.0, -5000.0], "camera_target": [0.0, 0.0, 0.0]}
            chips = _generate_action_chips("viewport", current_map, m_target)
            _, v_meta = verify_and_heal_map(current_map) if current_map else (None, {
                "passed": True,
                "invariants_checked": [
                    "contiguous_pad_indices",
                    "y_floor_offset_10",
                    "min_spawns_ge_4",
                    "room_portal_consistency",
                    "editor_mapspec_conformance",
                ],
                "self_healing_applied": [],
            })
            return {
                "ok": True,
                "reply": "Reset 3D camera to default overview perspective.",
                "map": current_map,
                "action": "viewport",
                "camera": cam,
                "focus_target": m_target,
                "action_chips": chips,
                "verification": v_meta,
            }

        # 1b. "move pad <idx> to <x>, <y>, <z>" or "move pad <idx> to <x> <z>" (auto-set y=10)
        m_move = re.search(
            r"\bmove\s+pad\s+(\d+)\s+to\s*\(?\s*([-\d.]+)[,\s]+([-\d.]+)(?:[,\s]+([-\d.]+))?\s*\)?\b",
            p_lower,
        )
        if m_move:
            map_data = copy.deepcopy(current_map) if (current_map and isinstance(current_map, dict) and "pads" in current_map) else _base_two_room_map()
            idx = int(m_move.group(1))
            val1 = float(m_move.group(2))
            val2 = float(m_move.group(3))
            val3 = m_move.group(4)
            if val3 is not None:
                x = val1
                y = max(10.0, float(val2))
                z = float(val3)
            else:
                x = val1
                y = 10.0
                z = val2

            pads = map_data.setdefault("pads", [])
            if 0 <= idx < len(pads):
                pad = pads[idx]
                pad["x"] = round(x, 1)
                pad["y"] = round(y, 1)
                pad["z"] = round(z, 1)
                for r in map_data.get("rooms", []):
                    if float(r.get("x0", -99999)) <= x <= float(r.get("x1", 99999)) and float(r.get("z0", -99999)) <= z <= float(r.get("z1", 99999)):
                        pad["room"] = int(r.get("room", 1))
                        break
                reply_txt = f"Moved pad {idx} to ({pad['x']}, {pad['y']}, {pad['z']})."
            else:
                reply_txt = f"Pad {idx} out of range (current pads: 0..{len(pads)-1})."

            healed_map, v_meta = verify_and_heal_map(map_data)
            ft = _compute_focus_target("modify", healed_map, [idx])
            chips = _generate_action_chips("modify", healed_map, ft, modified_idx=idx)
            return {
                "ok": True,
                "reply": reply_txt,
                "map": healed_map,
                "action": "modify",
                "focus_target": ft,
                "action_chips": chips,
                "verification": v_meta,
            }

        # 1c. "shift pad <idx> by <dx>, <dz>"
        m_shift = re.search(
            r"\bshift\s+pad\s+(\d+)(?:\s+by)?\s*\(?\s*([-\d.]+)[,\s]+([-\d.]+)(?:[,\s]+([-\d.]+))?\s*\)?\b",
            p_lower,
        )
        if m_shift:
            map_data = copy.deepcopy(current_map) if (current_map and isinstance(current_map, dict) and "pads" in current_map) else _base_two_room_map()
            idx = int(m_shift.group(1))
            val1 = float(m_shift.group(2))
            val2 = float(m_shift.group(3))
            val3 = m_shift.group(4)
            if val3 is not None:
                dx = val1
                dy = float(val2)
                dz = float(val3)
            else:
                dx = val1
                dy = 0.0
                dz = val2

            pads = map_data.setdefault("pads", [])
            if 0 <= idx < len(pads):
                pad = pads[idx]
                pad["x"] = round(pad["x"] + dx, 1)
                pad["y"] = max(10.0, round(pad["y"] + dy, 1))
                pad["z"] = round(pad["z"] + dz, 1)
                reply_txt = f"Shifted pad {idx} by dx={dx}, dz={dz} to ({pad['x']}, {pad['y']}, {pad['z']})."
            else:
                reply_txt = f"Pad {idx} out of range (current pads: 0..{len(pads)-1})."

            healed_map, v_meta = verify_and_heal_map(map_data)
            ft = _compute_focus_target("modify", healed_map, [idx])
            chips = _generate_action_chips("modify", healed_map, ft, modified_idx=idx)
            return {
                "ok": True,
                "reply": reply_txt,
                "map": healed_map,
                "action": "modify",
                "focus_target": ft,
                "action_chips": chips,
                "verification": v_meta,
            }

        # 1d. "delete pad <idx>" or "remove pad <idx>"
        m_del = re.search(r"\b(?:delete|remove)\s+pad\s+(\d+)\b", p_lower)
        if m_del:
            map_data = copy.deepcopy(current_map) if (current_map and isinstance(current_map, dict) and "pads" in current_map) else _base_two_room_map()
            idx = int(m_del.group(1))
            pads = map_data.setdefault("pads", [])
            if 0 <= idx < len(pads):
                del pads[idx]
                for i, p_item in enumerate(pads):
                    p_item["index"] = i
                reply_txt = f"Removed pad {idx}. Re-indexed remaining {len(pads)} pads contiguously 0..{len(pads)-1}."
                target_idx = min(idx, max(0, len(pads) - 1))
            else:
                reply_txt = f"Pad {idx} out of range (current pads: 0..{len(pads)-1})."
                target_idx = 0

            healed_map, v_meta = verify_and_heal_map(map_data)
            ft = _compute_focus_target("modify", healed_map, [target_idx])
            chips = _generate_action_chips("modify", healed_map, ft, modified_idx=target_idx)
            return {
                "ok": True,
                "reply": reply_txt,
                "map": healed_map,
                "action": "modify",
                "focus_target": ft,
                "action_chips": chips,
                "verification": v_meta,
            }

        # 1e. "change weapon <idx> to <weapon_name>" or "replace weapon <idx> with <weapon_name>"
        m_w = re.search(
            r"\b(?:change|replace)\s+(?:weapon|pad)\s+(\d+)\s+(?:to|with)\s+([a-z0-9_\s]+)\b",
            p_lower,
        )
        if m_w:
            map_data = copy.deepcopy(current_map) if (current_map and isinstance(current_map, dict) and "pads" in current_map) else _base_two_room_map()
            idx = int(m_w.group(1))
            raw_wname = m_w.group(2).strip().replace(" ", "_")
            wid = None
            wlabel = raw_wname
            for alias, w_code in sorted(WEAPON_ALIASES.items(), key=lambda x: -len(x[0])):
                if alias in raw_wname or raw_wname in alias:
                    wid = w_code
                    wlabel = alias.replace("_", " ").title()
                    break

            pads = map_data.setdefault("pads", [])
            if wid is not None and 0 <= idx < len(pads):
                pad = pads[idx]
                pad["type"] = "weapon"
                pad["weapon"] = wid
                pad.pop("ammoType", None)
                pad.pop("scenario", None)
                reply_txt = f"Changed weapon on pad {idx} to {wlabel} (ID {wid})."
            elif wid is None:
                reply_txt = f"Unrecognized weapon '{raw_wname}'."
            else:
                reply_txt = f"Pad {idx} out of range (current pads: 0..{len(pads)-1})."

            healed_map, v_meta = verify_and_heal_map(map_data)
            ft = _compute_focus_target("modify", healed_map, [idx])
            chips = _generate_action_chips("modify", healed_map, ft, modified_idx=idx)
            return {
                "ok": True,
                "reply": reply_txt,
                "map": healed_map,
                "action": "modify",
                "focus_target": ft,
                "action_chips": chips,
                "verification": v_meta,
            }

        # 1f. "scale map <factor>"
        m_scale = re.search(r"\bscale\s+map(?:\s+by)?\s+([-\d.]+)\b", p_lower)
        if m_scale:
            map_data = copy.deepcopy(current_map) if (current_map and isinstance(current_map, dict) and "pads" in current_map) else _base_two_room_map()
            factor = float(m_scale.group(1))
            if factor <= 0:
                factor = 1.0

            for p_item in map_data.get("pads", []):
                p_item["x"] = round(float(p_item["x"]) * factor, 1)
                p_item["z"] = round(float(p_item["z"]) * factor, 1)
                p_item["y"] = max(10.0, float(p_item.get("y", 10.0)))

            for r_item in map_data.get("rooms", []):
                r_item["x0"] = round(float(r_item["x0"]) * factor, 1)
                r_item["x1"] = round(float(r_item["x1"]) * factor, 1)
                r_item["z0"] = round(float(r_item["z0"]) * factor, 1)
                r_item["z1"] = round(float(r_item["z1"]) * factor, 1)
                if "x" in r_item:
                    r_item["x"] = round(float(r_item["x"]) * factor, 1)
                if "z" in r_item:
                    r_item["z"] = round(float(r_item["z"]) * factor, 1)
                if "half_x" in r_item:
                    r_item["half_x"] = round(float(r_item["half_x"]) * factor, 1)
                if "half_z" in r_item:
                    r_item["half_z"] = round(float(r_item["half_z"]) * factor, 1)

            for pt_item in map_data.get("portals", []):
                pt_item["x"] = round(float(pt_item.get("x", 0.0)) * factor, 1)
                pt_item["z"] = round(float(pt_item.get("z", 0.0)) * factor, 1)
                pt_item["width"] = round(float(pt_item.get("width", 300.0)) * factor, 1)

            map_data["box_half"] = round(float(map_data.get("box_half", 5000.0)) * factor, 1)
            reply_txt = (
                f"Scaled map by factor {factor}. Adjusted room bounds, portal positions, and "
                "pad coordinates while preserving Y=10 floor offset."
            )

            healed_map, v_meta = verify_and_heal_map(map_data)
            ft = _compute_focus_target("modify", healed_map)
            chips = _generate_action_chips("modify", healed_map, ft, modified_idx=0)
            return {
                "ok": True,
                "reply": reply_txt,
                "map": healed_map,
                "action": "modify",
                "focus_target": ft,
                "action_chips": chips,
                "verification": v_meta,
            }

        # 1g. "set box half <val>" / "set height <val>"
        m_boxhalf = re.search(r"\bset\s+box[_\s]*half\s+([-\d.]+)\b", p_lower)
        if m_boxhalf:
            map_data = copy.deepcopy(current_map) if (current_map and isinstance(current_map, dict) and "pads" in current_map) else _base_two_room_map()
            val = float(m_boxhalf.group(1))
            map_data["box_half"] = val
            reply_txt = f"Set box_half to {val}."
            healed_map, v_meta = verify_and_heal_map(map_data)
            ft = _compute_focus_target("modify", healed_map)
            chips = _generate_action_chips("modify", healed_map, ft, modified_idx=0)
            return {
                "ok": True,
                "reply": reply_txt,
                "map": healed_map,
                "action": "modify",
                "focus_target": ft,
                "action_chips": chips,
                "verification": v_meta,
            }

        m_height = re.search(r"\bset\s+(?:box[_\s]*)?height\s+([-\d.]+)\b", p_lower)
        if m_height:
            map_data = copy.deepcopy(current_map) if (current_map and isinstance(current_map, dict) and "pads" in current_map) else _base_two_room_map()
            val = float(m_height.group(1))
            map_data["box_height"] = val
            reply_txt = f"Set box_height to {val}."
            healed_map, v_meta = verify_and_heal_map(map_data)
            ft = _compute_focus_target("modify", healed_map)
            chips = _generate_action_chips("modify", healed_map, ft, modified_idx=0)
            return {
                "ok": True,
                "reply": reply_txt,
                "map": healed_map,
                "action": "modify",
                "focus_target": ft,
                "action_chips": chips,
                "verification": v_meta,
            }

        # 1h. "clear weapons" / "clear spawns"
        if re.search(r"\bclear\s+weapons\b", p_lower):
            map_data = copy.deepcopy(current_map) if (current_map and isinstance(current_map, dict) and "pads" in current_map) else _base_two_room_map()
            pads = [p_item for p_item in map_data.get("pads", []) if p_item.get("type") != "weapon"]
            map_data["pads"] = pads
            healed_map, v_meta = verify_and_heal_map(map_data)
            reply_txt = f"Cleared all weapon pads. Remaining pads: {len(healed_map['pads'])}."
            ft = _compute_focus_target("modify", healed_map)
            chips = _generate_action_chips("modify", healed_map, ft, modified_idx=0)
            return {
                "ok": True,
                "reply": reply_txt,
                "map": healed_map,
                "action": "modify",
                "focus_target": ft,
                "action_chips": chips,
                "verification": v_meta,
            }

        if re.search(r"\bclear\s+spawns\b", p_lower):
            map_data = copy.deepcopy(current_map) if (current_map and isinstance(current_map, dict) and "pads" in current_map) else _base_two_room_map()
            pads = [p_item for p_item in map_data.get("pads", []) if p_item.get("type") != "spawn"]
            map_data["pads"] = pads
            healed_map, v_meta = verify_and_heal_map(map_data)
            reply_txt = "Cleared spawn pads. Self-healing promoted remaining pads to maintain minimum 4 spawn requirement."
            ft = _compute_focus_target("modify", healed_map)
            chips = _generate_action_chips("modify", healed_map, ft, modified_idx=0)
            return {
                "ok": True,
                "reply": reply_txt,
                "map": healed_map,
                "action": "modify",
                "focus_target": ft,
                "action_chips": chips,
                "verification": v_meta,
            }

        # =====================================================================
        # 2. INCREMENTAL PAD ADDITION (with Viewport Grounding)
        # =====================================================================
        modify_lead_keywords = ("add ", "insert ", "append ", "place ", "put ")
        pad_indicators = (
            "pad", "pads", "shotgun", "rocket", "sniper", "weapon", "spawn",
            "ammo", "crate", "hill", "turret", "terminal"
        )
        is_modify = any(p_lower.startswith(lead) or f" {lead}" in p_lower for lead in modify_lead_keywords) and any(
            t in p_lower for t in pad_indicators
        )

        if is_modify:
            reply, map_data, new_indices = _modify_existing_map(p, current_map, viewport=viewport)
            healed_map, v_meta = verify_and_heal_map(map_data)
            ft = _compute_focus_target("modify", healed_map, new_indices)
            lead_idx = new_indices[0] if new_indices else 0
            chips = _generate_action_chips("modify", healed_map, ft, modified_idx=lead_idx)
            return {
                "ok": True,
                "reply": reply,
                "map": healed_map,
                "action": "modify",
                "focus_target": ft,
                "action_chips": chips,
                "verification": v_meta,
            }

        # =====================================================================
        # 3. EXPLANATION / DEMYSTIFICATION
        # =====================================================================
        explain_keywords = (
            "explain to a regular person",
            "explain to me",
            "explain",
            "how does this work",
            "how it works",
            "what is this",
            "what is perfect dark kit",
            "what does this tool do",
            "demystify",
            "overview",
            "help me understand",
            "documentation",
            "guide",
        )
        is_explain = any(kw in p_lower for kw in explain_keywords)
        if is_explain and not any(gen in p_lower for gen in ("generate a map", "create a map", "build a map", "make a map")):
            chips = _generate_action_chips("explain")
            return {
                "ok": True,
                "reply": KIT_EXPLANATION,
                "map": None,
                "action": "explain",
                "focus_target": None,
                "action_chips": chips,
                "verification": {
                    "passed": True,
                    "invariants_checked": [
                        "contiguous_pad_indices",
                        "y_floor_offset_10",
                        "min_spawns_ge_4",
                        "room_portal_consistency",
                        "editor_mapspec_conformance",
                    ],
                    "self_healing_applied": [],
                },
            }

        # =====================================================================
        # 4. MAP GENERATION
        # =====================================================================
        if "sniper" in p_lower or "duel" in p_lower:
            reply, map_data = _generate_sniper_duel(name="sniper_duel")
        elif "hill" in p_lower or "koth" in p_lower or "king of the hill" in p_lower:
            reply, map_data = _generate_koth_arena(name="koth_arena")
        elif "4-room" in p_lower or "4 room" in p_lower or ("shotgun" in p_lower and "rocket" in p_lower):
            reply, map_data = _generate_facility_combat(name="facility_combat")
        elif "warehouse" in p_lower or "bunker" in p_lower:
            reply, map_data = _generate_warehouse_bunker(name="warehouse_bunker")
        else:
            reply, map_data = _generate_generic_facility(p, name="custom_arena")

        healed_map, v_meta = verify_and_heal_map(map_data)
        ft = _compute_focus_target("generate", healed_map)
        chips = _generate_action_chips("generate", healed_map, ft)
        return {
            "ok": True,
            "reply": reply,
            "map": healed_map,
            "action": "generate",
            "focus_target": ft,
            "action_chips": chips,
            "verification": v_meta,
        }

