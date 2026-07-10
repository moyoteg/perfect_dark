"""Animation parade test map — registered stage ``STAGE_ANIMLAB`` (0x82)."""

import os
import json
from tools.pdmap.from_json import EditorMapSpec
from tools.pdmap.builders import floor_box_with_parade_zones
from tools.pdmap.anim_catalog import (
    parade_district_markers,
    parade_slot_markers,
    parade_special_marker,
    parade_zone_half,
    parade_zone_markers,
)

HERE = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.abspath(os.path.join(HERE, "..", "..", "journal", "uff_viewer", "maps", "animlab_map.json"))

BOX_HALF = 32000.0
BOX_HEIGHT = 3000.0
SEG_MODE = "parade"
RETAIL_GEOMETRY = True


def load_spec() -> EditorMapSpec:
    if not os.path.exists(JSON_PATH):
        raise FileNotFoundError(f"Animation Lab JSON descriptor not found at {JSON_PATH}")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return EditorMapSpec.from_json(data, deploy_name="animlab")


def build():
    spec = load_spec()
    return spec.mapdef


def build_tiles_json():
    spec = load_spec()
    slots = parade_slot_markers() + [parade_special_marker()]
    return floor_box_with_parade_zones(
        "animlab",
        half=spec.box_half,
        y=0.0,
        slots=slots,
        zones=parade_zone_markers(),
        districts=parade_district_markers(),
        zone_half=parade_zone_half(),
    )
