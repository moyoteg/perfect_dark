"""Tests for the Generative Map Assistant and Chat Backend.

Validates conversational explanations, deterministic semantic spatial grammar
map synthesis, incremental pad authoring, engine invariants, and EditorMapSpec compilation.
Strictly adheres to the Universal Calibrated Zero-Emoji Standard.
"""

from __future__ import annotations

import copy
import json
import time
import unittest.mock as mock
import pytest

from tools.pdmap.generative_assistant import (
    GenerativeAssistant,
    verify_and_heal_map,
    WEAPON_SNIPERRIFLE,
    WEAPON_SUPERDRAGON,
    WEAPON_SHOTGUN,
    WEAPON_FALCON2,
    WEAPON_ROCKETLAUNCHER,
    AMMOTYPE_RIFLE,
    AMMOTYPE_SHOTGUN,
    AMMOTYPE_ROCKET,
)
from tools.pdmap.from_json import EditorMapSpec
from tools.pdmap.validate import validate_mapdef


def assert_no_emojis(text: str) -> None:
    """Enforce the Universal Calibrated Zero-Emoji Standard."""
    for ch in text:
        code = ord(ch)
        is_emoji = (
            (0x1F600 <= code <= 0x1F64F)
            or (0x1F300 <= code <= 0x1F5FF)
            or (0x1F680 <= code <= 0x1F6FF)
            or (0x1F900 <= code <= 0x1F9FF)
            or (0x1FA00 <= code <= 0x1FAFF)
            or (0x2600 <= code <= 0x26FF)
            or (0x2700 <= code <= 0x27BF)
        )
        assert not is_emoji, f"Unicode emoji {ch!r} (U+{code:04X}) detected in text: {text!r}"


@pytest.fixture
def assistant() -> GenerativeAssistant:
    """Fixture providing a deterministic GenerativeAssistant instance."""
    return GenerativeAssistant(enable_ollama=False)


