import os
import json
from tools.pdmap.from_json import EditorMapSpec

HERE = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.abspath(os.path.join(HERE, "..", "..", "journal", "uff_viewer", "maps", "parade_map.json"))

BOX_HALF = 5000.0
BOX_HEIGHT = 3000.0
# Full museum districts mode
SEG_MODE = "parade_districts"
RETAIL_GEOMETRY = True


def load_spec() -> EditorMapSpec:
    if not os.path.exists(JSON_PATH):
        raise FileNotFoundError(f"Parade JSON descriptor not found at {JSON_PATH}")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return EditorMapSpec.from_json(data, deploy_name="parade")


def build():
    spec = load_spec()
    return spec.mapdef


def build_tiles_json():
    spec = load_spec()
    return spec.tiles_json()
