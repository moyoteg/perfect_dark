#!/usr/bin/env python3
"""Batch exporter for src/levels/*.py modules to Map Editor JSON.

Discovers and converts all custom procedural levels in src/levels/ into
canonical editor JSON files in journal/uff_viewer/maps/.
"""

import argparse
import importlib
import json
import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.pdmap.from_json import EditorMapSpec
from tools.pdmap.level_to_editor import mapdef_to_editor_json


def export_levels(
    levels_dir: str | None = None,
    output_dir: str | None = None,
    overwrite: bool = True,
) -> tuple[int, int, list[str]]:
    """Export all runnable level modules in levels_dir to output_dir."""
    if levels_dir is None:
        levels_dir = os.path.join(REPO_ROOT, "src", "levels")
    if output_dir is None:
        output_dir = os.path.join(REPO_ROOT, "journal", "uff_viewer", "maps")

    os.makedirs(output_dir, exist_ok=True)

    files = sorted(
        [
            f[:-3]
            for f in os.listdir(levels_dir)
            if f.endswith(".py") and not f.startswith("__")
        ]
    )

    exported = 0
    skipped = 0
    errors = []

    for name in files:
        target_json = os.path.join(output_dir, f"{name}.json")
        if not overwrite and os.path.exists(target_json):
            skipped += 1
            continue

        try:
            mod = importlib.import_module(f"src.levels.{name}")
            if not hasattr(mod, "build"):
                skipped += 1
                continue

            m = mod.build()
            editor_dict = mapdef_to_editor_json(m)
            # Validate that it satisfies EditorMapSpec
            _ = EditorMapSpec.from_json(editor_dict)

            with open(target_json, "w", encoding="utf-8") as fp:
                json.dump(editor_dict, fp, indent=2)

            exported += 1
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    return exported, skipped, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Export src/levels/*.py to Editor JSON")
    parser.add_argument("--levels-dir", default=None, help="Path to src/levels directory")
    parser.add_argument("--output-dir", default=None, help="Target JSON directory")
    parser.add_argument("--no-overwrite", action="store_true", help="Do not overwrite existing JSONs")
    args = parser.parse_args()

    exported, skipped, errors = export_levels(
        levels_dir=args.levels_dir,
        output_dir=args.output_dir,
        overwrite=not args.no_overwrite,
    )

    print(f"Exported: {exported}, Skipped: {skipped}, Errors: {len(errors)}")
    if errors:
        for err in errors:
            print(f"  ERROR: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