class TestGenerativeAssistantChat:
    """Test suite for generative assistant prompts, generation, and modifications."""

    @pytest.mark.parametrize(
        "prompt",
        [
            "explain to a regular person",
            "how does this work",
            "what is this",
            "what is perfect dark kit",
            "demystify how this tool works",
        ],
    )
    def test_conversational_explanation(self, assistant: GenerativeAssistant, prompt: str):
        """Verify conversational demystification returns educational text with zero emojis."""
        res = assistant.process_prompt(prompt)
        assert res["ok"] is True
        assert res["action"] == "explain"
        assert res["map"] is None
        assert isinstance(res["reply"], str)
        assert "Perfect Dark Kit" in res["reply"]
        assert "Pads" in res["reply"] or "pads" in res["reply"]
        assert_no_emojis(res["reply"])

    def test_two_room_sniper_duel_generation(self, assistant: GenerativeAssistant):
        """Verify 2-room sniper duel arena satisfies room count, spawns, weapons, and Y=10."""
        res = assistant.process_prompt("2-room sniper duel")
        assert res["ok"] is True
        assert res["action"] == "generate"
        assert_no_emojis(res["reply"])

        m = res["map"]
        assert isinstance(m, dict)
        assert m["name"] == "sniper_duel"
        assert m["level_module"] == "uff"
        assert m["box_half"] == 5000
        assert m["box_height"] == 3000
        assert m["spawn_y"] == 10

        # Assert 2 rooms
        rooms = m["rooms"]
        assert len(rooms) == 2
        assert rooms[0]["room"] == 1
        assert rooms[1]["room"] == 2

        # Assert at least 1 portal connecting them
        assert len(m["portals"]) >= 1
        portal = m["portals"][0]
        assert portal["room1"] in (1, 2)
        assert portal["room2"] in (1, 2)

        # Assert pads: >= 4 spawns, sniper weapon pads, all Y=10, contiguous indices
        pads = m["pads"]
        assert len(pads) >= 6
        assert [p["index"] for p in pads] == list(range(len(pads)))

        for p in pads:
            assert p["y"] == 10.0, f"Pad {p['index']} Y must be 10, got {p['y']}"
            assert p["room"] in (1, 2), f"Pad {p['index']} room must be 1 or 2, got {p['room']}"

        spawns = [p for p in pads if p["type"] == "spawn"]
        assert len(spawns) >= 4

        sniper_pads = [p for p in pads if p.get("type") == "weapon" and p.get("weapon") == WEAPON_SNIPERRIFLE]
        assert len(sniper_pads) >= 2

        ammo_pads = [p for p in pads if p.get("type") == "ammo" and p.get("ammoType") == AMMOTYPE_RIFLE]
        assert len(ammo_pads) >= 2

    def test_symmetrical_sniper_facility_generation(self, assistant: GenerativeAssistant):
        """Verify 'symmetrical sniper facility' creates the balanced sniper layout."""
        res = assistant.process_prompt("symmetrical sniper facility")
        assert res["ok"] is True
        assert res["action"] == "generate"
        m = res["map"]
        assert len(m["rooms"]) == 2
        assert any(p.get("weapon") == WEAPON_SNIPERRIFLE for p in m["pads"])
        assert all(p["y"] == 10 for p in m["pads"])
        assert_no_emojis(res["reply"])

    def test_koth_generation(self, assistant: GenerativeAssistant):
        """Verify King of the Hill arena synthesizes hill scenario pad and combat layout."""
        res = assistant.process_prompt("king of the hill arena")
        assert res["ok"] is True
        assert res["action"] == "generate"
        assert_no_emojis(res["reply"])

        m = res["map"]
        assert m["name"] == "koth_arena"
        pads = m["pads"]

        # Assert hill pad present
        hill_pads = [p for p in pads if p.get("type") == "scenario" and p.get("scenario") == "hill"]
        assert len(hill_pads) >= 1

        # Assert at least 4 spawns
        spawns = [p for p in pads if p["type"] == "spawn"]
        assert len(spawns) >= 4

        # Assert strict invariants
        assert all(p["y"] == 10 for p in pads)
        assert [p["index"] for p in pads] == list(range(len(pads)))

    def test_four_room_facility_generation(self, assistant: GenerativeAssistant):
        """Verify 4-room facility with shotgun & rocket synthesizes 4 rooms and expected weapons."""
        res = assistant.process_prompt("4-room facility with shotgun & rocket")
        assert res["ok"] is True
        assert res["action"] == "generate"
        assert_no_emojis(res["reply"])

        m = res["map"]
        assert len(m["rooms"]) == 4
        assert len(m["portals"]) >= 4

        pads = m["pads"]
        shotguns = [p for p in pads if p.get("weapon") == WEAPON_SHOTGUN]
        rockets = [p for p in pads if p.get("weapon") == WEAPON_ROCKETLAUNCHER]
        assert len(shotguns) >= 1
        assert len(rockets) >= 1

        spawns = [p for p in pads if p["type"] == "spawn"]
        assert len(spawns) >= 4
        assert all(p["y"] == 10 for p in pads)
        assert [p["index"] for p in pads] == list(range(len(pads)))

    def test_warehouse_bunker_generation(self, assistant: GenerativeAssistant):
        """Verify warehouse bunker synthesizes 3 industrial rooms and varied armaments."""
        res = assistant.process_prompt("warehouse bunker")
        assert res["ok"] is True
        assert res["action"] == "generate"
        assert_no_emojis(res["reply"])

        m = res["map"]
        assert len(m["rooms"]) == 3
        pads = m["pads"]
        spawns = [p for p in pads if p["type"] == "spawn"]
        assert len(spawns) >= 4
        assert all(p["y"] == 10 for p in pads)
        assert [p["index"] for p in pads] == list(range(len(pads)))

    def test_incremental_pad_addition_from_empty(self, assistant: GenerativeAssistant):
        """Verify adding pads to None/empty map initializes base facility and appends pads."""
        res = assistant.process_prompt("add two shotgun pads", current_map=None)
        assert res["ok"] is True
        assert res["action"] == "modify"
        assert_no_emojis(res["reply"])

        m = res["map"]
        assert m is not None
        pads = m["pads"]
        # Base facility has 4 spawns (indices 0..3) + 2 shotgun pads (indices 4..5)
        assert len(pads) == 6
        assert [p["index"] for p in pads] == list(range(6))
        assert all(p["y"] == 10.0 for p in pads)

        new_shotguns = [p for p in pads[-2:] if p.get("type") == "weapon" and p.get("weapon") == WEAPON_SHOTGUN]
        assert len(new_shotguns) == 2

    def test_incremental_pad_addition_to_existing(self, assistant: GenerativeAssistant):
        """Verify adding a rocket launcher pad appends with next contiguous index and Y=10."""
        # Generate initial 2-room sniper duel
        initial_res = assistant.process_prompt("2-room sniper duel")
        initial_map = initial_res["map"]
        initial_count = len(initial_map["pads"])

        # Incrementally add rocket launcher
        mod_res = assistant.process_prompt("add rocket launcher", current_map=initial_map)
        assert mod_res["ok"] is True
        assert mod_res["action"] == "modify"
        assert_no_emojis(mod_res["reply"])

        mod_map = mod_res["map"]
        assert len(mod_map["pads"]) == initial_count + 1

        new_pad = mod_map["pads"][-1]
        assert new_pad["index"] == initial_count
        assert new_pad["type"] == "weapon"
        assert new_pad["weapon"] == WEAPON_ROCKETLAUNCHER
        assert new_pad["y"] == 10.0

        # Indices must remain strictly contiguous
        assert [p["index"] for p in mod_map["pads"]] == list(range(len(mod_map["pads"])))
        assert all(p["y"] == 10.0 for p in mod_map["pads"])

    @pytest.mark.parametrize(
        "prompt",
        [
            "2-room sniper duel",
            "king of the hill arena",
            "4-room facility with shotgun & rocket",
            "warehouse bunker",
        ],
    )
    def test_compilation_via_editor_map_spec(self, assistant: GenerativeAssistant, prompt: str):
        """Verify all generated maps compile cleanly via EditorMapSpec.from_json() with 0 errors."""
        res = assistant.process_prompt(prompt)
        map_data = res["map"]

        spec = EditorMapSpec.from_json(map_data)
        assert spec.name == map_data["name"]
        assert spec.box_half == 5000.0
        assert spec.box_height == 3000.0
        assert spec.spawn_y == 10.0
        assert len(spec.rooms) == len(map_data["rooms"])
        assert len(spec.portals) == len(map_data["portals"])
        assert len(spec.mapdef.pads) == len(map_data["pads"])

        # Validate logical invariants
        errors = validate_mapdef(spec.mapdef, tiles_room_count=spec.tiles_room_count())
        assert errors == [], f"Validation failed for prompt '{prompt}': {errors}"

        # Verify multiroom floor tiles generation
        tiles = spec.tiles_json()
        assert "rooms" in tiles
        assert spec.tiles_room_count() == len(map_data["rooms"]) + 1

    def test_modified_map_compilation(self, assistant: GenerativeAssistant):
        """Verify incrementally modified map compiles and validates with 0 errors."""
        base_res = assistant.process_prompt("2-room sniper duel")
        mod_res1 = assistant.process_prompt("add two shotgun pads", current_map=base_res["map"])
        mod_res2 = assistant.process_prompt("add rocket launcher", current_map=mod_res1["map"])

        final_map = mod_res2["map"]
        spec = EditorMapSpec.from_json(final_map)
        errors = validate_mapdef(spec.mapdef, tiles_room_count=spec.tiles_room_count())
        assert errors == [], f"Validation failed on modified map: {errors}"

    def test_ollama_graceful_fallback(self):
        """Verify that when Ollama is unreachable or errors, assistant falls back to grammar."""
        asst = GenerativeAssistant(ollama_url="http://127.0.0.1:99999/unreachable", enable_ollama=True)
        res = asst.process_prompt("2-room sniper duel")
        assert res["ok"] is True
        assert res["action"] == "generate"
        assert len(res["map"]["rooms"]) == 2
        assert len(res["map"]["pads"]) >= 6

    def test_ollama_mocked_success(self):
        """Verify that valid Ollama JSON response is utilized when available."""
        asst = GenerativeAssistant(enable_ollama=True)
        mock_payload = {
            "ok": True,
            "reply": "Generated arena from mock Ollama model.",
            "map": {
                "name": "mock_arena",
                "level_module": "uff",
                "box_half": 5000,
                "box_height": 3000,
                "spawn_y": 10,
                "rooms": [
                    {"room": 1, "name": "r1", "x0": -2000, "x1": 0, "z0": -1000, "z1": 1000, "height": 2000, "floor_y": 0.0},
                    {"room": 2, "name": "r2", "x0": 0, "x1": 2000, "z0": -1000, "z1": 1000, "height": 2000, "floor_y": 0.0},
                ],
                "portals": [
                    {"room1": 1, "room2": 2, "room_from": 1, "room_to": 2, "x": 0, "y": 0, "z": 0, "width": 400, "height": 800}
                ],
                "pads": [
                    {"index": 0, "x": -1000, "y": 10.0, "z": 0, "room": 1, "type": "spawn"},
                    {"index": 1, "x": -800, "y": 10.0, "z": 200, "room": 1, "type": "spawn"},
                    {"index": 2, "x": 1000, "y": 10.0, "z": 0, "room": 2, "type": "spawn"},
                    {"index": 3, "x": 800, "y": 10.0, "z": -200, "room": 2, "type": "spawn"},
                ],
            },
            "action": "generate",
        }

        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.read.return_value = json.dumps({"response": json.dumps(mock_payload)}).encode("utf-8")

        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            res = asst.process_prompt("generate mock map")
            assert res["ok"] is True
            assert res["action"] == "generate"
            assert res["map"]["name"] == "mock_arena"

    def test_ollama_mocked_invalid_fallback(self):
        """Verify that when Ollama returns invalid pads (violating invariants), it falls back."""
        asst = GenerativeAssistant(enable_ollama=True)
        # Invalid payload: pad Y != 10
        mock_payload = {
            "ok": True,
            "reply": "Invalid map",
            "map": {
                "name": "invalid_arena",
                "pads": [
                    {"index": 0, "x": 0, "y": 0.0, "z": 0, "room": 1, "type": "spawn"}
                ],
            },
            "action": "generate",
        }

        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.read.return_value = json.dumps({"response": json.dumps(mock_payload)}).encode("utf-8")

        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            res = asst.process_prompt("2-room sniper duel")
            # Should have rejected invalid mock and fallen back to deterministic generator
            assert res["ok"] is True
            assert res["map"]["name"] == "sniper_duel"
            assert all(p["y"] == 10 for p in res["map"]["pads"])


