"""Tests for walk-up DM thread persistence (Phase 3 / Pass 6)."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "agent_office_llm"))

from service.dm_threads import (  # noqa: E402
    DM_MESSAGE_CAP,
    DmThreadAppendStatus,
    DmThreadReadStatus,
    DmThreadsLoadStatus,
    dm_thread_append_outcome,
    dm_thread_id,
    dm_thread_mark_read_outcome,
    dm_thread_read_outcome,
    load_dm_threads_outcome,
    parse_dm_thread,
    parse_dm_threads_document,
    resolve_dm_threads_path,
)
from service.workspace_config import merge_workspace_config  # noqa: E402


def _setup_member(tmp: str) -> str:
    cfg = merge_workspace_config(
        {"location_key": "g5", "member": {"display_name": "Joanna Dark", "codename": "Falcon"}},
        repo_root=tmp,
    )
    return cfg["member"]["user_id"]


def test_dm_thread_append_and_read_three_message_continuity():
    """Scenario 3: repeated walk-up appends accumulate in one thread."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AGENT_OFFICE_WORKSPACE_CONFIG"] = str(Path(tmp) / "workspace_config.json")
        os.environ["AGENT_OFFICE_DM_THREADS"] = str(Path(tmp) / "dm_threads.json")
        try:
            member_id = _setup_member(tmp)

            first = dm_thread_append_outcome(
                "research",
                from_role="human",
                text="status on vault log?",
                repo_root=tmp,
            )
            assert first.status == DmThreadAppendStatus.APPENDED
            assert first.stub_reply is True
            assert first.message_count == 2  # human + stub agent reply

            second = dm_thread_append_outcome(
                "research",
                from_role="human",
                text="any update?",
                repo_root=tmp,
                stub_reply=False,
            )
            assert second.status == DmThreadAppendStatus.APPENDED
            assert second.message_count == 3

            read = dm_thread_read_outcome("research", repo_root=tmp)
            assert read.status == DmThreadReadStatus.FOUND
            assert read.message_count == 3
            assert read.thread is not None
            assert read.thread["member_user_id"] == member_id
            assert read.thread["id"] == dm_thread_id("research")
            assert read.thread["messages"][0]["from"] == "human"
            assert read.thread["messages"][0]["text"] == "status on vault log?"
        finally:
            os.environ.pop("AGENT_OFFICE_WORKSPACE_CONFIG", None)
            os.environ.pop("AGENT_OFFICE_DM_THREADS", None)


def test_dm_thread_scoped_by_member():
    """Security and Research never share a thread — keyed by member_user_id."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AGENT_OFFICE_WORKSPACE_CONFIG"] = str(Path(tmp) / "workspace_config.json")
        os.environ["AGENT_OFFICE_DM_THREADS"] = str(Path(tmp) / "dm_threads.json")
        try:
            _setup_member(tmp)
            dm_thread_append_outcome("research", from_role="human", text="research only", repo_root=tmp, stub_reply=False)
            dm_thread_append_outcome("security", from_role="human", text="security only", repo_root=tmp, stub_reply=False)

            research = dm_thread_read_outcome("research", repo_root=tmp)
            security = dm_thread_read_outcome("security", repo_root=tmp)
            assert research.thread is not None
            assert security.thread is not None
            assert research.thread["id"] != security.thread["id"]
            assert len(research.thread["messages"]) == 1
            assert len(security.thread["messages"]) == 1
        finally:
            os.environ.pop("AGENT_OFFICE_WORKSPACE_CONFIG", None)
            os.environ.pop("AGENT_OFFICE_DM_THREADS", None)


def test_dm_thread_persists_across_workspace_location_change():
    """Merge workspace location does not clear DM threads."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AGENT_OFFICE_WORKSPACE_CONFIG"] = str(Path(tmp) / "workspace_config.json")
        os.environ["AGENT_OFFICE_DM_THREADS"] = str(Path(tmp) / "dm_threads.json")
        try:
            _setup_member(tmp)
            dm_thread_append_outcome("research", from_role="human", text="before switch", repo_root=tmp, stub_reply=False)

            merge_workspace_config(
                {"location_key": "lab", "member": {"display_name": "Joanna Dark", "codename": "Falcon"}},
                repo_root=tmp,
            )

            read = dm_thread_read_outcome("research", repo_root=tmp)
            assert read.status == DmThreadReadStatus.FOUND
            assert read.message_count == 1
            assert read.thread["messages"][0]["text"] == "before switch"
        finally:
            os.environ.pop("AGENT_OFFICE_WORKSPACE_CONFIG", None)
            os.environ.pop("AGENT_OFFICE_DM_THREADS", None)


