#!/usr/bin/env python3
"""List Perfect Dark animation IDs from src/assets/<ROMID>/animations.json.

Examples:
  python3 tools/list_animations.py                    # first 30 anims
  python3 tools/list_animations.py --search yawn
  python3 tools/list_animations.py --id ANIM_SNEEZE
  python3 tools/list_animations.py --index 154
  python3 tools/list_animations.py --named-only       # skip ANIM_0000-style stubs
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_anims(romid: str) -> list[dict]:
    path = os.path.join(ROOT, "src", "assets", romid, "animations.json")
    if not os.path.isfile(path):
        raise SystemExit(f"animations.json not found for ROMID={romid!r}: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt_row(i: int, row: dict) -> str:
    flags = []
    for bit, name in ((1, "abs-trans"), (2, "repeat"), (4, "?4"), (8, "?8")):
        key = f"flag0{bit}"
        if row.get(key):
            flags.append(name)
    flag_s = ",".join(flags) if flags else "-"
    return (
        f"{i:4d}  {row['id']:<28}  "
        f"frames={row['numframes']:4d}  bpf={row['bytesperframe']:3d}  "
        f"file={row['file']}  flags={flag_s}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="List animation enum IDs")
    parser.add_argument("--romid", default=os.environ.get("ROMID", "ntsc-final"))
    parser.add_argument("--search", "-s", help="Substring match on id (case insensitive)")
    parser.add_argument("--id", help="Exact ANIM_* name")
    parser.add_argument("--index", type=int, help="Numeric anim index")
    parser.add_argument("--named-only", action="store_true", help="Hide ANIM_NNNN hex stubs")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    anims = load_anims(args.romid)

    if args.index is not None:
        if args.index < 0 or args.index >= len(anims):
            raise SystemExit(f"index out of range: {args.index} (max {len(anims)-1})")
        print(fmt_row(args.index, anims[args.index]))
        return

    if args.id:
        for i, row in enumerate(anims):
            if row["id"] == args.id:
                print(fmt_row(i, row))
                return
        raise SystemExit(f"unknown id: {args.id}")

    hex_stub = re.compile(r"^ANIM_[0-9A-F]{4}$")
    shown = 0
    for i, row in enumerate(anims):
        if args.named_only and hex_stub.match(row["id"]):
            continue
        if args.search and args.search.lower() not in row["id"].lower():
            continue
        print(fmt_row(i, row))
        shown += 1
        if args.limit and shown >= args.limit:
            break

    if shown == 0:
        print("(no matches)", file=sys.stderr)
    elif not args.search and not args.named_only:
        print(f"\n… {len(anims)} total. Use --search, --id, or --limit to narrow.")


if __name__ == "__main__":
    main()