class TestSelfHealingLadder:
    """Test suite for mechanical verification and self-healing ladder (H1-H4)."""

    def test_contiguous_pad_indices_healed(self):
        """Verify that non-contiguous pad indices are automatically renumbered 0..N-1."""
        broken_map = {
            "name": "broken_indices",
            "level_module": "uff",
            "box_half": 5000,
            "box_height": 3000,
            "spawn_y": 10,
            "rooms": [
                {"room": 1, "name": "r1", "x0": -2000, "x1": 2000, "z0": -2000, "z1": 2000, "height": 2000, "floor_y": 0.0}
            ],
            "portals": [],
            "pads": [
                {"index": 5, "x": -500.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 12, "x": -200.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 20, "x": 200.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 99, "x": 500.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
            ],
        }

        healed, v_meta = verify_and_heal_map(broken_map)
        assert v_meta["passed"] is True
        assert "contiguous_pad_indices" in v_meta["invariants_checked"]
        assert any("renumbered" in h for h in v_meta["self_healing_applied"])
        assert [p["index"] for p in healed["pads"]] == [0, 1, 2, 3]

    def test_y_floor_offset_clamped_to_10(self):
        """Verify that pad Y coordinates < 10.0 or == 0 are strictly clamped to >= 10.0."""
        broken_map = {
            "name": "broken_y",
            "level_module": "uff",
            "box_half": 5000,
            "box_height": 3000,
            "spawn_y": 10,
            "rooms": [
                {"room": 1, "name": "r1", "x0": -2000, "x1": 2000, "z0": -2000, "z1": 2000, "height": 2000, "floor_y": 0.0}
            ],
            "portals": [],
            "pads": [
                {"index": 0, "x": -600.0, "y": 0.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 1, "x": -200.0, "y": -15.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 2, "x": 200.0, "y": 5.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 3, "x": 600.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
            ],
        }

        healed, v_meta = verify_and_heal_map(broken_map)
        assert v_meta["passed"] is True
        assert "y_floor_offset_10" in v_meta["invariants_checked"]
        assert any("clamped" in h for h in v_meta["self_healing_applied"])
        assert all(p["y"] >= 10.0 for p in healed["pads"])
        assert [p["y"] for p in healed["pads"]] == [10.0, 10.0, 10.0, 10.0]

    def test_min_spawns_invariant_promoted(self):
        """Verify that when fewer than 4 spawn pads exist, available non-spawns are promoted to spawns."""
        broken_map = {
            "name": "few_spawns",
            "level_module": "uff",
            "box_half": 5000,
            "box_height": 3000,
            "spawn_y": 10,
            "rooms": [
                {"room": 1, "name": "r1", "x0": -2000, "x1": 2000, "z0": -2000, "z1": 2000, "height": 2000, "floor_y": 0.0}
            ],
            "portals": [],
            "pads": [
                {"index": 0, "x": -600.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 1, "x": -200.0, "y": 10.0, "z": 0.0, "room": 1, "type": "weapon", "weapon": WEAPON_SHOTGUN},
                {"index": 2, "x": 200.0, "y": 10.0, "z": 0.0, "room": 1, "type": "weapon", "weapon": WEAPON_FALCON2},
                {"index": 3, "x": 600.0, "y": 10.0, "z": 0.0, "room": 1, "type": "ammo", "ammoType": AMMOTYPE_SHOTGUN},
            ],
        }

        healed, v_meta = verify_and_heal_map(broken_map)
        assert v_meta["passed"] is True
        assert "min_spawns_ge_4" in v_meta["invariants_checked"]
        assert any("promoted" in h for h in v_meta["self_healing_applied"])
        spawns = [p for p in healed["pads"] if p["type"] == "spawn"]
        assert len(spawns) >= 4

    def test_min_spawns_invariant_synthesized(self):
        """Verify that when total pads < 4, new spawn pads are synthesized to reach min 4."""
        broken_map = {
            "name": "tiny_map",
            "level_module": "uff",
            "box_half": 5000,
            "box_height": 3000,
            "spawn_y": 10,
            "rooms": [
                {"room": 1, "name": "r1", "x0": -2000, "x1": 2000, "z0": -2000, "z1": 2000, "height": 2000, "floor_y": 0.0}
            ],
            "portals": [],
            "pads": [
                {"index": 0, "x": -200.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
            ],
        }

        healed, v_meta = verify_and_heal_map(broken_map)
        assert v_meta["passed"] is True
        assert any("synthesized" in h for h in v_meta["self_healing_applied"])
        spawns = [p for p in healed["pads"] if p["type"] == "spawn"]
        assert len(spawns) >= 4
        assert [p["index"] for p in healed["pads"]] == list(range(len(healed["pads"])))

    def test_room_and_portal_consistency_healed(self):
        """Verify that pads referencing invalid rooms are rebound, and invalid portals are removed."""
        broken_map = {
            "name": "invalid_rooms_and_portals",
            "level_module": "uff",
            "box_half": 5000,
            "box_height": 3000,
            "spawn_y": 10,
            "rooms": [
                {"room": 1, "name": "r1", "x0": -2000, "x1": 0, "z0": -1000, "z1": 1000, "height": 2000, "floor_y": 0.0},
                {"room": 2, "name": "r2", "x0": 0, "x1": 2000, "z0": -1000, "z1": 1000, "height": 2000, "floor_y": 0.0},
            ],
            "portals": [
                {"room1": 1, "room2": 2, "x": 0.0, "y": 0.0, "z": 0.0, "width": 400.0, "height": 800.0},
                {"room1": 1, "room2": 99, "x": 0.0, "y": 0.0, "z": 0.0, "width": 400.0, "height": 800.0},  # Invalid
            ],
            "pads": [
                {"index": 0, "x": -1000.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 1, "x": -800.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 2, "x": 800.0, "y": 10.0, "z": 0.0, "room": 2, "type": "spawn"},
                {"index": 3, "x": 1000.0, "y": 10.0, "z": 0.0, "room": 99, "type": "spawn"},  # Invalid room
            ],
        }

        healed, v_meta = verify_and_heal_map(broken_map)
        assert v_meta["passed"] is True
        assert "room_portal_consistency" in v_meta["invariants_checked"]
        assert any("reassigned" in h for h in v_meta["self_healing_applied"])
        assert any("removed_invalid_portal" in h for h in v_meta["self_healing_applied"])
        assert all(p["room"] in (1, 2) for p in healed["pads"])
        assert len(healed["portals"]) == 1

    def test_fast3d_g_vtx_vertex_batch_clamp(self):
        """Verify that tiles with > 16 vertices are clamped to comply with Fast3D G_VTX limits."""
        map_with_huge_tile = {
            "name": "huge_tile_map",
            "level_module": "uff",
            "box_half": 5000,
            "box_height": 3000,
            "spawn_y": 10,
            "rooms": [
                {"room": 1, "name": "r1", "x0": -2000, "x1": 2000, "z0": -2000, "z1": 2000, "height": 2000, "floor_y": 0.0}
            ],
            "tiles": {
                "rooms": {
                    "r1": [
                        {
                            "vertices": [{"x": i * 10, "y": 0, "z": i * 10} for i in range(25)]
                        }
                    ]
                }
            },
            "pads": [
                {"index": 0, "x": -500.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 1, "x": -200.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 2, "x": 200.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 3, "x": 500.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
            ],
        }

        healed, v_meta = verify_and_heal_map(map_with_huge_tile)
        assert v_meta["passed"] is True
        assert len(healed["tiles"]["rooms"]["r1"][0]["vertices"]) == 16
        assert any("truncated" in h for h in v_meta["self_healing_applied"])

    def test_mapspec_conformance_and_verification_metadata(self):
        """Verify that EditorMapSpec.from_json compiles successfully after self-healing."""
        raw_map = {
            "name": "raw-map-name-WITH-CAPS!",
            "pads": [
                {"index": 10, "x": 100, "y": 0.0, "z": 200, "type": "weapon", "weapon": WEAPON_SHOTGUN},
            ],
        }

        healed, v_meta = verify_and_heal_map(raw_map)
        assert v_meta["passed"] is True
        assert v_meta["invariants_checked"] == [
            "contiguous_pad_indices",
            "y_floor_offset_10",
            "min_spawns_ge_4",
            "room_portal_consistency",
            "editor_mapspec_conformance",
        ]
        # Verify EditorMapSpec compiles without error
        spec = EditorMapSpec.from_json(healed)
        assert spec.name.startswith("raw_map_name")
        assert len(spec.mapdef.pads) >= 4


class TestFastPathDeterministicVerbs:
    """Test suite for expanded fast-path regex/grammar parser (<10ms execution)."""

    def test_move_pad_xyz(self, assistant: GenerativeAssistant):
        """Verify 'move pad <idx> to <x>, <y>, <z>' moves pad and clamps Y >= 10."""
        res = assistant.process_prompt("move pad 0 to 450, 10, -250")
        assert res["ok"] is True
        assert res["action"] == "modify"
        p0 = res["map"]["pads"][0]
        assert p0["x"] == 450.0
        assert p0["y"] == 10.0
        assert p0["z"] == -250.0
        assert res["focus_target"] == [450.0, 10.0, -250.0]
        assert_no_emojis(res["reply"])

    def test_move_pad_xz_auto_y10(self, assistant: GenerativeAssistant):
        """Verify 'move pad <idx> to <x> <z>' automatically sets Y=10."""
        res = assistant.process_prompt("move pad 1 to 300 -150")
        assert res["ok"] is True
        assert res["action"] == "modify"
        p1 = res["map"]["pads"][1]
        assert p1["x"] == 300.0
        assert p1["y"] == 10.0
        assert p1["z"] == -150.0
        assert res["focus_target"] == [300.0, 10.0, -150.0]
        assert_no_emojis(res["reply"])

    def test_shift_pad(self, assistant: GenerativeAssistant):
        """Verify 'shift pad <idx> by <dx>, <dz>' updates coordinates by delta."""
        base_res = assistant.process_prompt("2-room sniper duel")
        orig_p0 = base_res["map"]["pads"][0]
        orig_x, orig_z = orig_p0["x"], orig_p0["z"]

        res = assistant.process_prompt("shift pad 0 by 100, -200", current_map=base_res["map"])
        assert res["ok"] is True
        assert res["action"] == "modify"
        p0 = res["map"]["pads"][0]
        assert p0["x"] == orig_x + 100.0
        assert p0["z"] == orig_z - 200.0
        assert p0["y"] >= 10.0
        assert res["focus_target"] == [p0["x"], p0["y"], p0["z"]]
        assert_no_emojis(res["reply"])

    def test_delete_pad_reindexes_contiguously(self, assistant: GenerativeAssistant):
        """Verify 'delete pad <idx>' removes pad and re-indexes remaining contiguously 0..N-1."""
        base_res = assistant.process_prompt("2-room sniper duel")
        initial_count = len(base_res["map"]["pads"])

        res = assistant.process_prompt("delete pad 1", current_map=base_res["map"])
        assert res["ok"] is True
        assert res["action"] == "modify"
        pads = res["map"]["pads"]
        assert len(pads) == initial_count - 1
        assert [p["index"] for p in pads] == list(range(len(pads)))
        assert_no_emojis(res["reply"])

        # Also test 'remove pad' alias
        res2 = assistant.process_prompt("remove pad 0", current_map=res["map"])
        assert res2["ok"] is True
        pads2 = res2["map"]["pads"]
        assert len(pads2) == len(pads) - 1
        assert [p["index"] for p in pads2] == list(range(len(pads2)))
        assert_no_emojis(res2["reply"])

    def test_change_weapon_and_replace_weapon(self, assistant: GenerativeAssistant):
        """Verify 'change weapon <idx> to <name>' and 'replace weapon <idx> with <name>'."""
        base_res = assistant.process_prompt("2-room sniper duel")

        # Change weapon on pad 4 (originally Sniper Rifle) to shotgun
        res1 = assistant.process_prompt("change weapon 4 to shotgun", current_map=base_res["map"])
        assert res1["ok"] is True
        assert res1["action"] == "modify"
        assert res1["map"]["pads"][4]["weapon"] == WEAPON_SHOTGUN
        assert res1["map"]["pads"][4]["type"] == "weapon"
        assert_no_emojis(res1["reply"])

        # Replace weapon on pad 4 with rocket launcher
        res2 = assistant.process_prompt("replace weapon 4 with rocket launcher", current_map=res1["map"])
        assert res2["ok"] is True
        assert res2["action"] == "modify"
        assert res2["map"]["pads"][4]["weapon"] == WEAPON_ROCKETLAUNCHER
        assert_no_emojis(res2["reply"])

    def test_scale_map(self, assistant: GenerativeAssistant):
        """Verify 'scale map <factor>' scales pad x/z and room bounds while preserving Y=10."""
        base_res = assistant.process_prompt("2-room sniper duel")
        orig_p0 = base_res["map"]["pads"][0]
        orig_r0 = base_res["map"]["rooms"][0]

        res = assistant.process_prompt("scale map 2.0", current_map=base_res["map"])
        assert res["ok"] is True
        assert res["action"] == "modify"
        scaled_p0 = res["map"]["pads"][0]
        scaled_r0 = res["map"]["rooms"][0]

        assert scaled_p0["x"] == orig_p0["x"] * 2.0
        assert scaled_p0["z"] == orig_p0["z"] * 2.0
        assert scaled_p0["y"] >= 10.0
        assert scaled_r0["x0"] == orig_r0["x0"] * 2.0
        assert scaled_r0["x1"] == orig_r0["x1"] * 2.0
        assert_no_emojis(res["reply"])

    def test_set_box_half_and_height(self, assistant: GenerativeAssistant):
        """Verify 'set box half <val>' and 'set height <val>' update arena bounding dimensions."""
        res1 = assistant.process_prompt("set box half 6500")
        assert res1["ok"] is True
        assert res1["map"]["box_half"] == 6500.0
        assert_no_emojis(res1["reply"])

        res2 = assistant.process_prompt("set height 3500", current_map=res1["map"])
        assert res2["ok"] is True
        assert res2["map"]["box_height"] == 3500.0
        assert_no_emojis(res2["reply"])

    def test_clear_weapons(self, assistant: GenerativeAssistant):
        """Verify 'clear weapons' removes all weapon pads while preserving map validity."""
        base_res = assistant.process_prompt("2-room sniper duel")
        assert any(p.get("type") == "weapon" for p in base_res["map"]["pads"])

        res = assistant.process_prompt("clear weapons", current_map=base_res["map"])
        assert res["ok"] is True
        assert res["action"] == "modify"
        assert not any(p.get("type") == "weapon" for p in res["map"]["pads"])
        # Minimum spawns preserved
        assert sum(1 for p in res["map"]["pads"] if p.get("type") == "spawn") >= 4
        assert [p["index"] for p in res["map"]["pads"]] == list(range(len(res["map"]["pads"])))
        assert_no_emojis(res["reply"])

    def test_clear_spawns_maintains_4_spawns(self, assistant: GenerativeAssistant):
        """Verify 'clear spawns' clears spawns and self-healing ladder promotes/synthesizes min 4 spawns."""
        base_res = assistant.process_prompt("2-room sniper duel")
        res = assistant.process_prompt("clear spawns", current_map=base_res["map"])
        assert res["ok"] is True
        assert res["action"] == "modify"
        # Invariant ensures >= 4 spawns
        spawns = [p for p in res["map"]["pads"] if p.get("type") == "spawn"]
        assert len(spawns) >= 4
        assert [p["index"] for p in res["map"]["pads"]] == list(range(len(res["map"]["pads"])))
        assert_no_emojis(res["reply"])

    def test_viewport_camera_commands(self, assistant: GenerativeAssistant):
        """Verify all viewport camera commands return appropriate action and camera dict."""
        base_res = assistant.process_prompt("2-room sniper duel")
        current_map = base_res["map"]

        # focus on spawn
        res_spawn = assistant.process_prompt("focus on spawn", current_map=current_map)
        assert res_spawn["ok"] is True
        assert res_spawn["action"] == "viewport"
        assert res_spawn["camera"]["mode"] == "focus"
        assert res_spawn["focus_target"] == [-2200.0, 10.0, -600.0]
        assert_no_emojis(res_spawn["reply"])

        # focus on pad 4
        res_pad = assistant.process_prompt("focus on pad 4", current_map=current_map)
        assert res_pad["ok"] is True
        assert res_pad["action"] == "viewport"
        assert res_pad["camera"]["mode"] == "focus"
        assert res_pad["focus_target"] == [-1200.0, 10.0, 0.0]
        assert_no_emojis(res_pad["reply"])

        # focus on room 1
        res_room = assistant.process_prompt("focus on room 1", current_map=current_map)
        assert res_room["ok"] is True
        assert res_room["action"] == "viewport"
        assert res_room["camera"]["mode"] == "focus"
        assert res_room["focus_target"] == [-1500.0, 10.0, 0.0]
        assert_no_emojis(res_room["reply"])

        # top-down view
        res_td = assistant.process_prompt("top-down view", current_map=current_map)
        assert res_td["ok"] is True
        assert res_td["action"] == "viewport"
        assert res_td["camera"]["mode"] == "top_down"
        assert_no_emojis(res_td["reply"])

        # reset view
        res_rst = assistant.process_prompt("reset view", current_map=current_map)
        assert res_rst["ok"] is True
        assert res_rst["action"] == "viewport"
        assert res_rst["camera"]["mode"] == "default"
        assert_no_emojis(res_rst["reply"])

    def test_fast_path_latency_sub_10ms(self, assistant: GenerativeAssistant):
        """Ensure all fast-path commands execute deterministically in under 10ms with zero network overhead."""
        base_res = assistant.process_prompt("2-room sniper duel")
        current_map = base_res["map"]

        commands = [
            "move pad 0 to 100, 200",
            "shift pad 1 by 50, -50",
            "change weapon 2 to shotgun",
            "scale map 1.1",
            "set box half 5500",
            "set height 3100",
            "focus on spawn",
            "focus on pad 3",
            "focus on room 2",
            "top-down view",
            "reset view",
            "delete pad 4",
        ]

        for cmd in commands:
            t0 = time.perf_counter()
            res = assistant.process_prompt(cmd, current_map=current_map)
            elapsed = time.perf_counter() - t0
            assert res["ok"] is True
            assert elapsed < 0.010, f"Command '{cmd}' took {elapsed*1000:.2f}ms (must be < 10ms)"


class TestViewportGroundingAndFocusTarget:
    """Test suite for Viewport Grounding & Focus Target Generator."""

    def test_add_shotgun_here_with_viewport(self, assistant: GenerativeAssistant):
        """Verify 'add shotgun here' uses camera_target and active_room from viewport."""
        base_res = assistant.process_prompt("2-room sniper duel")
        current_map = base_res["map"]
        initial_pad_count = len(current_map["pads"])

        viewport = {
            "camera_pos": [1500.0, 1000.0, 1000.0],
            "camera_target": [1200.0, 10.0, 450.0],
            "active_room": 2,
            "selected_pad": 2,
        }

        res = assistant.process_prompt(
            "add shotgun here",
            current_map=current_map,
            viewport=viewport,
        )
        assert res["ok"] is True
        assert res["action"] == "modify"
        pads = res["map"]["pads"]
        assert len(pads) == initial_pad_count + 1

        new_pad = pads[-1]
        assert new_pad["weapon"] == WEAPON_SHOTGUN
        assert new_pad["x"] == 1200.0
        assert new_pad["y"] == 10.0
        assert new_pad["z"] == 450.0
        assert new_pad["room"] == 2
        assert res["focus_target"] == [1200.0, 10.0, 450.0]
        assert_no_emojis(res["reply"])

    def test_add_spawn_in_this_room_with_viewport(self, assistant: GenerativeAssistant):
        """Verify 'add spawn in this room' uses active_room from viewport."""
        base_res = assistant.process_prompt("2-room sniper duel")
        current_map = base_res["map"]

        viewport = {
            "active_room": 2,
        }

        res = assistant.process_prompt(
            "add spawn in this room",
            current_map=current_map,
            viewport=viewport,
        )
        assert res["ok"] is True
        assert res["action"] == "modify"
        new_pad = res["map"]["pads"][-1]
        assert new_pad["type"] == "spawn"
        assert new_pad["room"] == 2
        assert new_pad["y"] == 10.0
        assert res["focus_target"] is not None
        assert len(res["focus_target"]) == 3
        assert_no_emojis(res["reply"])

    def test_focus_target_geometric_center(self, assistant: GenerativeAssistant):
        """Verify focus_target returns 3-coordinate geometric center [x, y, z] of generated and modified entities."""
        gen_res = assistant.process_prompt("2-room sniper duel")
        ft = gen_res["focus_target"]
        assert isinstance(ft, list)
        assert len(ft) == 3
        assert all(isinstance(c, float) for c in ft)
        assert ft[1] == 10.0  # Y floor offset


class TestAntiSlopActionChips:
    """Test suite for Anti-Slop Action Chips Generator."""

    def test_generation_action_chips(self, assistant: GenerativeAssistant):
        """Verify action_chips for generated maps follow standard 4-chip schema."""
        res = assistant.process_prompt("2-room sniper duel")
        chips = res["action_chips"]
        assert len(chips) == 4

        actions = [c["action"] for c in chips]
        assert actions == ["playtest", "focus", "save", "undo"]

        labels = [c["label"] for c in chips]
        assert labels == ["Playtest (T)", "Focus 3D View", "Save Map", "Undo"]

        # Focus chip has valid coords matching focus_target
        focus_chip = next(c for c in chips if c["action"] == "focus")
        assert focus_chip["coords"] == res["focus_target"]

        for c in chips:
            assert_no_emojis(c["label"])

    def test_modification_action_chips(self, assistant: GenerativeAssistant):
        """Verify action_chips for pad modifications follow 3-chip inspection schema."""
        res = assistant.process_prompt("move pad 2 to 500, 200")
        chips = res["action_chips"]
        assert len(chips) == 3

        actions = [c["action"] for c in chips]
        assert actions == ["select_pad", "playtest", "undo"]

        inspect_chip = next(c for c in chips if c["action"] == "select_pad")
        assert inspect_chip["label"] == "Inspect Pad 2"
        assert inspect_chip["target"] == 2

        for c in chips:
            assert_no_emojis(c["label"])

    def test_explanation_action_chips(self, assistant: GenerativeAssistant):
        """Verify action_chips for explanations provide 1-click starter prompts."""
        res = assistant.process_prompt("explain how this works")
        chips = res["action_chips"]
        assert len(chips) == 2

        prompts = [c["prompt"] for c in chips]
        assert "Symmetrical 2-room sniper duel" in prompts
        assert "King of the hill arena" in prompts

        for c in chips:
            assert_no_emojis(c["label"])

    def test_viewport_action_chips(self, assistant: GenerativeAssistant):
        """Verify action_chips for viewport commands include Playtest, Focus, and Undo."""
        res = assistant.process_prompt("top-down view")
        chips = res["action_chips"]
        assert len(chips) == 3
        actions = [c["action"] for c in chips]
        assert "playtest" in actions
        assert "focus" in actions
        assert "undo" in actions

        for c in chips:
            assert_no_emojis(c["label"])

    def test_universal_zero_emoji_guarantee(self, assistant: GenerativeAssistant):
        """Assert complete absence of Unicode emojis across all prompts, replies, and metadata."""
        test_prompts = [
            "explain to a regular person",
            "2-room sniper duel",
            "king of the hill arena",
            "4-room facility with shotgun & rocket",
            "warehouse bunker",
            "move pad 0 to 100, 200",
            "shift pad 1 by 50, -50",
            "change weapon 0 to shotgun",
            "scale map 1.5",
            "set box half 6000",
            "set height 2500",
            "clear weapons",
            "focus on spawn",
            "top-down view",
            "reset view",
        ]

        for p in test_prompts:
            res = assistant.process_prompt(p)
            assert_no_emojis(res["reply"])
            for chip in res.get("action_chips", []):
                assert_no_emojis(chip.get("label", ""))
                assert_no_emojis(chip.get("prompt", ""))
            v_meta = res.get("verification", {})
            for h in v_meta.get("self_healing_applied", []):
                assert_no_emojis(h)