def test_dm_thread_lifecycle_logs_never_include_message_body():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AGENT_OFFICE_WORKSPACE_CONFIG"] = str(Path(tmp) / "workspace_config.json")
        os.environ["AGENT_OFFICE_DM_THREADS"] = str(Path(tmp) / "dm_threads.json")
        try:
            _setup_member(tmp)
            buf = io.StringIO()
            with redirect_stdout(buf):
                dm_thread_append_outcome(
                    "research",
                    from_role="human",
                    text="secret vault password",
                    repo_root=tmp,
                    stub_reply=False,
                )
            log_text = buf.getvalue()
            assert "secret vault password" not in log_text
            record = json.loads(log_text.strip().splitlines()[-1])
            assert record["operation"] == "dm_thread_append"
            assert record["outcome"] == "ok"
            assert record["agent_id"] == "research"
            assert "text" not in record
        finally:
            os.environ.pop("AGENT_OFFICE_WORKSPACE_CONFIG", None)
            os.environ.pop("AGENT_OFFICE_DM_THREADS", None)


def test_dm_thread_trim_at_cap():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AGENT_OFFICE_WORKSPACE_CONFIG"] = str(Path(tmp) / "workspace_config.json")
        os.environ["AGENT_OFFICE_DM_THREADS"] = str(Path(tmp) / "dm_threads.json")
        try:
            _setup_member(tmp)
            for i in range(DM_MESSAGE_CAP + 5):
                dm_thread_append_outcome(
                    "comms",
                    from_role="human",
                    text=f"line {i}",
                    repo_root=tmp,
                    stub_reply=False,
                )
            read = dm_thread_read_outcome("comms", repo_root=tmp)
            assert read.message_count == DM_MESSAGE_CAP
            assert read.thread["messages"][0]["text"] == f"line {5}"
        finally:
            os.environ.pop("AGENT_OFFICE_WORKSPACE_CONFIG", None)
            os.environ.pop("AGENT_OFFICE_DM_THREADS", None)


def test_dm_thread_unknown_agent_and_validation():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AGENT_OFFICE_WORKSPACE_CONFIG"] = str(Path(tmp) / "workspace_config.json")
        os.environ["AGENT_OFFICE_DM_THREADS"] = str(Path(tmp) / "dm_threads.json")
        try:
            _setup_member(tmp)
            unknown = dm_thread_read_outcome("not-an-agent", repo_root=tmp)
            assert unknown.status == DmThreadReadStatus.UNKNOWN_AGENT

            bad = dm_thread_append_outcome("research", from_role="human", text="   ", repo_root=tmp)
            assert bad.status == DmThreadAppendStatus.VALIDATION_ERROR
        finally:
            os.environ.pop("AGENT_OFFICE_WORKSPACE_CONFIG", None)
            os.environ.pop("AGENT_OFFICE_DM_THREADS", None)


def test_dm_threads_sidecar_load_missing():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AGENT_OFFICE_DM_THREADS"] = str(Path(tmp) / "dm_threads.json")
        try:
            status, doc, path, run_id = load_dm_threads_outcome(repo_root=tmp)
            assert status.value == "missing"
            assert doc is None
            assert resolve_dm_threads_path(tmp) == Path(path)
            assert run_id.startswith("dm_")
        finally:
            os.environ.pop("AGENT_OFFICE_DM_THREADS", None)


def test_parse_dm_thread_roundtrip():
    raw = {
        "id": "dm-research",
        "agent_id": "research",
        "member_user_id": "member_a1b2c3d4",
        "opened_at": 1710000000.0,
        "updated_at": 1710000123.0,
        "messages": [
            {"from": "human", "text": "hello", "ts": 1710000100.0},
            {"from": "agent", "text": "hi", "ts": 1710000123.0},
        ],
    }
    thread = parse_dm_thread(raw)
    assert thread is not None
    assert thread.to_dict()["messages"][1]["from"] == "agent"


