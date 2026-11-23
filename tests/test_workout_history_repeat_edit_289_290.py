"""GitHub issues #289 and #290 — repeat blocked while editing; single detail footer."""

from __future__ import annotations

import gc
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from progression.db import FitnessRepository
from progression.models import Exercise, WorkoutSession, WorkoutSet


def _temp_repo() -> tuple[FitnessRepository, str]:
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    handle.close()
    repo = FitnessRepository(db_path=handle.name)
    repo.initialize()
    return repo, handle.name


def _dispose_temp_repo(repo: FitnessRepository | None, path: str) -> None:
    if repo is not None:
        del repo
    gc.collect()
    try:
        os.unlink(path)
    except OSError:
        pass


def _session_with_set(repo: FitnessRepository) -> WorkoutSession:
    ex = Exercise(id="ex1", name="Pull", source_book="CC", family="pull", mastery_criteria={})
    repo.add_exercise(ex)
    session = WorkoutSession(date="2026-06-15", created_at="2026-06-15T10:00:00Z")
    repo.add_workout_session(session)
    wset = WorkoutSet(
        id="s1",
        session_id=session.id,
        exercise_id="ex1",
        sets=3,
        reps=10,
        ordinal=0,
    )
    repo.add_workout_set(wset)
    return session


def _is_descendant_of(widget, ancestor) -> bool:
    current = widget
    while current is not None:
        if current is ancestor:
            return True
        current = getattr(current, "master", None)
    return False


def _bottom_packed_frames(parent) -> list:
    frames = []
    for child in parent.winfo_children():
        if child.winfo_manager() != "pack":
            continue
        if child.pack_info().get("side") == "bottom":
            frames.append(child)
    return frames


class TestWorkoutHistorySingleFooter290(unittest.TestCase):
    def test_one_footer_row_when_both_hooks_present(self):
        try:
            import tkinter as tk

            from theme import get_theme
            from workout_history_ui import WorkoutHistoryView
        except ImportError:
            self.skipTest("tkinter not available")

        repo, path = _temp_repo()
        session = _session_with_set(repo)
        root = tk.Tk()
        root.withdraw()
        try:
            repeat_hook = MagicMock()
            view = WorkoutHistoryView(
                root,
                repo,
                get_theme(False),
                on_repeat_session=repeat_hook,
            )
            view.selected_session = session
            view.sets_by_session[session.id] = repo.list_workout_sets(session.id)
            root.update_idletasks()
            detail_frame = view.detail_stack.master
            bottoms = _bottom_packed_frames(detail_frame)
            self.assertEqual(len(bottoms), 1, "session detail pane must have one bottom footer")
            self.assertTrue(_is_descendant_of(view.edit_btn, view.detail_actions))
            assert view.repeat_session_btn is not None
            self.assertTrue(_is_descendant_of(view.repeat_session_btn, view.detail_actions))
        finally:
            view.destroy()
            root.destroy()
            _dispose_temp_repo(repo, path)

    def test_repeat_not_packed_when_hook_missing(self):
        try:
            import tkinter as tk

            from theme import get_theme
            from workout_history_ui import WorkoutHistoryView
        except ImportError:
            self.skipTest("tkinter not available")

        repo, path = _temp_repo()
        _session_with_set(repo)
        root = tk.Tk()
        root.withdraw()
        try:
            view = WorkoutHistoryView(root, repo, get_theme(False), on_repeat_session=None)
            root.update_idletasks()
            self.assertFalse(
                getattr(view, "repeat_session_btn", None)
                and view.repeat_session_btn.winfo_manager() == "pack",
                "Repeat control must not be packed when on_repeat_session is None",
            )
            detail_frame = view.detail_stack.master
            self.assertEqual(len(_bottom_packed_frames(detail_frame)), 1)
        finally:
            view.destroy()
            root.destroy()
            _dispose_temp_repo(repo, path)


class TestWorkoutHistoryRepeatWhileEditing289(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk

            from theme import get_theme
            from workout_history_ui import WorkoutHistoryView
        except ImportError:
            self.skipTest("tkinter not available")

        self.tk = tk
        self.get_theme = get_theme
        self.WorkoutHistoryView = WorkoutHistoryView

    def _open_view(self, repeat_hook: MagicMock):
        repo, self._path = _temp_repo()
        self._repo = repo
        session = _session_with_set(repo)
        root = self.tk.Tk()
        root.withdraw()
        view = self.WorkoutHistoryView(
            root,
            repo,
            self.get_theme(False),
            on_repeat_session=repeat_hook,
        )
        view.selected_session = session
        view.sets_by_session[session.id] = repo.list_workout_sets(session.id)
        root.update_idletasks()
        return root, repo, session, view

    def tearDown(self):
        path = getattr(self, "_path", None)
        if path:
            _dispose_temp_repo(getattr(self, "_repo", None), path)
            self._path = None
            self._repo = None

    def test_repeat_hook_blocked_while_editing_button_and_alt_r(self):
        repeat_hook = MagicMock()
        root, repo, session, view = self._open_view(repeat_hook)
        try:
            view._enter_edit_mode()
            root.update_idletasks()
            self.assertTrue(view._session_editing)
            repeat_hook.reset_mock()

            view._invoke_repeat_session()
            view._on_alt_repeat_session()
            self.assertEqual(repeat_hook.call_count, 0)

            assert view.repeat_session_btn is not None
            self.assertTrue(view.repeat_session_btn.instate(["disabled"]))

            view._exit_edit_mode()
            root.update_idletasks()
            repeat_hook.reset_mock()
            view._invoke_repeat_session()
            repeat_hook.assert_called_once_with(session.id)
        finally:
            view.destroy()
            root.destroy()

    def test_alt_r_returns_break_while_editing_including_from_entry(self):
        repeat_hook = MagicMock()
        root, repo, session, view = self._open_view(repeat_hook)
        try:
            view._enter_edit_mode()
            root.update_idletasks()
            panel = view._edit_panel
            assert panel is not None
            reps_entry = panel._row_widgets[0]["reps"]
            reps_entry.focus_set()
            root.update_idletasks()
            repeat_hook.reset_mock()

            with patch.object(view._status_banner, "show_info") as show_info:
                result = view._on_alt_repeat_session()
                self.assertEqual(result, "break")
                repeat_hook.assert_not_called()
                show_info.assert_called_once()
                self.assertIn("Finish or cancel", show_info.call_args[0][0])
        finally:
            view.destroy()
            root.destroy()

    def test_esc_exit_edit_allows_repeat_again(self):
        repeat_hook = MagicMock()
        root, repo, session, view = self._open_view(repeat_hook)
        try:
            view._enter_edit_mode()
            root.update_idletasks()
            panel = view._edit_panel
            assert panel is not None
            panel._on_cancel_event()
            root.update()
            self.assertFalse(view._session_editing)
            repeat_hook.reset_mock()
            view._invoke_repeat_session()
            repeat_hook.assert_called_once_with(session.id)
        finally:
            view.destroy()
            root.destroy()

    def test_view_mode_alt_r_unchanged_when_not_editing(self):
        repeat_hook = MagicMock()
        root, repo, session, view = self._open_view(repeat_hook)
        try:
            self.assertFalse(view._session_editing)
            view._on_alt_repeat_session()
            repeat_hook.assert_called_once_with(session.id)
        finally:
            view.destroy()
            root.destroy()


if __name__ == "__main__":
    unittest.main()