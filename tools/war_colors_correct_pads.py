#!/usr/bin/env python3
"""Probe Conker floor Y at War Colors spawn/weapon pads and write corrected bg_mp13_padsZ.

Uses the engine's own ROM-loaded pad blob: probes cdFindGround from high Y at each
pad XZ, patches packed INTPOS Y in memory, then writes RareZip to mod_kakariko.
Avoids mkpads rebuild (which does not match the runtime ROM pad envelope).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KAKARIKO_PADS = os.path.join(ROOT, "mods", "mod_kakariko", "files", "bgdata", "bg_mp13_padsZ")
DEFAULT_LOG = os.path.join(ROOT, "journal", "map_learn", ".war_colors_pad_probe.log")

PROBE_RE = re.compile(
    r"PROBE_PAD index=(\d+) x=([-\d.]+) y=([-\d.]+) z=([-\d.]+) "
    r"ground=([-\d.]+) room=(-?\d+) usable=(\d+) patched=(\d+)"
)


def run_probe(
    pd_binary: str,
    log_path: str,
    write_pads: str | None,
    *,
    probe_all: bool = False,
) -> str:
    os.makedirs(os.path.dirname(write_pads or KAKARIKO_PADS), exist_ok=True)
    if os.path.isfile(KAKARIKO_PADS) and write_pads and not probe_all:
        os.remove(KAKARIKO_PADS)

    cmd = [
        pd_binary,
        "--boot-stage",
        "0x5b",
        "--skip-intro",
        "--scenario-0",
        "--basedir",
        os.path.join(ROOT, "data"),
        "--moddir",
        os.path.join(ROOT, "mods", "mod_allinone"),
        "--kakarikomoddir",
        os.path.join(ROOT, "mods", "mod_kakariko"),
        "--savedir",
        ROOT,
        "--solo",
        "--num-sims",
        "0",
    ]
    if probe_all:
        cmd.append("--probe-war-colors-all")
        if write_pads:
            cmd.extend(["--write-corrected-pads", write_pads])
    else:
        cmd.append("--probe-war-colors-pads")
        if write_pads:
            cmd.extend(["--write-corrected-pads", write_pads])

    env = {**os.environ, "SDL_AUDIODRIVER": "dummy"}
    if sys.platform != "darwin":
        env["SDL_VIDEODRIVER"] = "dummy"

    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=45,
        env=env,
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    with open(log_path, "w", encoding="utf-8") as fp:
        fp.write(combined)
    if proc.returncode != 0:
        raise RuntimeError(
            f"probe exited {proc.returncode}; see {log_path}\n{combined[-3000:]}"
        )
    return combined


def parse_probe_log(text: str) -> list[dict]:
    rows: list[dict] = []
    for line in text.splitlines():
        m = PROBE_RE.search(line.strip())
        if not m:
            continue
        rows.append(
            {
                "index": int(m.group(1)),
                "x": float(m.group(2)),
                "y": float(m.group(3)),
                "z": float(m.group(4)),
                "ground": float(m.group(5)),
                "room": int(m.group(6)),
                "usable": int(m.group(7)) == 1,
                "patched": int(m.group(8)) == 1,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pd", default=os.path.join(ROOT, "build", "pd.arm64"))
    parser.add_argument("--log", default=DEFAULT_LOG)
    parser.add_argument("--output", default=KAKARIKO_PADS)
    parser.add_argument("--no-probe", action="store_true")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Probe all 219 mp13 pads; with default output, patch Y for every usable pad",
    )
    args = parser.parse_args()

    if args.no_probe:
        with open(args.log, encoding="utf-8") as fp:
            log_text = fp.read()
    else:
        if not os.path.isfile(args.pd):
            print(f"ERROR: missing binary {args.pd}", file=sys.stderr)
            return 1
        log_text = run_probe(
            args.pd,
            args.log,
            args.output,
            probe_all=args.all,
        )

    rows = parse_probe_log(log_text)
    min_rows = 219 if args.all else 22
    if len(rows) < min_rows and not args.all:
        print(f"ERROR: parsed {len(rows)}/22 probe rows from {args.log}", file=sys.stderr)
        return 1

    patched = sum(1 for r in rows if r["patched"])
    usable = sum(1 for r in rows if r["usable"])
    print(f"probe: usable={usable}/{len(rows)} patched={patched}/{len(rows)}")
    for row in rows:
        status = "patched" if row["patched"] else ("usable" if row["usable"] else "VOID")
        print(
            f"  pad {row['index']:3d}: ({row['x']:.0f},{row['y']:.0f},{row['z']:.0f}) "
            f"ground={row['ground']:.0f} room={row['room']} [{status}]"
        )

    if not args.no_probe and not args.all:
        if not os.path.isfile(args.output):
            print(f"ERROR: expected output pads at {args.output}", file=sys.stderr)
            return 1
        print(f"deployed: {args.output} ({os.path.getsize(args.output)} bytes)")
    elif not args.no_probe and args.all and os.path.isfile(args.output):
        print(f"deployed: {args.output} ({os.path.getsize(args.output)} bytes, all usable Y patches)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