def test_format_dm_thread_tail_for_hud_prefers_agent():
    from service.dm_threads import format_dm_thread_tail_for_hud

    thread = {
        "messages": [
            {"from": "human", "text": "status?", "ts": 1.0},
            {"from": "agent", "text": "Still tracing owner…", "ts": 2.0},
        ]
    }
    assert format_dm_thread_tail_for_hud(thread) == "Still tracing owner…"


def test_walk_up_dm_hud_outcome_returns_tail():
    from service.dm_threads import WalkUpDmHudStatus, WalkUpDmAppendRequest, walk_up_dm_hud_outcome

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AGENT_OFFICE_WORKSPACE_CONFIG"] = str(Path(tmp) / "workspace_config.json")
        os.environ["AGENT_OFFICE_DM_THREADS"] = str(Path(tmp) / "dm_threads.json")
        try:
            _setup_member(tmp)
            request = WalkUpDmAppendRequest(
                agent_id="research",
                text="status on vault log?",
                source="z_target",
            )
            outcome = walk_up_dm_hud_outcome(request, repo_root=tmp)
            assert outcome.status == WalkUpDmHudStatus.LIVE_TAIL
            assert "tracing owner" in outcome.hud_text.lower()
            assert outcome.message_count == 2
        finally:
            os.environ.pop("AGENT_OFFICE_WORKSPACE_CONFIG", None)
            os.environ.pop("AGENT_OFFICE_DM_THREADS", None)


def test_merge_persisted_dm_tails_into_pragchat_shape():
    from service.dm_threads import merge_persisted_dm_tails

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AGENT_OFFICE_WORKSPACE_CONFIG"] = str(Path(tmp) / "workspace_config.json")
        os.environ["AGENT_OFFICE_DM_THREADS"] = str(Path(tmp) / "dm_threads.json")
        try:
            _setup_member(tmp)
            dm_thread_append_outcome(
                "research",
                from_role="human",
                text="ping",
                repo_root=tmp,
            )
            base = [{"agent_id": "research", "id": "agent-research", "title": "Research"}]
            merged = merge_persisted_dm_tails(base, repo_root=tmp)
            assert merged[0]["message_count"] == 2
            assert merged[0]["messages"][0]["text"] == "ping"
        finally:
            os.environ.pop("AGENT_OFFICE_WORKSPACE_CONFIG", None)
            os.environ.pop("AGENT_OFFICE_DM_THREADS", None)


def test_director_live_reply_when_flag_set():
    from service.director_bridge import DirectorDmReplyStatus, director_dm_reply_outcome
    from service import director_bridge as db

    db._LLM_BACKEND = None
    db._LLM_BACKEND_TRIED = False
    os.environ["AGENT_OFFICE_DIRECTOR_LIVE"] = "1"
    try:
        outcome = director_dm_reply_outcome("research", "vault log status?")
        assert outcome.status == DirectorDmReplyStatus.LIVE
        assert outcome.reply_text
        assert "vault log" in outcome.reply_text.lower() or "index" in outcome.reply_text.lower()
    finally:
        os.environ.pop("AGENT_OFFICE_DIRECTOR_LIVE", None)
        db._LLM_BACKEND = None
        db._LLM_BACKEND_TRIED = False


def test_dm_thread_unread_and_mark_read():
    """Pass 8: agent replies after last_read_at surface as unread; mark-read clears."""
    from service.dm_threads import (
        DmThreadMarkReadStatus,
        compute_dm_thread_unread,
        dm_thread_mark_read_outcome,
    )

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AGENT_OFFICE_WORKSPACE_CONFIG"] = str(Path(tmp) / "workspace_config.json")
        os.environ["AGENT_OFFICE_DM_THREADS"] = str(Path(tmp) / "dm_threads.json")
        try:
            _setup_member(tmp)
            append = dm_thread_append_outcome(
                "code",
                from_role="human",
                text="build status?",
                repo_root=tmp,
            )
            assert append.status == DmThreadAppendStatus.APPENDED
            assert append.thread is not None
            assert compute_dm_thread_unread(append.thread) == 1

            listing = dm_thread_read_outcome("code", repo_root=tmp)
            assert listing.message_count == 2

            marked = dm_thread_mark_read_outcome("code", repo_root=tmp)
            assert marked.status == DmThreadMarkReadStatus.MARKED
            assert marked.unread_count == 0
            assert marked.thread["unread_count_display"] == 0

            read_after = dm_thread_read_outcome("code", repo_root=tmp)
            assert compute_dm_thread_unread(read_after.thread) == 0
        finally:
            os.environ.pop("AGENT_OFFICE_WORKSPACE_CONFIG", None)
            os.environ.pop("AGENT_OFFICE_DM_THREADS", None)


