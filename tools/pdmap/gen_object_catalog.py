#!/usr/bin/env python3
"""Object catalog generator — a test map that lays out prop MODELs in a labeled grid so
you can SEE which model is a door / desk / computer (agent-office curriculum tool).

Parses MODEL_* from constants.h, filters by keyword, and emits a curriculum-style JSON
(deploy-as uff) plus a legend + top-down map (PNG) that says which grid cell is which
model. Walk the catalog, note the position of the object that looks right, cross-reference
the legend for its model id.

    python3 tools/pdmap/gen_object_catalog.py door        # door models only
    python3 tools/pdmap/gen_object_catalog.py desk chair console monitor computer
    python3 tools/pdmap/gen_object_catalog.py --all       # everything (big)

Writes:
    journal/map_learn/maps/learn_33_object_catalog.json   (run: play-learn-step.sh 33)
    journal/agent_office/object_catalog_<filter>.md        (legend: cell -> model)
    journal/agent_office/object_catalog_<filter>.png       (top-down map)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONSTANTS = REPO / "src" / "include" / "constants.h"

COLS = 8            # models per row
SPACING = 700.0     # world units between models
Y = 10.0


def parse_models() -> list[tuple[str, int]]:
    """(name, id) for every MODEL_* constant."""
    out = []
    rx = re.compile(r"#define\s+(MODEL_\w+)\s+(0x[0-9A-Fa-f]+|\d+)")
    for line in CONSTANTS.read_text(errors="ignore").splitlines():
        m = rx.search(line)
        if m:
            out.append((m.group(1), int(m.group(2), 0)))
    return out


def select(models, keywords, want_all):
    if want_all:
        return models
    kws = [k.lower() for k in keywords]
    return [(n, i) for n, i in models if any(k in n.lower() for k in kws)]


def build(models) -> tuple[dict, list[dict]]:
    """Curriculum JSON (grid of prop pads) + legend rows."""
    n = len(models)
    rows = (n + COLS - 1) // COLS
    half = max(3000.0, (max(COLS, rows) * SPACING) / 2 + 1000)

    pads = [{"index": 0, "type": "spawn", "x": 0, "y": Y,
             "z": -(rows * SPACING) / 2 - 900, "room": 1}]
    legend = []
    idx = 1
    for k, (name, mid) in enumerate(models):
        col, row = k % COLS, k // COLS
        x = (col - (COLS - 1) / 2) * SPACING
        z = (row - (rows - 1) / 2) * SPACING
        pads.append({"index": idx, "type": "prop", "x": x, "y": 0, "z": z,
                     "room": 1, "model": mid})
        legend.append({"cell": f"r{row}c{col}", "x": round(x), "z": round(z),
                       "model": name, "id": f"0x{mid:04X}"})
        idx += 1

    return {"name": "learn_33_object_catalog", "box_half": half, "box_height": 3000,
            "center_marker": True, "pads": pads}, legend


def render_map(legend, out_png):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(min(20, COLS * 1.6), 12))
        for row in legend:
            ax.plot(row["x"], row["z"], "s", color="#48f", ms=8)
            ax.annotate(f'{row["model"].replace("MODEL_","")}\n{row["id"]}',
                        (row["x"], row["z"]), fontsize=6, ha="center", va="bottom")
        spawn_z = min(r["z"] for r in legend) - 900
        ax.plot(0, spawn_z, "*", color="orange", ms=20)
        ax.annotate("SPAWN", (0, spawn_z), color="darkorange", fontsize=9)
        ax.set_aspect("equal"); ax.grid(alpha=0.3); ax.invert_yaxis()
        ax.set_title("Object catalog — walk from SPAWN (bottom); each square is a model")
        plt.tight_layout(); plt.savefig(out_png, dpi=90); plt.close()
    except (ImportError, Exception):
        # High-fidelity PIL fallback when matplotlib is unavailable
        from PIL import Image, ImageDraw
        xs = [r["x"] for r in legend] + [0]
        zs = [r["z"] for r in legend] + [min(r["z"] for r in legend) - 900]
        min_x, max_x = min(xs) - 400, max(xs) + 400
        min_z, max_z = min(zs) - 400, max(zs) + 400
        w = 1200
        h = max(600, int(1200 * (max_z - min_z) / max(1, (max_x - min_x))))
        img = Image.new("RGBA", (w, h), (20, 24, 33, 255))
        draw = ImageDraw.Draw(img)

        def to_img(wx, wz):
            ix = int((wx - min_x) / (max_x - min_x) * (w - 120) + 60)
            iz = int((wz - min_z) / (max_z - min_z) * (h - 120) + 60)
            return ix, iz

        for row in legend:
            ix, iz = to_img(row["x"], row["z"])
            draw.rectangle([ix - 6, iz - 6, ix + 6, iz + 6], fill=(68, 136, 255, 255))
            label = f"{row['model'].replace('MODEL_','')}\n{row['id']}"
            draw.text((ix, iz + 10), label, fill=(220, 225, 235, 255), anchor="mt")

        sx, sz = to_img(0, min(r["z"] for r in legend) - 900)
        draw.text((sx, sz), "SPAWN", fill=(255, 165, 0, 255), anchor="mm")
        out_p = Path(out_png)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_p, format="PNG")


def main():
    args = [a for a in sys.argv[1:] if a != "--all"]
    want_all = "--all" in sys.argv
    keywords = args or ["door"]
    models = select(parse_models(), keywords, want_all)
    if not models:
        print("No models match", keywords); return
    tag = "all" if want_all else "_".join(keywords)

    spec, legend = build(models)
    (REPO / "journal/map_learn/maps/learn_33_object_catalog.json").write_text(
        json.dumps(spec, indent=2) + "\n")

    md = [f"# Object catalog — filter: {tag} ({len(models)} models)", "",
          "Walk from SPAWN; find the object that looks right, read its model here.", "",
          "| cell | model | id | x | z |", "|------|-------|----|---|---|"]
    md += [f'| {r["cell"]} | `{r["model"]}` | {r["id"]} | {r["x"]} | {r["z"]} |' for r in legend]
    (REPO / f"journal/agent_office/object_catalog_{tag}.md").write_text("\n".join(md) + "\n")

    try:
        render_map(legend, REPO / f"journal/agent_office/object_catalog_{tag}.png")
    except Exception as e:  # noqa: BLE001
        print("map render skipped:", e)

    print(f"catalog: {len(models)} models (filter={tag})")
    print("  map:  journal/map_learn/maps/learn_33_object_catalog.json")
    print(f"  legend: journal/agent_office/object_catalog_{tag}.md")
    print("  run:  ./scripts/play-learn-step.sh 33   (after registering step 33 / deploy-as uff)")


if __name__ == "__main__":
    main()
