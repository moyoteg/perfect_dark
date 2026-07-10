"""Stage registration planner — deterministic codegen for four C wiring points."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .core import ROOT, ROMID
from .from_json import validate_level_name

FILES_H = os.path.join(ROOT, "src", "include", "files.h")
CONSTANTS_H = os.path.join(ROOT, "src", "include", "constants.h")
STAGETABLE = os.path.join(ROOT, "src", "game", "stagetable.c")
SETUP_C = os.path.join(ROOT, "src", "game", "mplayer", "setup.c")
LIST_C = os.path.join(ROOT, "src", "assets", ROMID, "files", "list.c")
ENV_C = os.path.join(ROOT, "src", "game", "env.c")
LANG_C = os.path.join(ROOT, "src", "game", "lang.c")


@dataclass
class RegistrationPlan:
    name: str
    upper: str
    stage_const: str
    file_ids: dict[str, int]
    already_registered: bool
    snippets: dict[str, str]
    textid: int
    label: str

    def render_markdown(self) -> str:
        lines = [
            f"# Stage registration plan: {self.name}",
            "",
            f"Already registered: **{self.already_registered}**",
            "",
            "## 1. `src/include/files.h`",
            "",
            "```c",
            self.snippets["files_h"],
            "```",
            "",
            "## 2. `src/assets/ntsc-final/files/list.c`",
            "",
            "```c",
            self.snippets["list_c"],
            "```",
            "",
            "## 3. `src/game/stagetable.c`",
            "",
            "```c",
            self.snippets["stagetable"],
            "```",
            "",
            "## 4. `src/game/mplayer/setup.c` (`g_MpArenas[]`)",
            "",
            "```c",
            self.snippets["setup_c"],
            "```",
            "",
            "## 5. `src/game/env.c` (`g_StagesEnv[]`)",
            "",
            "```c",
            self.snippets["env_c"],
            "```",
            "",
            "## 6. `src/game/lang.c` (`langGet` & `langGetBank`)",
            "",
            "```c",
            self.snippets["lang_c_get"],
            self.snippets["lang_c_bank"],
            "```",
            "",
            "> After editing, run `make -j8` and `pdmap build {name} --deploy`.",
            "> For quick test without menu registration, use `--deploy-as uff` instead.",
            "",
        ]
        return "\n".join(lines)


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fp:
        return fp.read()


def _next_file_id() -> int:
    """Next unused FILE_* hex id (PC port block before NUM_FILES)."""
    text = _read(FILES_H)
    ids = [int(m.group(1), 16) for m in re.finditer(r"#define\s+FILE_\w+\s+(0x[0-9A-Fa-f]+)", text)]
    # Stay below PD Plus mod extension block; use high unused slot near custom maps.
    base = max(ids) + 1 if ids else 0x07E4
    return base


def _resolve_textid(name: str) -> tuple[int, str]:
    """Find textid for a stage name. Returns (textid, label)."""
    text = _read(LANG_C)
    label = " ".join(word.capitalize() for word in name.split("_"))

    # Check if stage name already exists in lang.c
    m = re.search(r'if\s*\(textid\s*==\s*(0x7[0-9A-Fa-f]{3})\)\s*return\s*"' + re.escape(label) + r'";', text)
    if m:
        return int(m.group(1), 16), label

    ids = [int(match.group(0), 16) for match in re.finditer(r"0x7[0-9A-Fa-f]{3}", text)]
    ids = [x for x in ids if x != 0x7FFE]
    val = min(ids) - 1 if ids else 0x7FFF
    return val, label


def _resolve_stage_const(name: str) -> tuple[str, int]:
    """Return (STAGE_FOO symbol, hex value) for constants.h / stagetable."""
    text = _read(CONSTANTS_H)
    existing = re.findall(r"#define\s+(STAGE_\w+)\s+(0x[0-9A-Fa-f]+)", text)
    target = f"STAGE_{name.upper()}"
    for const, val in existing:
        if const == target:
            return const, int(val, 16)
    ids = [int(val, 16) for _, val in existing]
    # Custom pdmap arenas: ids may exceed STAGE_TITLE (0x5c) — engine uses
    # STAGE_IS_MENU(), not a numeric cutoff, for title/boot/credits only.
    stage_val = max(0x80, max(ids) + 1 if ids else 0x80)
    return target, stage_val


def _next_stage_id(name: str) -> str:
    sym, val = _resolve_stage_const(name)
    if f"#define {sym}" in _read(CONSTANTS_H):
        return sym
    return f"{sym}  /* assign {val:#x} in constants.h */"


def _is_registered(name: str) -> bool:
    upper = name.upper()
    text = _read(FILES_H)
    return f"FILE_BG_{upper}_SEG" in text or f"FILE_BG_{upper}_TILES" in text


def plan_registration(name: str) -> RegistrationPlan:
    name = validate_level_name(name)
    upper = name.upper()
    already = _is_registered(name)

    seg_id = _next_file_id()
    tiles_id = seg_id + 1
    pads_id = seg_id + 2
    usetup_id = seg_id + 3
    ump_id = seg_id + 4

    stage_const = _next_stage_id(name)
    stage_sym = stage_const.split()[0]
    textid, label = _resolve_textid(name)

    files_h = (
        f"#define FILE_BG_{upper}_SEG       {seg_id:#06x}\n"
        f"#define FILE_BG_{upper}_TILES     {tiles_id:#06x}\n"
        f"#define FILE_BG_{upper}_PADS      {pads_id:#06x}\n"
        f"#define FILE_USETUP{upper}         {usetup_id:#06x}\n"
        f"#define FILE_UMP_SETUP{upper}      {ump_id:#06x}"
    )

    list_c = (
        f"/*{seg_id:#06x}*/ \"bgdata/bg_{name}.seg\",\n"
        f"/*{tiles_id:#06x}*/ \"bgdata/bg_{name}_tilesZ\",\n"
        f"/*{pads_id:#06x}*/ \"bgdata/bg_{name}_padsZ\",\n"
        f"/*{usetup_id:#06x}*/ \"Usetup{name}Z\",\n"
        f"/*{ump_id:#06x}*/ \"Ump_setup{name}Z\","
    )

    stagetable = (
        f"/*{seg_id:#06x}*/ {stage_sym}, 2, 255, 100, 100, 0, "
        f"FILE_BG_{upper}_SEG, FILE_BG_{upper}_TILES, FILE_BG_{upper}_PADS, "
        f"FILE_USETUP{upper}, FILE_UMP_SETUP{upper}, "
        f"1, 1, 100, 0, 0, -1, 255, 0x3e19999a, -1, 400, 0, 1, SFX_ALARM_DEFAULT, 0,"
    )

    setup_c = f"{{ {stage_sym}, 0, {textid:#06x} }}, // {label}"
    env_c = f"\t{{ {stage_sym},      10, 10000,   0,  0,  0, RGB(0x000000), NO_SUNS,            0, RGB(0xcccccc),  5000,   0, 0, RGB(0x000000),  -5000,    0, 0, 0 }},"
    lang_c_get = f"\tif (textid == {textid:#06x}) return \"{label}\";"
    lang_c_bank = f"\tcase {stage_sym}:      bank = LANGBANK_UFF; break;"

    return RegistrationPlan(
        name=name,
        upper=upper,
        stage_const=stage_const,
        file_ids={
            "seg": seg_id,
            "tiles": tiles_id,
            "pads": pads_id,
            "usetup": usetup_id,
            "ump_setup": ump_id,
        },
        already_registered=already,
        snippets={
            "files_h": files_h,
            "list_c": list_c,
            "stagetable": stagetable,
            "setup_c": setup_c,
            "env_c": env_c,
            "lang_c_get": lang_c_get,
            "lang_c_bank": lang_c_bank,
        },
        textid=textid,
        label=label,
    )


def write_plan(name: str, *, out_dir: str | None = None) -> str:
    plan = plan_registration(name)
    out_dir = out_dir or os.path.join(ROOT, "journal", "map_learn")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"register_{name}.md")
    with open(path, "w", encoding="utf-8") as fp:
        fp.write(plan.render_markdown())
    return path


def _patch_insert_before(text: str, anchor: str, insertion: str, *, marker: str) -> str:
    """Insert block before anchor; no-op when marker already present (idempotent)."""
    if marker in text:
        return text
    pos = text.find(anchor)
    if pos < 0:
        raise ValueError(f"Registration patch anchor not found: {anchor!r}")
    block = insertion if insertion.endswith("\n") else insertion + "\n"
    result = text[:pos] + block + text[pos:]
    # Guard against glued `#endif` + `#define` when anchors abut preprocessor lines.
    return re.sub(r"#endif(#define)", r"#endif\n\1", result)


def _patch_insert_after(text: str, anchor: str, insertion: str, *, marker: str) -> str:
    """Insert block immediately after anchor (idempotent)."""
    if marker in text:
        return text
    pos = text.find(anchor)
    if pos < 0:
        raise ValueError(f"Registration patch anchor not found: {anchor!r}")
    insert_at = pos + len(anchor)
    block = insertion if insertion.startswith("\n") else "\n" + insertion
    if not block.endswith("\n"):
        block += "\n"
    result = text[:insert_at] + block + text[insert_at:]
    return re.sub(r"#endif(#define)", r"#endif\n\1", result)


def _files_h_anchor(text: str) -> tuple[str, bool]:
    """Return (anchor, insert_after) for the next FILE_* block in files.h."""
    ump = list(re.finditer(r"^#define FILE_UMP_SETUP\w+\s+0x[0-9A-Fa-f]+", text, re.M))
    if ump:
        line = ump[-1].group(0)
        return line + "\n", True
    if "\n\n// PD Plus Mod" in text:
        return "\n\n// PD Plus Mod", False
    if "// Custom pdmap arenas" in text:
        return "// Custom pdmap arenas", False
    raise ValueError("files.h: no anchor for FILE_* insertion")


def _bump_num_files(text: str, *, delta: int = 5) -> str:
    """Increment NUM_FILES PC-port counts when adding a five-file stage."""

    def _repl(match: re.Match[str]) -> str:
        old = int(match.group(2))
        suffix = match.group(3) or ""
        return f"{match.group(1)}{old + delta}{suffix}"

    return re.sub(
        r"(#define\s+NUM_FILES\s+)(\d+)(\s+//[^\n]*)?",
        _repl,
        text,
    )


def apply_registration(name: str) -> list[str]:
    """Patch C sources for stage registration (idempotent). Returns changed file paths."""
    plan = plan_registration(name)
    if plan.already_registered:
        raise ValueError(f"{name}: already registered in files.h")

    stage_sym, stage_val = _resolve_stage_const(name)
    changed: list[str] = []

    const_line = f"#define {stage_sym:<20} {stage_val:#x}"
    const_text = _read(CONSTANTS_H)
    new_const = _patch_insert_before(
        const_text, "#define STAGE_TITLE", const_line + "\n", marker=const_line,
    )
    if new_const != const_text:
        with open(CONSTANTS_H, "w", encoding="utf-8") as fp:
            fp.write(new_const)
        changed.append(CONSTANTS_H)

    files_block = plan.snippets["files_h"] + "\n"
    files_text = _read(FILES_H)
    anchor, after = _files_h_anchor(files_text)
    marker = f"FILE_BG_{plan.upper}_SEG"
    if after:
        new_files = _patch_insert_after(files_text, anchor, files_block, marker=marker)
    else:
        new_files = _patch_insert_before(files_text, anchor, files_block + "\n", marker=marker)
    new_files = _bump_num_files(new_files)
    if new_files != files_text:
        with open(FILES_H, "w", encoding="utf-8") as fp:
            fp.write(new_files)
        changed.append(FILES_H)

    list_lines = plan.snippets["list_c"].replace(",\n", ",\n\t").split("\n")
    list_block = "\n\t".join(list_lines) + "\n"
    list_text = _read(LIST_C)
    array_close = list_text.rfind("\n};")
    endif_pos = list_text.rfind("#endif", 0, array_close) if array_close >= 0 else -1
    if endif_pos >= 0 and "#ifndef PLATFORM_N64" in list_text:
        new_list = _patch_insert_before(
            list_text, "#endif", list_block, marker=f"bg_{name}.seg",
        )
    else:
        new_list = _patch_insert_before(list_text, "\n};", list_block, marker=f"bg_{name}.seg")
    if new_list != list_text:
        with open(LIST_C, "w", encoding="utf-8") as fp:
            fp.write(new_list)
        changed.append(LIST_C)

    stage_row = "\t" + plan.snippets["stagetable"].rstrip().rstrip(",") + ",\n"
    stage_text = _read(STAGETABLE)
    new_stage = _patch_insert_before(
        stage_text, "#endif\n};", stage_row, marker=f"FILE_BG_{plan.upper}_SEG",
    )
    if new_stage != stage_text:
        with open(STAGETABLE, "w", encoding="utf-8") as fp:
            fp.write(new_stage)
        changed.append(STAGETABLE)

    setup_row = "\t" + plan.snippets["setup_c"] + "\n"
    setup_text = _read(SETUP_C)
    new_setup = _patch_insert_before(
        setup_text, "\t// Random", setup_row, marker=stage_sym,
    )
    if new_setup != setup_text:
        with open(SETUP_C, "w", encoding="utf-8") as fp:
            fp.write(new_setup)
        changed.append(SETUP_C)

    # 5. Patch env.c
    env_row = plan.snippets["env_c"] + "\n"
    env_text = _read(ENV_C)
    env_anchor = "\t{ STAGE_MY_ARENA,      10, 10000,   0,  0,  0, RGB(0x000000), NO_SUNS,            0, RGB(0xcccccc),  5000,   0, 0, RGB(0x000000),  -5000,    0, 0, 0 },"
    new_env = _patch_insert_after(
        env_text, env_anchor, env_row, marker=stage_sym
    )
    if new_env != env_text:
        with open(ENV_C, "w", encoding="utf-8") as fp:
            fp.write(new_env)
        changed.append(ENV_C)

    # 6. Patch lang.c
    lang_text = _read(LANG_C)
    lang_get_row = plan.snippets["lang_c_get"] + "\n"
    lang_get_anchor = "\tif (textid == 0x7FFC) return \"Test Arena\";"
    new_lang = _patch_insert_after(
        lang_text, lang_get_anchor, lang_get_row, marker=f"== {plan.textid:#06x}"
    )

    lang_bank_row = plan.snippets["lang_c_bank"] + "\n"
    lang_bank_anchor = "\tcase STAGE_TESTARENA:     bank = LANGBANK_UFF; break;"
    new_lang = _patch_insert_after(
        new_lang, lang_bank_anchor, lang_bank_row, marker=stage_sym
    )
    if new_lang != lang_text:
        with open(LANG_C, "w", encoding="utf-8") as fp:
            fp.write(new_lang)
        changed.append(LANG_C)

    return changed
