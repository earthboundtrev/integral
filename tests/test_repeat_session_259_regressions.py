"""Regression tests for PR #287 tester findings."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import tkinter as tk
from tkinter import ttk

import pytest

import theme as app_theme
from fitness_repeat_ui import RecentSessionsOverlay, build_repeat_type_menu
from fitness_ui import ensure_fitness_seeded, open_new_session_dialog, repeat_session_into_log
from progression.db import FitnessRepository
from progression.session_repeat import list_repeatable_session_rows
from progression.sessions import prefill_from_latest_session, prefill_from_session
from tests.conftest import create_tk_root, pump_tk


def make_repo(tmp_path) -> FitnessRepository:
    return FitnessRepository(str(tmp_path / "fitness.db"))


def _insert_session_raw(repo, session_id: str, date: str, created_at: str) -> None:
    with repo.connect() as conn:
        conn.execute(
            """
            INSERT INTO workout_sessions (id, date, notes, duration_minutes, body_weight_kg, created_at)
            VALUES (?, ?, '', NULL, NULL, ?)
            """,
            (session_id, date, created_at),
        )
        conn.commit()


def _insert_set_raw(
    repo,
    session_id: str,
    exercise_id: str,
    *,
    sets: int = 3,
    reps: int = 10,
    ordinal: int = 0,
) -> None:
    with repo.connect() as conn:
        conn.execute(
            """
            INSERT INTO workout_sets (
                id, session_id, exercise_id, sets, reps, hold_seconds, weight_kg, form_quality, ordinal, created_at
            ) VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, ?, datetime('now'))
            """,
            (str(uuid4()), session_id, exercise_id, sets, reps, ordinal),
        )
        conn.commit()


def _seed_push_vs_bridge(repo: FitnessRepository) -> tuple[str, str]:
    push = repo.get_exercise("cc1_push_01")
    bridge = repo.get_exercise("cc1_bridge_01")
    form_date = "2026-11-22"
    _insert_session_raw(repo, "push-only", "2026-11-09", "2026-11-09T10:00:00+00:00")
    _insert_set_raw(repo, "push-only", push.id, sets=9, reps=9)
    _insert_session_raw(repo, "bridge-only", "2026-11-10", "2026-11-10T10:00:00+00:00")
    _insert_set_raw(repo, "bridge-only", bridge.id, sets=3, reps=3)
    return "push-only", "bridge-only"


def _listbox_texts(root: tk.Misc) -> list[str]:
    lines: list[str] = []
    stack = [root]
    while stack:
        widget = stack.pop()
        if isinstance(widget, tk.Listbox):
            try:
                lines.extend(widget.get(0, tk.END))
            except tk.TclError:
                pass
        try:
            stack.extend(widget.winfo_children())
        except tk.TclError:
            pass
    return lines


def _log_toplevels(root: tk.Misc) -> list[tk.Toplevel]:
    return [
        w
        for w in root.winfo_children()
        if isinstance(w, tk.Toplevel) and w.winfo_exists() and w.title() == "Log Exercise Session"
    ]


@pytest.fixture
def tk_root():
    root = create_tk_root()
    yield root
    try:
        for w in list(root.winfo_children()):
            try:
                w.destroy()
            except tk.TclError:
                pass
        root.destroy()
    except tk.TclError:
        pass


def test_alt_r_after_last_push_prefill_uses_last_overall(tmp_path, tk_root):
    """Last Push (by session id), then Alt+R Replace must queue last-overall."""
    repo = make_repo(tmp_path)
    ensure_fitness_seeded(repo)
    _seed_push_vs_bridge(repo)
    theme = app_theme.get_theme(False)
    tracker = SimpleNamespace(_log_exercise_dialog=None)

    dialog = open_new_session_dialog(
        tk_root,
        repo,
        initial_date="2026-11-22",
        theme=theme,
        tracker=tracker,
    )
    pump_tk(tk_root, 40)

    dialog._integral_repeat_session("push-only")
    pump_tk(tk_root, 20)
    assert any("9x9" in line or "9" in line for line in _listbox_texts(dialog))

    dialog.event_generate("<Alt-r>")
    pump_tk(tk_root, 20)
    dialog.event_generate("<Return>")
    pump_tk(tk_root, 20)

    lines = _listbox_texts(dialog)
    assert any("3x3" in line or "Bridge" in line or "bridge" in line.lower() for line in lines)

    items, overall_id, _ = prefill_from_latest_session(repo, exclude_date="2026-11-22")
    assert overall_id == "bridge-only"
    assert items[0]["reps"] == 3


def test_type_menu_builds_without_family_context(tmp_path, tk_root):
    root = tk_root
    repo = make_repo(tmp_path)
    ensure_fitness_seeded(repo)
    push_id, bridge_id = _seed_push_vs_bridge(repo)
    menu = build_repeat_type_menu(
        root,
        [("push", "Last Push (Nov 9)", push_id)],
        on_pick_session=lambda _sid: None,
        on_pick_history=lambda: None,
    )
    assert menu.index("end") is not None
    _, overall_id, _ = prefill_from_latest_session(repo, exclude_date="2026-11-22", family=None)
    assert overall_id == bridge_id


def test_open_new_session_dialog_registers_tracker_ref(tmp_path, tk_root):
    repo = make_repo(tmp_path)
    ensure_fitness_seeded(repo)
    _insert_session_raw(repo, "hist", "2026-11-01", "2026-11-01T10:00:00+00:00")
    _insert_set_raw(repo, "hist", repo.get_exercise("cc1_push_01").id)
    tracker = SimpleNamespace(_log_exercise_dialog=None)
    theme = app_theme.get_theme(False)

    dialog = open_new_session_dialog(
        tk_root,
        repo,
        initial_date="2026-11-22",
        theme=theme,
        tracker=tracker,
    )
    pump_tk(tk_root, 20)
    assert tracker._log_exercise_dialog is dialog

    repeat_session_into_log(
        tk_root,
        repo,
        "hist",
        tracker=tracker,
        theme=theme,
    )
    pump_tk(tk_root, 20)
    assert len(_log_toplevels(tk_root)) == 1


def test_show_log_exercise_path_shares_single_log_toplevel(tmp_path, tk_root):
    repo = make_repo(tmp_path)
    ensure_fitness_seeded(repo)
    _insert_session_raw(repo, "hist", "2026-11-01", "2026-11-01T10:00:00+00:00")
    _insert_set_raw(repo, "hist", repo.get_exercise("cc1_push_01").id)
    tracker = SimpleNamespace(_log_exercise_dialog=None)
    theme = app_theme.get_theme(False)

    first = open_new_session_dialog(tk_root, repo, initial_date="2026-11-22", theme=theme, tracker=tracker)
    pump_tk(tk_root, 20)
    repeat_session_into_log(tk_root, repo, "hist", tracker=tracker, theme=theme)
    pump_tk(tk_root, 20)
    assert len(_log_toplevels(tk_root)) == 1
    second = open_new_session_dialog(tk_root, repo, initial_date="2026-11-22", theme=theme, tracker=tracker)
    pump_tk(tk_root, 20)
    assert second is first
    assert len(_log_toplevels(tk_root)) == 1


def test_replace_bar_escape_keeps_dialog_open(tmp_path, tk_root):
    repo = make_repo(tmp_path)
    ensure_fitness_seeded(repo)
    _seed_push_vs_bridge(repo)
    theme = app_theme.get_theme(False)

    dialog = open_new_session_dialog(
        tk_root,
        repo,
        initial_date="2026-11-22",
        theme=theme,
    )
    pump_tk(tk_root, 40)
    dialog._integral_repeat_session("push-only")
    pump_tk(tk_root, 20)
    dialog._integral_repeat_session("bridge-only")
    pump_tk(tk_root, 20)

    with patch("tkinter.messagebox.askyesno") as ask:
        dialog.event_generate("<Escape>")
        pump_tk(tk_root, 20)
        assert dialog.winfo_exists()
        ask.assert_not_called()


def test_overlay_close_does_not_unbind_all_escape(tmp_path, tk_root):
    repo = make_repo(tmp_path)
    ensure_fitness_seeded(repo)
    _seed_push_vs_bridge(repo)
    theme = app_theme.get_theme(False)

    dialog = open_new_session_dialog(
        tk_root,
        repo,
        initial_date="2026-11-22",
        theme=theme,
    )
    pump_tk(tk_root, 40)

    rows = list_repeatable_session_rows(repo, exclude_date="2026-11-22", limit=10)
    overlay = RecentSessionsOverlay(
        dialog,
        theme,
        on_pick=lambda _sid: None,
        on_close=lambda: None,
        default_session_id=None,
    )
    caret = None
    for w in dialog.winfo_children():
        if isinstance(w, ttk.Frame):
            for c in w.winfo_children():
                if isinstance(c, ttk.Button) and c.cget("text") == "▾":
                    caret = c
    assert caret is not None

    def forbid_unbind_all(_seq):
        raise AssertionError("overlay must not call unbind_all for Escape")

    with patch.object(tk.Misc, "unbind_all", side_effect=forbid_unbind_all):
        overlay.show(caret, rows)
        pump_tk(tk_root, 20)
        overlay.close()
        pump_tk(tk_root, 20)

    bound = dialog.bind("<Escape>")
    assert bound, "log dialog Escape binding must survive overlay close"