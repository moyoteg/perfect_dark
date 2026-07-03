"""Load retail stage pad JSON into MapDef (preserve indices for real geometry overlays)."""

from __future__ import annotations

import json
import os

from .core import MapDef, Pad, ROOT, ROMID


def retail_pads_json_path(stage: str) -> str:
    return os.path.join(ROOT, "src", "assets", ROMID, "pads", f"{stage}.json")


def load_retail_pads(mapdef: MapDef, stage: str = "mp13", *, default_room: int = 1) -> int:
    """Append retail pads to *mapdef* in file order; returns pad count loaded."""
    path = retail_pads_json_path(stage)
    with open(path, encoding="utf-8") as fp:
        data = json.load(fp)

    start = len(mapdef.pads)
    for offset, entry in enumerate(data.get("pads", [])):
        pos = entry["pos"]
        direction = entry.get("dir", [0.0, 0.0, 1.0])
        up = entry.get("up", [0.0, 1.0, 0.0])
        pad = Pad(
            index=start + offset,
            x=float(pos[0]),
            y=float(pos[1]),
            z=float(pos[2]),
            dir_x=float(direction[0]),
            dir_y=float(direction[1]),
            dir_z=float(direction[2]),
            up_x=float(up[0]),
            up_y=float(up[1]),
            up_z=float(up[2]),
            room=int(entry.get("room", default_room)),
            liftnum=int(entry.get("liftnum", 0)),
            xmin=float(entry.get("xmin", -100.0)),
            xmax=float(entry.get("xmax", 100.0)),
            ymin=float(entry.get("ymin", -100.0)),
            ymax=float(entry.get("ymax", 100.0)),
            zmin=float(entry.get("zmin", -100.0)),
            zmax=float(entry.get("zmax", 100.0)),
            aiwaitlift=bool(entry.get("aiwaitlift", False)),
            aionlift=bool(entry.get("aionlift", False)),
            aiwalkdirect=bool(entry.get("aiwalkdirect", False)),
            aidrop=bool(entry.get("aidrop", False)),
            aicrouch=bool(entry.get("aicrouch", False)),
            aiignorey=bool(entry.get("aiignorey", False)),
            aiduck=bool(entry.get("aiduck", False)),
        )
        mapdef.pads.append(pad)
    return len(data.get("pads", []))


def pick_team_spawn_pad_indices(
    stage: str,
    *,
    team: int,
    count: int = 32,
) -> list[int]:
    """Pick evenly spaced retail pad indices for team spawns on *stage* geometry."""
    path = retail_pads_json_path(stage)
    with open(path, encoding="utf-8") as fp:
        pads = json.load(fp)["pads"]

    if team == 0:
        candidates = [
            (i, p["pos"])
            for i, p in enumerate(pads)
            if p["pos"][2] > 800 and p["pos"][1] >= 80
        ]
        candidates.sort(key=lambda t: (-t[1][2], t[1][0]))
    else:
        candidates = [
            (i, p["pos"])
            for i, p in enumerate(pads)
            if p["pos"][2] < -500 and -800 <= p["pos"][1] <= -300
        ]
        candidates.sort(key=lambda t: (t[1][2], t[1][0]))

    if len(candidates) <= count:
        return [i for i, _ in candidates]

    step = len(candidates) / count
    return [candidates[int(k * step)][0] for k in range(count)]