def test_walk_up_stub_texts_cover_all_agents():
    """Pass 8: every roster agent has walk-up utterance + stub reply."""
    from service.dm_threads import AGENT_DM_STUB_REPLIES, VALID_AGENT_IDS, WALK_UP_DM_STUB_TEXTS

    for agent_id in VALID_AGENT_IDS:
        assert agent_id in WALK_UP_DM_STUB_TEXTS, agent_id
        assert agent_id in AGENT_DM_STUB_REPLIES, agent_id


def test_dm_unread_notification_stub():
    """Pass 10: visor notification stub sums unread across threads."""
    from service.dm_threads import format_dm_unread_notification_stub, sum_dm_threads_unread

    threads = [
        {"agent_id": "research", "unread_count_display": 2},
        {"agent_id": "code", "unread_count_display": 1},
    ]
    assert sum_dm_threads_unread(threads) == 3
    stub = format_dm_unread_notification_stub(3)
    assert stub is not None
    assert "3" in stub
    assert format_dm_unread_notification_stub(0) is None


def test_dm_visor_rail_lines_sorted_and_formatted():
    """Pass 14: visor rail rows prioritize unread, then preview last agent line."""
    from service.dm_threads import (
        VISOR_RAIL_LINE_DELIM,
        format_dm_visor_rail_lines,
        format_dm_visor_rail_text,
    )

    threads = [
        {
            "agent_id": "code",
            "unread_count_display": 0,
            "updated_at": 200.0,
            "messages": [
                {"from": "human", "text": "ping", "ts": 100.0},
                {"from": "agent", "text": "Build green on main.", "ts": 110.0},
            ],
        },
        {
            "agent_id": "research",
            "unread_count_display": 2,
            "updated_at": 150.0,
            "messages": [
                {"from": "human", "text": "vault?", "ts": 120.0},
                {"from": "agent", "text": "Still tracing owner…", "ts": 130.0},
            ],
        },
    ]
    lines = format_dm_visor_rail_lines(threads)
    assert len(lines) == 2
    assert lines[0].startswith("@research")
    assert "2 unread" in lines[0]
    assert "Still tracing" in lines[0]
    assert lines[1].startswith("@code")
    assert "Build green" in lines[1]

    rail = format_dm_visor_rail_text(threads)
    assert rail is not None
    assert VISOR_RAIL_LINE_DELIM in rail
    assert rail.split(VISOR_RAIL_LINE_DELIM)[0] == lines[0]


def test_dm_visor_scrollback_lines_from_top_unread_thread():
    """Pass 17: scrollback pane shows message tail from top-priority unread thread."""
    from service.dm_threads import (
        VISOR_SCROLLBACK_LINE_DELIM,
        format_dm_visor_scrollback_lines,
        format_dm_visor_scrollback_text,
    )

    threads = [
        {
            "agent_id": "code",
            "unread_count_display": 0,
            "updated_at": 200.0,
            "messages": [
                {"from": "human", "text": "ping", "ts": 100.0},
                {"from": "agent", "text": "Build green on main.", "ts": 110.0},
            ],
        },
        {
            "agent_id": "research",
            "unread_count_display": 2,
            "updated_at": 150.0,
            "messages": [
                {"from": "human", "text": "vault log?", "ts": 120.0},
                {"from": "agent", "text": "Still tracing owner…", "ts": 130.0},
            ],
        },
    ]
    lines = format_dm_visor_scrollback_lines(threads)
    assert lines[0] == "— @research —"
    assert any("You: vault log?" in line for line in lines)
    assert any("@research: Still tracing" in line for line in lines)
    assert not any("@code:" in line for line in lines)

    scroll = format_dm_visor_scrollback_text(threads)
    assert scroll is not None
    assert VISOR_SCROLLBACK_LINE_DELIM in scroll
    assert scroll.split(VISOR_SCROLLBACK_LINE_DELIM)[0] == lines[0]


