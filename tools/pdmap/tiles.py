import json
import os

from .core import ROOT, ROMID


_DEFAULT_FLAGS = {
    "flag0001": True, "flag0002": True, "flag0004": False,
    "flag0008": True, "flag0010": True, "flag0020": False,
    "ladder": False, "flag0080": False, "flag0100": False,
    "underwater": False, "flag0400": False, "aibotcrouch": False,
    "aibotduck": False, "flag2000": False, "die": False,
    "climbableledge": False,
}


def copy_tiles_from_template(name: str, template_name: str = "mp14") -> str:
    in_path = os.path.join(ROOT, "src", "assets", ROMID, "tiles", f"{template_name}.json")
    out_path = os.path.join(ROOT, "src", "assets", ROMID, "tiles", f"{name}.json")

    with open(in_path) as f:
        data = json.load(f)

    rooms = {}
    for key, tiles in data["rooms"].items():
        rooms[key.replace(template_name.upper(), name.upper())] = tiles
    data["rooms"] = rooms

    with open(out_path, "w") as f:
        json.dump(data, f, indent=4)

    return out_path


def gen_room_tiles(name: str, tiles_by_room: dict) -> str:
    rooms = {}
    for room_key, tile_list in tiles_by_room.items():
        rooms[room_key] = tile_list

    data = {"rooms": rooms}

    out_path = os.path.join(ROOT, "src", "assets", ROMID, "tiles", f"{name}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(data, f, indent=4)
    return out_path


def import_obj_to_tiles(obj_path: str, map_name: str, default_floortype: str = "default") -> dict:
    """Parses a Wavefront .obj file and translates it into N64 room tiles JSON."""
    vertices = []
    rooms = {}
    current_room_idx = 1
    current_floortype = default_floortype

    def get_room_key(idx: int) -> str:
        return f"ROOM_{map_name.upper()}_{idx:04X}"

    # Initialize room 0 (always required in Perfect Dark tiles)
    rooms[get_room_key(0)] = []
    # Initialize first room
    rooms[get_room_key(current_room_idx)] = []

    with open(obj_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            cmd = parts[0]

            if cmd == "v":
                # Parse vertex coordinates
                x = int(round(float(parts[1])))
                y = int(round(float(parts[2])))
                z = int(round(float(parts[3])))
                vertices.append({"x": x, "y": y, "z": z})

            elif cmd in ("g", "o"):
                # Group/object indicates a new room
                group_name = parts[1].lower()
                import re
                match = re.search(r"\d+", group_name)
                if match:
                    current_room_idx = int(match.group())
                else:
                    current_room_idx += 1
                
                room_key = get_room_key(current_room_idx)
                if room_key not in rooms:
                    rooms[room_key] = []

            elif cmd == "usemtl":
                # Material maps to floor type
                mat = parts[1].lower()
                # If material name contains known floor types, map them
                for ft in ("dirt", "grass", "metal", "stone", "wood", "water", "carpet", "snow", "sand"):
                    if ft in mat:
                        current_floortype = ft
                        break
                else:
                    current_floortype = default_floortype

            elif cmd == "f":
                # Parse face indices
                face_vertices = []
                for token in parts[1:]:
                    idx = int(token.split("/")[0])
                    if idx > 0:
                        v = vertices[idx - 1]
                    else:
                        v = vertices[len(vertices) + idx]
                    face_vertices.append(v)

                tile = {
                    "floortype": current_floortype,
                    "floorcolour": 4095,
                    "vertices": face_vertices
                }
                tile.update(_DEFAULT_FLAGS)

                room_key = get_room_key(current_room_idx)
                rooms[room_key].append(tile)

    # Clean up empty rooms (but preserve room 0!)
    non_empty_rooms = {k: v for k, v in rooms.items() if v or k.endswith("_0000")}
    if len(non_empty_rooms) <= 1:
        # If no faces were grouped, put everything under room 1
        non_empty_rooms = {get_room_key(0): [], get_room_key(1): []}

    return {"rooms": non_empty_rooms}
