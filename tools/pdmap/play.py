"""Launch the PC port with a built mod map."""

from __future__ import annotations

import os
import platform
import sys

from .core import ROOT

TEST_MAP_SLOT = "uff"
STAGE_TEST_UFF = 0x4D
STAGE_ANIMLAB = 0x82

MOD_CHOICES: dict[str, str] = {
    "mod_allinone": "mods/mod_allinone",
    "mod_dark_noon": "mods/mod_dark_noon",
    "mod_gex": "mods/mod_gex",
    "mod_kakariko": "mods/mod_kakariko",
    "mod_goldfinger_64": "mods/mod_goldfinger_64",
}

SCENARIO_CHOICES = {
    0: "Combat",
    1: "Hold the Briefcase",
    2: "Hacker Central",
    3: "Pop a Cap",
    4: "King of the Hill",
    5: "Capture the Case",
}


def detect_pd_binary() -> str:
    """Return the repo-built pd binary (always prefer native arm64 on macOS)."""
    arm64 = os.path.join(ROOT, "build", "pd.arm64")
    if sys.platform == "darwin" and os.path.isfile(arm64):
        return arm64
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        name = "pd.arm64"
    elif sys.platform == "darwin":
        name = "pd.arm64"
    else:
        name = "pd.x86_64"
    path = os.path.join(ROOT, "build", name)
    if os.path.isfile(path):
        return path
    alt = os.path.join(ROOT, "build", "pd.x86_64")
    if os.path.isfile(alt):
        return alt
    return path


def play_command(
    *,
    mod_key: str = "mod_allinone",
    scenario: int = 0,
    pd_binary: str | None = None,
    deploy_name: str | None = None,
    level: str | None = None,
    use_test_map: bool | None = None,
    play: bool = True,
    **_ignored,
) -> list[str]:
    """Build argv to launch pd.

    Pass ``level='animlab'`` for ``--test-animlab`` (STAGE_ANIMLAB).
    Pass ``level='uff'`` or ``use_test_map=True`` for ``--test-map`` (STAGE_TEST_UFF).
    """
    if mod_key not in MOD_CHOICES:
        raise ValueError(f"Unknown mod {mod_key!r}; choose from {', '.join(MOD_CHOICES)}")
    mod_path = os.path.join(ROOT, MOD_CHOICES[mod_key])
    binary = pd_binary or detect_pd_binary()
    map_level = (level or deploy_name or TEST_MAP_SLOT).strip().lower()
    if use_test_map is None:
        use_test_map = map_level in (TEST_MAP_SLOT, "uff")
    cmd = [binary]
    if play:
        if map_level == "animlab":
            cmd.append("--test-animlab")
            cmd.append(f"--scenario-{scenario}")
        elif use_test_map:
            cmd.append("--test-map")
            cmd.append(f"--scenario-{scenario}")
        else:
            stage = STAGE_ANIMLAB if map_level == "animlab" else STAGE_TEST_UFF
            cmd.extend(["--boot-stage", str(stage)])
            cmd.append("--skip-intro")
    cmd.extend(["--moddir", mod_path])
    return cmd