def test_visor_compose_target_picks_priority_thread():
    """Pass 21: visor compose targets top-priority thread with visor-prefixed stub text."""
    from service.dm_threads import (
        VISOR_COMPOSE_TEXT_PREFIX,
        project_visor_compose_target,
        visor_compose_stub_text,
    )

    threads = [
        {
            "agent_id": "code",
            "unread_count_display": 0,
            "updated_at": 200.0,
            "messages": [{"from": "human", "text": "ping", "ts": 100.0}],
        },
        {
            "agent_id": "research",
            "unread_count_display": 2,
            "updated_at": 150.0,
            "messages": [{"from": "human", "text": "vault?", "ts": 120.0}],
        },
    ]
    target = project_visor_compose_target(threads)
    assert target is not None
    assert target["agent_id"] == "research"
    assert target["text"] == visor_compose_stub_text("research")
    assert target["text"].startswith(VISOR_COMPOSE_TEXT_PREFIX)
    assert "@research" in target["hint"]
    assert "Tab cycle" in target["hint"]
    assert project_visor_compose_target([]) is None


def test_visor_compose_hint_keyboard_instructions():
    """Pass 22: visor compose hint tells player how to type and submit."""
    from service.dm_threads import format_visor_compose_hint

    hint = format_visor_compose_hint("research")
    assert hint is not None
    assert "@research" in hint
    assert "Enter" in hint
    assert "Esc" in hint
    assert format_visor_compose_hint("") is None


def test_visor_compose_picker_agents_sorted():
    """Pass 23: visor compose picker lists unread-first agents, capped at 4."""
    from service.dm_threads import (
        VISOR_COMPOSE_PICKER_MAX,
        format_visor_compose_picker_agents,
        format_visor_compose_picker_text,
        format_visor_compose_hint,
        project_visor_compose_target,
    )

    threads = [
        {
            "agent_id": "code",
            "unread_count_display": 0,
            "updated_at": 200.0,
            "messages": [{"from": "human", "text": "ping", "ts": 100.0}],
        },
        {
            "agent_id": "research",
            "unread_count_display": 2,
            "updated_at": 150.0,
            "messages": [{"from": "human", "text": "vault?", "ts": 120.0}],
        },
        {
            "agent_id": "ops",
            "unread_count_display": 1,
            "updated_at": 180.0,
            "messages": [{"from": "human", "text": "deploy?", "ts": 130.0}],
        },
    ]
    agents = format_visor_compose_picker_agents(threads)
    assert agents == ["research", "ops", "code"]
    assert format_visor_compose_picker_text(threads) == "research|ops|code"

    target = project_visor_compose_target(threads)
    assert target is not None
    assert target["agent_id"] == "research"
    assert "Tab cycle" in target["hint"]
    assert target["picker_agents"] == agents

    single = [threads[0]]
    assert format_visor_compose_picker_agents(single) == ["code"]
    assert "Tab cycle" not in format_visor_compose_hint("code", ["code"])
    assert format_visor_compose_picker_agents([]) == []

    many = [
        {
            "agent_id": aid,
            "unread_count_display": i,
            "updated_at": float(i),
            "messages": [{"from": "human", "text": "x", "ts": 1.0}],
        }
        for i, aid in enumerate(["director", "research", "code", "ops", "qa"])
    ]
    assert len(format_visor_compose_picker_agents(many)) == VISOR_COMPOSE_PICKER_MAX


def test_director_bridge_uses_injected_llm_backend():
    """Pass 9: live flag + resolved llm-play backend returns backend label on outcome."""
    from service import director_bridge as db
    from service.director_bridge import DirectorDmReplyStatus, director_dm_reply_outcome

    class FakeBackend:
        name = "fake-llm"

        def generate(self, system_prompt: str, user_prompt: str) -> str:
            assert "Return ONLY valid JSON" in system_prompt
            return '{"reply":"Live build check — green on main."}'

    os.environ["AGENT_OFFICE_DIRECTOR_LIVE"] = "1"
    os.environ["AGENT_OFFICE_LLM_BACKEND"] = "auto"
    db._LLM_BACKEND = FakeBackend()
    db._LLM_BACKEND_TRIED = True
    try:
        outcome = director_dm_reply_outcome("code", "build status?")
        assert outcome.status == DirectorDmReplyStatus.LIVE
        assert outcome.reply_text
        assert "green on main" in outcome.reply_text.lower()
        assert outcome.backend == "fake-llm"
        assert outcome.fallback_reason is None
    finally:
        os.environ.pop("AGENT_OFFICE_DIRECTOR_LIVE", None)
        os.environ.pop("AGENT_OFFICE_LLM_BACKEND", None)
        db._LLM_BACKEND = None
        db._LLM_BACKEND_TRIED = False


