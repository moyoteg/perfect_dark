"""Regression tests for the Virtual Agent Office proximity-greeting layer.

Guarantees the opt-in `greet_text` addition did NOT change the bytecode of the
existing examine-only agents, and that the greeting branch is well-formed for
opted-in agents (dataDyne G5 Security, Carrington Security).

Runnable two ways (no pytest required):
    python3 tests/test_agent_office_ailist.py
    python3 -m pytest tests/test_agent_office_ailist.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools.pdmap import agent_office as G5  # noqa: E402
from tools.pdmap import agent_office_ci as CI  # noqa: E402


def _examine_only(mod, spec):
    return mod._build_agent_briefing_ailist(spec.anim_index, spec.status_text, None)


def _actual(mod, spec):
    return mod._build_agent_briefing_ailist(spec.anim_index, spec.status_text, spec.greet_text)


def test_examine_only_agents_unchanged():
    """Agents without a greeting emit byte-identical bytecode to before."""
    for mod in (G5, CI):
        for spec in mod.VIRTUAL_AGENTS:
            if spec.greet_text is None:
                assert _actual(mod, spec) == _examine_only(mod, spec), (
                    f"{mod.__name__}:{spec.role} bytecode changed unexpectedly"
                )


def test_greeter_agents_extend_examine_build():
    """Opted-in greeters strictly extend (never shrink) the examine-only build."""
    greeters = 0
    for mod in (G5, CI):
        for spec in mod.VIRTUAL_AGENTS:
            if spec.greet_text is not None:
                greeters += 1
                a = _actual(mod, spec)
                base = _examine_only(mod, spec)
                assert a != base and len(a) > len(base), (
                    f"{mod.__name__}:{spec.role} greeting not applied"
                )
                assert a.endswith(struct.pack(">H", 0x0004)), "ailist must end with endlist"
    assert greeters >= 2, "expected at least the two Security greeters (G5 + CI)"


def test_distance_opcode_encoding():
    """if_distance_to_target_{lt,gt} encode as commands.h specifies (distance/10)."""
    for mod in (G5, CI):
        assert mod._cmd_if_distance_to_target_lt(400, 0x30) == struct.pack(">HHB", 0x0052, 40, 0x30)
        assert mod._cmd_if_distance_to_target_gt(400, 0x11) == struct.pack(">HHB", 0x0053, 40, 0x11)


def test_setup_binaries_still_pack():
    """Full MP setup packs without error for both variants."""
    assert len(G5.agent_ailist_chunks()) == len(G5.VIRTUAL_AGENTS) + 1
    assert len(CI.agent_ci_ailist_chunks()) == len(CI.VIRTUAL_AGENTS) + 1


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{'OK' if not failures else str(failures) + ' FAILED'}")
    sys.exit(1 if failures else 0)
