"""Shared restore/undo busy blocks saves (#271)."""

from __future__ import annotations

import tkinter as tk

import pytest

import backup_dialog_ui
import paths

from tests.conftest import create_tk_root
from tests.test_backup import temp_app  # noqa: F401
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file


@pytest.fixture
def tk_root():
    root = create_tk_root(withdraw=True)
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def tracker_with_data(tk_root, temp_app, monkeypatch):
    import personal_dev_tracker as pdt_mod

    _seed_data_file(_minimal_v2_payload())
    monkeypatch.setattr(pdt_mod, "DATA_FILE", paths.data_file())
    tracker = pdt_mod.PersonalDevelopmentTracker(tk_root)
    return tracker


def test_save_data_blocked_while_restore_operation_active(tracker_with_data, temp_app):
    tracker = tracker_with_data
    data_path = paths.data_file()
    before = open(data_path, encoding="utf-8").read()
    backup_dialog_ui.begin_restore_operation(tracker)
    try:
        tracker.entries["2099-01-01"] = {
            "Emotional Wellbeing": {"rating": 9, "checklist": {}, "metrics": {}, "notes": "stale"}
        }
        tracker.save_data(flush=True)
        tracker.root.update_idletasks()
        assert open(data_path, encoding="utf-8").read() == before
        assert tracker._restore_deferred_saves
    finally:
        backup_dialog_ui.end_restore_operation()


def test_restore_dialog_close_blocked_while_busy(tk_root, tracker_with_data):
    tracker = tracker_with_data
    backup_dialog_ui.show_backup_dialog(tracker)
    tk_root.update_idletasks()
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    backup_dialog_ui.begin_restore_operation(tracker)
    try:
        assert backup_dialog_ui.restore_operation_in_progress()
        dialog.event_generate("<Escape>")
        tk_root.update_idletasks()
        assert dialog.winfo_exists()
    finally:
        backup_dialog_ui.end_restore_operation()