"""Tests for UJ-18: Interactive 3D Object Vitrine and Catalog Generation.

Validates parsing of constants.h MODEL_* identifiers, keyword filtering,
3D grid layout synthesis (8-column grid, 700-unit spacing, spawn pad 0),
Markdown visual legend generation, and map rendering.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[1]

from tools.pdmap.gen_object_catalog import (
    CONSTANTS,
    COLS,
    SPACING,
    Y,
    build,
    parse_models,
    render_map,
    select,
)


def test_parse_models_from_constants():
    """Verify parse_models extracts all MODEL_* definitions from constants.h."""
    assert CONSTANTS.is_file(), f"constants.h not found at {CONSTANTS}"
    models = parse_models()

    assert len(models) >= 400, f"Expected >= 400 models, parsed {len(models)}"
    names = [name for name, _ in models]
    ids = [mid for _, mid in models]

    # All names must start with MODEL_
    for name in names:
        assert name.startswith("MODEL_"), f"Invalid model identifier: {name}"

    # All IDs must be non-negative integers
    for mid in ids:
        assert isinstance(mid, int) and mid >= 0, f"Invalid model ID: {mid}"

    # Check key well-known models
    assert "MODEL_CRYPTDOOR1B" in names
    assert "MODEL_DOORCONSOLE" in names
    assert "MODEL_CHRFALCON2" in names or any("FALCON" in n for n in names)


def test_select_keyword_filtering():
    """Verify select() accurately filters models by keywords case-insensitively."""
    models = parse_models()

    # Filter for 'door'
    doors = select(models, ["door"], want_all=False)
    assert len(doors) >= 80, f"Expected >= 80 door models, found {len(doors)}"
    for name, _ in doors:
        assert "door" in name.lower()

    # Filter for multiple keywords: 'desk', 'chair', 'console'
    office_props = select(models, ["desk", "chair", "console"], want_all=False)
    assert len(office_props) > 0
    for name, _ in office_props:
        nl = name.lower()
        assert "desk" in nl or "chair" in nl or "console" in nl

    # Filter with want_all=True returns entire set
    all_models = select(models, ["door"], want_all=True)
    assert len(all_models) == len(models)


def test_build_3d_grid_layout_and_legend():
    """Verify build() generates compliant 3D grid layout and visual legend."""
    models = [
        ("MODEL_DOOR1", 0x0010),
        ("MODEL_DOOR2", 0x0015),
        ("MODEL_DOOR3", 0x0018),
        ("MODEL_DOOR4", 0x0019),
        ("MODEL_DOOR5", 0x001A),
        ("MODEL_DOOR6", 0x001B),
        ("MODEL_DOOR7", 0x001C),
        ("MODEL_DOOR8", 0x001D),
        ("MODEL_DOOR9", 0x001E),
    ]

    spec, legend = build(models)

    # Validate specification envelope
    assert spec["name"] == "learn_33_object_catalog"
    assert spec["center_marker"] is True
    assert spec["box_height"] == 3000
    assert spec["box_half"] >= 3000.0

    pads = spec["pads"]
    # 1 spawn pad + 9 prop pads = 10 total pads
    assert len(pads) == 10

    # Spawn pad (index 0) invariants
    spawn = pads[0]
    assert spawn["index"] == 0
    assert spawn["type"] == "spawn"
    assert spawn["x"] == 0
    assert spawn["y"] == Y
    assert spawn["room"] == 1
    # Spawn should be placed south of the grid
    assert spawn["z"] < 0

    # Prop pads invariants (indices 1..9)
    assert len(legend) == 9
    for i, (name, mid) in enumerate(models):
        pad = pads[i + 1]
        leg = legend[i]

        col = i % COLS
        row = i // COLS
        expected_x = (col - (COLS - 1) / 2) * SPACING
        expected_z = (row - (2 - 1) / 2) * SPACING  # 9 models with COLS=8 -> 2 rows

        assert pad["index"] == i + 1
        assert pad["type"] == "prop"
        assert pad["model"] == mid
        assert pad["x"] == expected_x
        assert pad["z"] == expected_z
        assert pad["y"] == 0
        assert pad["room"] == 1

        assert leg["cell"] == f"r{row}c{col}"
        assert leg["model"] == name
        assert leg["id"] == f"0x{mid:04X}"
        assert leg["x"] == round(expected_x)
        assert leg["z"] == round(expected_z)


def test_render_map_output(tmp_path):
    """Verify render_map creates a valid PNG visual top-down map via Matplotlib or PIL fallback."""
    models = parse_models()
    test_models = select(models, ["doorconsole"], want_all=False)
    if not test_models:
        test_models = models[:4]

    _, legend = build(test_models)
    out_png = tmp_path / "test_catalog_map.png"

    render_map(legend, out_png)
    assert out_png.is_file()
    assert out_png.stat().st_size > 1000