def test_director_bridge_scripted_fallback_when_backend_raises():
    """Pass 12: llm-play generate errors map to SCRIPTED_FALLBACK, not static DM stub."""
    from service import director_bridge as db
    from service.director_bridge import DirectorDmReplyStatus, director_dm_reply_outcome

    class BrokenBackend:
        name = "broken-llm"

        def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise RuntimeError("provider down")

    os.environ["AGENT_OFFICE_DIRECTOR_LIVE"] = "1"
    os.environ["AGENT_OFFICE_LLM_BACKEND"] = "auto"
    db._LLM_BACKEND = BrokenBackend()
    db._LLM_BACKEND_TRIED = True
    try:
        outcome = director_dm_reply_outcome("research", "vault log status?")
        assert outcome.status == DirectorDmReplyStatus.SCRIPTED_FALLBACK
        assert outcome.reply_text
        assert outcome.fallback_reason == "backend_error:RuntimeError"
        assert "heard you" in outcome.reply_text.lower() or "index" in outcome.reply_text.lower()
    finally:
        os.environ.pop("AGENT_OFFICE_DIRECTOR_LIVE", None)
        os.environ.pop("AGENT_OFFICE_LLM_BACKEND", None)
        db._LLM_BACKEND = None
        db._LLM_BACKEND_TRIED = False


def test_director_bridge_scripted_fallback_when_backend_times_out():
    """Pass 12: slow llm-play generate respects AGENT_OFFICE_LLM_TIMEOUT_SEC."""
    import time

    from service import director_bridge as db
    from service.director_bridge import DirectorDmReplyStatus, director_dm_reply_outcome

    class SlowBackend:
        name = "slow-llm"

        def generate(self, system_prompt: str, user_prompt: str) -> str:
            time.sleep(0.25)
            return '{"reply":"too late"}'

    os.environ["AGENT_OFFICE_DIRECTOR_LIVE"] = "1"
    os.environ["AGENT_OFFICE_LLM_BACKEND"] = "auto"
    os.environ["AGENT_OFFICE_LLM_TIMEOUT_SEC"] = "0.05"
    db._LLM_BACKEND = SlowBackend()
    db._LLM_BACKEND_TRIED = True
    try:
        outcome = director_dm_reply_outcome("code", "build status?")
        assert outcome.status == DirectorDmReplyStatus.SCRIPTED_FALLBACK
        assert outcome.fallback_reason == "backend_timeout"
        assert outcome.reply_text
    finally:
        os.environ.pop("AGENT_OFFICE_DIRECTOR_LIVE", None)
        os.environ.pop("AGENT_OFFICE_LLM_BACKEND", None)
        os.environ.pop("AGENT_OFFICE_LLM_TIMEOUT_SEC", None)
        db._LLM_BACKEND = None
        db._LLM_BACKEND_TRIED = False


def test_dm_append_uses_scripted_fallback_not_static_stub():
    """Pass 12: SCRIPTED_FALLBACK director line wins over AGENT_DM_STUB_REPLIES."""
    from service import director_bridge as db
    from service.dm_threads import DmThreadAppendStatus, dm_thread_append_outcome

    class BrokenBackend:
        name = "broken-llm"

        def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise RuntimeError("offline")

    os.environ["AGENT_OFFICE_DIRECTOR_LIVE"] = "1"
    os.environ["AGENT_OFFICE_LLM_BACKEND"] = "auto"
    db._LLM_BACKEND = BrokenBackend()
    db._LLM_BACKEND_TRIED = True

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AGENT_OFFICE_WORKSPACE_CONFIG"] = str(Path(tmp) / "workspace_config.json")
        os.environ["AGENT_OFFICE_DM_THREADS"] = str(Path(tmp) / "dm_threads.json")
        try:
            _setup_member(tmp)
            append = dm_thread_append_outcome(
                "research",
                from_role="human",
                text="vault log status?",
                repo_root=tmp,
                stub_reply=True,
            )
            assert append.status == DmThreadAppendStatus.APPENDED
            assert append.stub_reply is False
            assert append.director_live is False
            agent_lines = [m for m in append.thread["messages"] if m["from"] == "agent"]
            assert len(agent_lines) == 1
            assert "Still tracing owner" not in agent_lines[0]["text"]
        finally:
            os.environ.pop("AGENT_OFFICE_WORKSPACE_CONFIG", None)
            os.environ.pop("AGENT_OFFICE_DM_THREADS", None)
            os.environ.pop("AGENT_OFFICE_DIRECTOR_LIVE", None)
            os.environ.pop("AGENT_OFFICE_LLM_BACKEND", None)
            db._LLM_BACKEND = None
            db._LLM_BACKEND_TRIED = False


def test_dm_threads_file_lock_wiring_present():
    """Pass 24: append/mark-read paths use advisory dm_threads.json file lock."""
    src = (REPO / "tools/agent_office_llm/service/dm_threads.py").read_text(encoding="utf-8")
    assert "_dm_threads_file_lock" in src
    assert "fcntl.flock" in src
    assert "_save_dm_threads_unlocked" in src
    assert "with _dm_threads_file_lock(repo_root):" in src
    assert "dm_thread_append" in src.split("with _dm_threads_file_lock(repo_root):")[1]
    assert "dm_thread_mark_read" in src.split("with _dm_threads_file_lock(repo_root):")[2]


def test_concurrent_dm_thread_append_parity():
    """Pass 24 Scenario 9: concurrent visor/walk-up/Electron DM writes stay valid — no lost messages."""
    from concurrent.futures import ThreadPoolExecutor

    agents = [
        "research",
        "security",
        "code",
        "ops",
        "comms",
        "qa",
        "director",
        "orchestrator",
    ]

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AGENT_OFFICE_WORKSPACE_CONFIG"] = str(Path(tmp) / "workspace_config.json")
        os.environ["AGENT_OFFICE_DM_THREADS"] = str(Path(tmp) / "dm_threads.json")
        try:
            member_id = _setup_member(tmp)

            def visor_compose(agent_id: str, seq: int) -> None:
                dm_thread_append_outcome(
                    agent_id,
                    from_role="human",
                    text=f"visor:{seq}",
                    repo_root=tmp,
                    stub_reply=False,
                )

            def walk_up(agent_id: str, seq: int) -> None:
                dm_thread_append_outcome(
                    agent_id,
                    from_role="human",
                    text=f"walk:{seq}",
                    repo_root=tmp,
                    stub_reply=False,
                )

            def electron_compose(agent_id: str, seq: int) -> None:
                dm_thread_append_outcome(
                    agent_id,
                    from_role="human",
                    text=f"electron:{seq}",
                    repo_root=tmp,
                    stub_reply=False,
                )

            def mark_read(agent_id: str) -> None:
                dm_thread_mark_read_outcome(agent_id, repo_root=tmp)

            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = []
                for seq, agent_id in enumerate(agents):
                    futures.append(pool.submit(visor_compose, agent_id, seq))
                    futures.append(pool.submit(walk_up, agent_id, seq + 10))
                    futures.append(pool.submit(electron_compose, agent_id, seq + 20))
                for agent_id in agents[:4]:
                    futures.append(pool.submit(mark_read, agent_id))
                for fut in futures:
                    fut.result()

            status, doc, _, _ = load_dm_threads_outcome(repo_root=tmp)
            assert status == DmThreadsLoadStatus.FOUND
            assert doc is not None
            parse_dm_threads_document(doc.to_dict())

            for agent_id in agents:
                thread = next(t for t in doc.threads if t.agent_id == agent_id)
                assert thread.member_user_id == member_id
                human_msgs = [m for m in thread.messages if m.from_role == "human"]
                assert len(human_msgs) == 3
                texts = {m.text for m in human_msgs}
                assert any(text.startswith("visor:") for text in texts)
                assert any(text.startswith("walk:") for text in texts)
                assert any(text.startswith("electron:") for text in texts)
        finally:
            os.environ.pop("AGENT_OFFICE_WORKSPACE_CONFIG", None)
            os.environ.pop("AGENT_OFFICE_DM_THREADS", None)


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{'OK' if not fails else str(fails) + ' FAILED'}")
    sys.exit(1 if fails else 0)
