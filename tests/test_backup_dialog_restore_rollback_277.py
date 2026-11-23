"""Restore journal snap rollback and startup cleanup (#277)."""

from __future__ import annotations

import json
import os
import pathlib
import tkinter as tk
from contextlib import ExitStack
from tkinter import ttk
from unittest.mock import patch

import pytest

pytest.importorskip("cryptography")

import backup
import backup_dialog_ui
import paths
import personal_dev_tracker
import profiles
import storage
from backup_dialog_ui import (
    GENERIC_RESTORE_ERROR,
    GENERIC_RESTORE_PENDING_ROLLBACK_MSG,
    _artifact_has_pending_rollback,
    _journal_snapshot_path,
    _move_unreadable_journal_aside,
    _rollback_journal_copies,
    _rollback_journal_from_snapshot,
    _rollback_pending_marker_path,
    _snapshot_file_if_present,
    _snapshot_journal_if_present,
    restore_blocked_by_pending_rollback,
    sweep_pre_restore_journal_snaps_at_startup,
)
from tests.conftest import pump_tk, pump_tk_until
from tests.test_backup import temp_app  # noqa: F401
from tests.test_backup_dialog_pr275_ui import _find_button, _label_texts, _walk
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file
from vault import is_encrypted_file, save_data_file


@pytest.fixture(autouse=True)
def _sync_data_file(monkeypatch):
    monkeypatch.setattr(personal_dev_tracker, "DATA_FILE", paths.data_file())


@pytest.fixture
def immediate_threads(monkeypatch):
    class _ImmediateThread:
        def __init__(self, target=None, daemon=None, args=(), kwargs=None):
            self._target = target

        def start(self) -> None:
            if self._target:
                self._target()

    monkeypatch.setattr(backup_dialog_ui.threading, "Thread", _ImmediateThread)


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def _journal_notes(data_path: str) -> str | None:
    if is_encrypted_file(data_path):
        return "encrypted"
    try:
        with open(data_path, encoding="utf-8") as handle:
            data = json.load(handle)
        notes = (
            data.get("entries", {})
            .get("2000-01-01", {})
            .get("Emotional Wellbeing", {})
            .get("notes")
        )
        return notes
    except (OSError, json.JSONDecodeError, TypeError, KeyError):
        return None


def test_rollback_uses_replace_and_keeps_journal_on_replace_failure(temp_app, tmp_path, monkeypatch):
    data_path = str(tmp_path / "data.json")
    prior = storage.empty_data()
    prior["entries"]["2000-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": "keep-me"}
    }
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(prior, handle)
    snap = _snapshot_journal_if_present(data_path)
    assert snap and os.path.isfile(snap)
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "entries": {
                    "2099-01-01": {
                        "Emotional Wellbeing": {
                            "rating": 9,
                            "checklist": {},
                            "metrics": {},
                            "notes": "broken-apply",
                        }
                    }
                }
            },
            handle,
        )

    _patch_failed_snap_to_live_replace(monkeypatch)
    assert _rollback_journal_from_snapshot(data_path, snap) is False

    with open(data_path, encoding="utf-8") as handle:
        on_disk = json.load(handle)
    assert (
        on_disk["entries"]["2099-01-01"]["Emotional Wellbeing"]["notes"] == "broken-apply"
    )
    assert os.path.isfile(snap)
    msg = backup_dialog_ui._safe_user_error(PermissionError("C:\\secret\\data.json"), context="restore")
    assert "data.json" not in msg
    assert GENERIC_RESTORE_ERROR in msg or "Restore failed" in msg


def _make_selective_failed_snap_replace():
    real_replace = os.replace

    def selective(src, dst, *args, **kwargs):
        src_s, dst_s = str(src), str(dst)
        if (
            src_s.endswith(".pre-restore-snap")
            and not dst_s.endswith(".tmp")
            and _ROLLBACK_MARKER_BASENAME not in dst_s
        ):
            raise PermissionError("locked")
        return real_replace(src, dst, *args, **kwargs)

    return selective


def _patch_failed_snap_to_live_replace(monkeypatch):
    monkeypatch.setattr(backup_dialog_ui.os, "replace", _make_selective_failed_snap_replace())


_ROLLBACK_MARKER_BASENAME = ".integral-restore-rollback-pending.json"


def _write_sqlite_stub(path: pathlib.Path, payload: bytes = b"") -> None:
    header = b"SQLite format 3\x00"
    body = payload or b"stub"
    with open(path, "wb") as handle:
        handle.write(header + b"\x00" * 80 + body)


def test_failed_rollback_with_valid_live_json_recovers_via_marker(tmp_path, monkeypatch):
    data_path = tmp_path / "data.json"
    container = str(tmp_path)
    prior = storage.empty_data()
    prior["entries"]["2000-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": "pre-restore"}
    }
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(prior, handle)
    snap = _snapshot_journal_if_present(str(data_path))
    backup_live = _minimal_v2_payload()
    backup_live["entries"]["2099-08-01"] = {
        "Emotional Wellbeing": {"rating": 9, "checklist": {}, "metrics": {}, "notes": "from-backup"}
    }
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(backup_live, handle)

    with patch.object(backup_dialog_ui.os, "replace", _make_selective_failed_snap_replace()):
        assert (
            _rollback_journal_copies(
                str(data_path), snap, None, None, journal_existed=True
            )
            is False
        )

    assert snap and os.path.isfile(snap)
    assert _artifact_has_pending_rollback(container, "data.json")
    with open(data_path, encoding="utf-8") as handle:
        assert json.load(handle)["entries"]["2099-08-01"]["Emotional Wellbeing"]["notes"] == "from-backup"

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(data_path), container)],
    ):
        sweep_pre_restore_journal_snaps_at_startup()

    with open(data_path, encoding="utf-8") as handle:
        loaded = json.load(handle)
    assert loaded["entries"]["2000-01-01"]["Emotional Wellbeing"]["notes"] == "pre-restore"
    aside_files = list(pathlib.Path(container).glob("data.json.rolled-back-*"))
    assert len(aside_files) == 1
    with open(aside_files[0], encoding="utf-8") as handle:
        aside = json.load(handle)
    assert aside["entries"]["2099-08-01"]["Emotional Wellbeing"]["notes"] == "from-backup"
    assert not os.path.isfile(snap)
    assert not os.path.isfile(_rollback_pending_marker_path(container))


def test_marker_apply_preserves_newer_live_in_rolled_back_aside(tmp_path, monkeypatch):
    data_path = tmp_path / "data.json"
    container = str(tmp_path)
    prior = storage.empty_data()
    prior["entries"]["2000-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": "snap-prior"}
    }
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(prior, handle)
    snap_path = _snapshot_journal_if_present(str(data_path))
    newer = _minimal_v2_payload()
    newer["entries"]["2099-12-01"] = {
        "Emotional Wellbeing": {"rating": 5, "checklist": {}, "metrics": {}, "notes": "newer-after-save"}
    }
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(newer, handle)

    marker_path = _rollback_pending_marker_path(container)
    with open(marker_path, "w", encoding="utf-8") as handle:
        json.dump({"version": 1, "artifacts": ["data.json"]}, handle)

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(data_path), container)],
    ):
        sweep_pre_restore_journal_snaps_at_startup()

    with open(data_path, encoding="utf-8") as handle:
        live = json.load(handle)
    assert live["entries"]["2000-01-01"]["Emotional Wellbeing"]["notes"] == "snap-prior"
    aside_files = list(tmp_path.glob("data.json.rolled-back-*"))
    assert len(aside_files) == 1
    with open(aside_files[0], encoding="utf-8") as handle:
        aside = json.load(handle)
    assert aside["entries"]["2099-12-01"]["Emotional Wellbeing"]["notes"] == "newer-after-save"
    assert not pathlib.Path(snap_path).exists()


def test_pending_marker_blocks_restore_and_preserves_snap_bytes(tmp_path, monkeypatch):
    data_path = tmp_path / "data.json"
    container = str(tmp_path)
    prior = storage.empty_data()
    prior["entries"]["2000-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": "marker-snap"}
    }
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(prior, handle)
    snap_path = _snapshot_journal_if_present(str(data_path))
    snap_bytes = pathlib.Path(snap_path).read_bytes()

    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(_minimal_v2_payload(), handle)

    marker_path = _rollback_pending_marker_path(container)
    with open(marker_path, "w", encoding="utf-8") as handle:
        json.dump({"version": 1, "artifacts": ["data.json"]}, handle)

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(data_path), container)],
    ):
        assert restore_blocked_by_pending_rollback()

    reused = _snapshot_journal_if_present(str(data_path))
    assert reused == snap_path
    assert pathlib.Path(snap_path).read_bytes() == snap_bytes


def test_guard_restore_shows_plain_message(temp_app, tk_root):
    data_path = paths.data_file()
    container = os.path.dirname(data_path)
    marker_path = _rollback_pending_marker_path(container)
    os.makedirs(container, exist_ok=True)

    _seed_data_file(_minimal_v2_payload())
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    banner = tracker.ensure_status_banner()
    with open(marker_path, "w", encoding="utf-8") as handle:
        json.dump({"version": 1, "artifacts": ["data.json"]}, handle)

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(data_path, container)],
    ):
        assert backup_dialog_ui._guard_restore_against_pending_rollback(tracker) is False

    assert GENERIC_RESTORE_PENDING_ROLLBACK_MSG in (banner._message_var.get() or "")
    try:
        os.remove(marker_path)
    except OSError:
        pass


def test_rollback_copies_keeps_snap_then_startup_recovers(temp_app, tmp_path, monkeypatch):
    # absent live path still recovers once marker defers snap deletion
    data_path = str(tmp_path / "data.json")
    prior = storage.empty_data()
    prior["entries"]["2000-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": "from-snap"}
    }
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(prior, handle)
    snap = _snapshot_journal_if_present(data_path)
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump({"entries": {}}, handle)

    with patch.object(backup_dialog_ui.os, "replace", _make_selective_failed_snap_replace()):
        assert (
            _rollback_journal_copies(data_path, snap, None, None, journal_existed=True)
            is False
        )
    assert snap and os.path.isfile(snap)

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(data_path, str(tmp_path))],
    ):
        sweep_pre_restore_journal_snaps_at_startup()

    with open(data_path, encoding="utf-8") as handle:
        loaded = json.load(handle)
    assert loaded["entries"]["2000-01-01"]["Emotional Wellbeing"]["notes"] == "from-snap"


def test_move_unreadable_aside_unique_within_same_second(tmp_path, monkeypatch):
    from datetime import datetime as real_datetime

    data_path = tmp_path / "data.json"
    fixed = real_datetime(2026, 1, 1, 12, 0, 0, 123456)

    class _FixedDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr(backup_dialog_ui, "datetime", _FixedDatetime)

    data_path.write_text("first", encoding="utf-8")
    aside1 = _move_unreadable_journal_aside(str(data_path))
    assert aside1
    data_path.write_text("second", encoding="utf-8")
    aside2 = _move_unreadable_journal_aside(str(data_path))
    assert aside2
    assert aside1 != aside2
    assert (tmp_path / os.path.basename(aside1)).read_text(encoding="utf-8") == "first"
    assert (tmp_path / os.path.basename(aside2)).read_text(encoding="utf-8") == "second"


def test_reencrypt_failure_restores_data_json_and_fitness_db_bytes(temp_app, tmp_path):
    import profiles

    profiles.set_active_profile("default")
    data_path = paths.data_file()
    prior_payload = _minimal_v2_payload()
    prior_payload["entries"]["2000-01-01"] = {
        "Emotional Wellbeing": {"rating": 4, "checklist": {}, "metrics": {}, "notes": "keep-json"}
    }
    _seed_data_file(prior_payload)
    prior_json = pathlib.Path(data_path).read_bytes()

    db_path = os.path.join(profiles.get_profile_dir("default"), "fitness.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    prior_db = b"PRIOR-FITNESS-DB-277"
    with open(db_path, "wb") as handle:
        handle.write(prior_db)

    journal_snap = _snapshot_journal_if_present(data_path)
    fitness_snap = _snapshot_file_if_present(db_path)
    fitness_rollbacks = [(db_path, fitness_snap, True)]

    restored = storage.empty_data()
    restored["entries"]["2099-01-01"] = {
        "Emotional Wellbeing": {"rating": 9, "checklist": {}, "metrics": {}, "notes": "new"}
    }
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(restored, handle)
    with open(db_path, "wb") as handle:
        handle.write(b"NEW-FITNESS-DB-CONTENT")

    with patch(
        "backup_dialog_ui.reencrypt_restored_journal_from_disk",
        return_value=(False, backup_dialog_ui.GENERIC_REENCRYPT_ERROR),
    ):
        backup_dialog_ui._rollback_journal_copies(
            data_path,
            journal_snap,
            None,
            None,
            fitness_rollbacks=fitness_rollbacks,
            journal_existed=True,
        )

    assert pathlib.Path(data_path).read_bytes() == prior_json
    assert pathlib.Path(db_path).read_bytes() == prior_db
    if fitness_snap and os.path.isfile(fitness_snap):
        os.remove(fitness_snap)


def test_import_failure_restores_pre_restore_journal(temp_app, tmp_path, tk_root, immediate_threads):
    enc = str(tmp_path / "fail-277.enc")
    backup.export_backup(enc, passphrase="twelve-char-pp")
    prior_payload = _minimal_v2_payload()
    prior_payload["entries"]["2000-01-01"] = {
        "Emotional Wellbeing": {"rating": 2, "checklist": {}, "metrics": {}, "notes": "pre-restore"}
    }
    _seed_data_file(prior_payload)
    data_path = paths.data_file()

    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    banner = tracker.ensure_status_banner()
    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))

    with (
        patch("backup_dialog_ui.filedialog.askopenfilename", return_value=enc),
        patch(
            "backup_dialog_ui.backup.import_backup",
            side_effect=OSError("simulated import failure"),
        ),
        patch("backup_dialog_ui.prepare_restore_apply", return_value=True),
    ):
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 20)
        restore_entry = None
        for w in _walk(dialog):
            if not isinstance(w, ttk.Entry):
                continue
            for sib in w.master.winfo_children():
                if isinstance(sib, ttk.Label) and "Restore passphrase" in str(sib.cget("text")):
                    restore_entry = w
                    break
        assert restore_entry is not None
        restore_entry.delete(0, tk.END)
        restore_entry.insert(0, "twelve-char-pp")
        _find_button(dialog, "Continue").invoke()
        pump_tk(tk_root, 15)
        _find_button(dialog, "Restore", exclude="from").invoke()
        pump_tk_until(
            tk_root,
            lambda: GENERIC_RESTORE_ERROR in (banner._message_var.get() or ""),
            timeout_s=3.0,
        )

    with open(data_path, encoding="utf-8") as handle:
        restored = json.load(handle)
    assert (
        restored["entries"]["2000-01-01"]["Emotional Wellbeing"]["notes"] == "pre-restore"
    )
    assert not os.path.isfile(_journal_snapshot_path(data_path))


@pytest.fixture
def capture_restore_threads(monkeypatch):
    import threading

    started: list[threading.Thread] = []

    class _CapturingThread(threading.Thread):
        def start(self) -> None:
            started.append(self)
            super().start()

    monkeypatch.setattr(backup_dialog_ui.threading, "Thread", _CapturingThread)
    return started


def _restore_passphrase_entry(dialog):
    for w in _walk(dialog):
        if not isinstance(w, ttk.Entry):
            continue
        for sib in w.master.winfo_children():
            if isinstance(sib, ttk.Label) and "Restore passphrase" in str(sib.cget("text")):
                return w
    raise AssertionError("restore passphrase entry not found")


def _trigger_wm_delete_window(dialog: tk.Toplevel) -> None:
    name = dialog.tk.call("wm", "protocol", dialog, "WM_DELETE_WINDOW")
    if name:
        dialog.tk.call(name)


def _start_busy_encrypted_restore(
    dialog, tk_root, tmp_path, capture_restore_threads, *, mock_snapshots: bool = True
):
    import threading

    enc = str(tmp_path / "slow-277.enc")
    backup.export_backup(enc, passphrase="twelve-char-pp")
    apply_started = threading.Event()
    release_import = threading.Event()

    def gated_import(*_a, **_k):
        apply_started.set()
        assert release_import.wait(timeout=30)
        raise OSError("stop-after-block-test")

    patches = [
        patch("backup_dialog_ui.filedialog.askopenfilename", return_value=enc),
        patch("backup_dialog_ui.backup.import_backup", side_effect=gated_import),
        patch("backup_dialog_ui.prepare_restore_apply", return_value=True),
    ]
    if mock_snapshots:
        patches.append(
            patch(
                "backup_dialog_ui._restore_snapshots_for_vault",
                return_value=backup_dialog_ui.RestoreSnapshotBundle(
                    journal_snap=None,
                    journal_existed=False,
                    profile_snap=None,
                    profile_existed=False,
                    profile_path=None,
                    fitness_rollbacks=[],
                ),
            )
        )
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 20)
        restore_entry = _restore_passphrase_entry(dialog)
        restore_entry.insert(0, "twelve-char-pp")
        _find_button(dialog, "Continue").invoke()
        pump_tk(tk_root, 10)
        pump_tk_until(
            tk_root,
            lambda: "backup from" in " ".join(_label_texts(dialog)).lower(),
            timeout_s=3.0,
        )
        _find_button(dialog, "Restore", exclude="from").invoke()
        pump_tk_until(tk_root, lambda: apply_started.is_set(), timeout_s=5.0)
    return release_import


def test_close_blocked_during_restore_apply(temp_app, tmp_path, tk_root, capture_restore_threads):
    import threading

    _seed_data_file(_minimal_v2_payload())
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))

    release_import = _start_busy_encrypted_restore(
        dialog,
        tk_root,
        tmp_path,
        capture_restore_threads,
        mock_snapshots=False,
    )

    snap_path = _journal_snapshot_path(paths.data_file())
    assert os.path.isfile(snap_path)

    dialog.event_generate("<Escape>")
    pump_tk(tk_root, 5)
    assert dialog.winfo_exists()

    close_btn = _find_button(dialog, "Close")
    assert str(close_btn.cget("state")) == tk.DISABLED

    release_import.set()
    pump_tk_until(
        tk_root,
        lambda: GENERIC_RESTORE_ERROR in (tracker.ensure_status_banner()._message_var.get() or ""),
        timeout_s=5.0,
    )
    for thread in capture_restore_threads:
        thread.join(timeout=10.0)
    try:
        dialog.destroy()
    except tk.TclError:
        pass
    pump_tk(tk_root, 5)


def test_wm_delete_blocked_during_busy_restore(temp_app, tmp_path, tk_root, capture_restore_threads):
    _seed_data_file(_minimal_v2_payload())
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    release_import = _start_busy_encrypted_restore(
        dialog, tk_root, tmp_path, capture_restore_threads
    )
    _trigger_wm_delete_window(dialog)
    pump_tk(tk_root, 5)
    assert dialog.winfo_exists()
    release_import.set()
    pump_tk_until(
        tk_root,
        lambda: GENERIC_RESTORE_ERROR in (tracker.ensure_status_banner()._message_var.get() or ""),
        timeout_s=5.0,
    )
    for thread in capture_restore_threads:
        thread.join(timeout=10.0)
    try:
        dialog.destroy()
    except tk.TclError:
        pass
    pump_tk(tk_root, 5)


def test_close_when_idle_clears_passphrase_widgets(temp_app, tmp_path, tk_root):
    enc = str(tmp_path / "idle-close-277.enc")
    backup.export_backup(enc, passphrase="twelve-char-pp")
    _seed_data_file(_minimal_v2_payload())
    tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=enc):
        _find_button(dialog, "Restore from").invoke()
        pump_tk(tk_root, 20)
    restore_entry = _restore_passphrase_entry(dialog)
    restore_entry.insert(0, "temporary-secret-value")
    assert restore_entry.get() == "temporary-secret-value"
    _find_button(dialog, "Close").invoke()
    pump_tk(tk_root, 5)
    assert not dialog.winfo_exists()

    backup_dialog_ui.show_backup_dialog(tracker)
    pump_tk(tk_root)
    dialog2 = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
    with patch("backup_dialog_ui.filedialog.askopenfilename", return_value=enc):
        _find_button(dialog2, "Restore from").invoke()
        pump_tk(tk_root, 20)
    restore_entry2 = _restore_passphrase_entry(dialog2)
    assert restore_entry2.get() == ""
    try:
        dialog2.destroy()
    except tk.TclError:
        pass


def test_note_incomplete_rollback_preserves_unreadable_marker(tmp_path, caplog):
    import logging

    container = str(tmp_path)
    marker_path = pathlib.Path(_rollback_pending_marker_path(container))
    corrupt = "{unreadable-marker-bytes"
    marker_path.write_text(corrupt, encoding="utf-8")
    data_path = tmp_path / "data.json"
    data_path.write_text("{}", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="integral"):
        backup_dialog_ui._note_incomplete_rollback(str(data_path))

    assert marker_path.read_text(encoding="utf-8") == corrupt
    assert any(
        backup_dialog_ui._STARTUP_RESTORE_SNAP_DEFERRED_WARNING in record.message
        for record in caplog.records
    )


def test_unreadable_marker_snaps_retained_after_failed_rollback_note(tmp_path, monkeypatch):
    container = str(tmp_path)
    data_path = tmp_path / "data.json"
    live = _minimal_v2_payload()
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(live, handle)
    live_bytes = data_path.read_bytes()
    snap_path = tmp_path / "data.json.pre-restore-snap"
    stale = storage.empty_data()
    stale["entries"]["1999-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": "stale-snap"}
    }
    with open(snap_path, "w", encoding="utf-8") as handle:
        json.dump(stale, handle)
    pathlib.Path(_rollback_pending_marker_path(container)).write_text(
        "{was-listing-data.json", encoding="utf-8"
    )

    prior = storage.empty_data()
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(prior, handle)
    snap = _snapshot_journal_if_present(str(data_path))
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(live, handle)

    _patch_failed_snap_to_live_replace(monkeypatch)
    backup_dialog_ui._rollback_file_from_snapshot(str(data_path), snap, existed_before=True)

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(data_path), container)],
    ):
        sweep_pre_restore_journal_snaps_at_startup()

    assert data_path.read_bytes() == live_bytes
    assert snap_path.is_file()


def test_encrypted_journal_snap_stays_encrypted(temp_app):
    data_path = paths.data_file()
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    save_data_file(
        data_path,
        _minimal_v2_payload(),
        encrypted=True,
        passphrase="twelve-char-pp",
    )
    assert is_encrypted_file(data_path)
    snap = _snapshot_journal_if_present(data_path)
    assert snap and is_encrypted_file(snap)
    if snap and os.path.isfile(snap):
        os.remove(snap)


def test_startup_recovers_missing_live_journal_from_snap(tmp_path, monkeypatch):
    data_file = tmp_path / "data.json"
    snap_file = tmp_path / "data.json.pre-restore-snap"
    good = _minimal_v2_payload()
    good["entries"]["2000-01-01"] = {
        "Emotional Wellbeing": {"rating": 2, "checklist": {}, "metrics": {}, "notes": "from-snap"}
    }
    with open(snap_file, "w", encoding="utf-8") as handle:
        json.dump(good, handle)
    assert not data_file.exists()

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(data_file), str(tmp_path))],
    ):
        sweep_pre_restore_journal_snaps_at_startup()

    assert data_file.is_file()
    with open(data_file, encoding="utf-8") as handle:
        loaded = json.load(handle)
    assert loaded["entries"]["2000-01-01"]["Emotional Wellbeing"]["notes"] == "from-snap"
    assert not snap_file.exists()


def test_startup_recovers_missing_fitness_db_from_snap(tmp_path, monkeypatch):
    data_file = tmp_path / "data.json"
    fitness_file = tmp_path / "fitness.db"
    snap_file = tmp_path / "fitness.db.pre-restore-snap"
    _write_sqlite_stub(snap_file, b"prior-fitness-bytes")
    assert not fitness_file.exists()

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(data_file), str(tmp_path))],
    ):
        sweep_pre_restore_journal_snaps_at_startup()

    assert fitness_file.is_file()
    assert b"prior-fitness-bytes" in fitness_file.read_bytes()
    assert not snap_file.exists()


def test_startup_drops_stale_fitness_snap_when_db_healthy(tmp_path, monkeypatch):
    data_file = tmp_path / "data.json"
    fitness_file = tmp_path / "fitness.db"
    snap_file = tmp_path / "fitness.db.pre-restore-snap"
    _write_sqlite_stub(fitness_file, b"live-db")
    _write_sqlite_stub(snap_file, b"stale-snap")

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(data_file), str(tmp_path))],
    ):
        sweep_pre_restore_journal_snaps_at_startup()

    assert fitness_file.is_file()
    assert b"live-db" in fitness_file.read_bytes()
    assert not snap_file.exists()


def test_pending_marker_keeps_fitness_snap_over_healthy_live(tmp_path, monkeypatch):
    data_file = tmp_path / "data.json"
    fitness_file = tmp_path / "fitness.db"
    snap_file = tmp_path / "fitness.db.pre-restore-snap"
    _write_sqlite_stub(fitness_file, b"live-imported")
    _write_sqlite_stub(snap_file, b"pre-restore-fitness")

    marker_path = _rollback_pending_marker_path(str(tmp_path))
    with open(marker_path, "w", encoding="utf-8") as handle:
        json.dump({"version": 1, "artifacts": ["fitness.db"]}, handle)

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(data_file), str(tmp_path))],
    ):
        sweep_pre_restore_journal_snaps_at_startup()

    assert b"pre-restore-fitness" in fitness_file.read_bytes()
    assert not snap_file.exists()
    assert not os.path.isfile(marker_path)


def test_failed_rollback_records_marker_for_fitness_snap(tmp_path, monkeypatch):
    fitness_file = tmp_path / "fitness.db"
    _write_sqlite_stub(fitness_file, b"before")
    snap = _snapshot_file_if_present(str(fitness_file))
    with open(fitness_file, "wb") as handle:
        handle.write(b"after-import")

    _patch_failed_snap_to_live_replace(monkeypatch)
    ok = backup_dialog_ui._rollback_file_from_snapshot(
        str(fitness_file), snap, existed_before=True
    )
    assert ok is False
    assert snap and os.path.isfile(snap)
    assert _artifact_has_pending_rollback(str(tmp_path), "fitness.db")


def test_startup_drops_leftover_snap_when_live_journal_complete(tmp_path, monkeypatch):
    data_file = tmp_path / "data.json"
    snap_file = tmp_path / "data.json.pre-restore-snap"
    live = _minimal_v2_payload()
    stale = storage.empty_data()
    stale["entries"]["1999-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": "stale-snap"}
    }
    with open(data_file, "w", encoding="utf-8") as handle:
        json.dump(live, handle)
    with open(snap_file, "w", encoding="utf-8") as handle:
        json.dump(stale, handle)

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(data_file), str(tmp_path))],
    ):
        sweep_pre_restore_journal_snaps_at_startup()

    assert data_file.is_file()
    with open(data_file, encoding="utf-8") as handle:
        loaded = json.load(handle)
    assert "1999-01-01" not in loaded.get("entries", {})
    assert not snap_file.exists()


def test_startup_absent_live_corrupt_snap_keeps_snap(tmp_path, monkeypatch, caplog):
    import logging

    data_file = tmp_path / "data.json"
    snap_file = tmp_path / "data.json.pre-restore-snap"
    snap_file.write_text("not-json", encoding="utf-8")
    assert not data_file.exists()

    with (
        patch(
            "vault.iter_journal_sweep_targets",
            return_value=[(str(data_file), str(tmp_path))],
        ),
        caplog.at_level(logging.WARNING, logger="integral"),
    ):
        sweep_pre_restore_journal_snaps_at_startup()

    assert not data_file.exists()
    assert snap_file.is_file()
    assert "data.json" not in caplog.text
    assert str(tmp_path) not in caplog.text


def test_startup_moves_unreadable_live_aside_then_restores_from_snap(tmp_path, monkeypatch):
    data_file = tmp_path / "data.json"
    snap_file = tmp_path / "data.json.pre-restore-snap"
    good = _minimal_v2_payload()
    good["entries"]["2000-01-01"] = {
        "Emotional Wellbeing": {"rating": 2, "checklist": {}, "metrics": {}, "notes": "from-snap"}
    }
    data_file.write_text("{not-a-journal", encoding="utf-8")
    with open(snap_file, "w", encoding="utf-8") as handle:
        json.dump(good, handle)

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(data_file), str(tmp_path))],
    ):
        sweep_pre_restore_journal_snaps_at_startup()

    assert data_file.is_file()
    aside_files = list(tmp_path.glob("data.json.unreadable-*"))
    assert len(aside_files) == 1
    assert aside_files[0].read_text(encoding="utf-8") == "{not-a-journal"
    with open(data_file, encoding="utf-8") as handle:
        loaded = json.load(handle)
    assert loaded["entries"]["2000-01-01"]["Emotional Wellbeing"]["notes"] == "from-snap"
    assert not snap_file.exists()


def test_startup_unreadable_live_bad_snap_restores_original_keeps_snap(tmp_path, monkeypatch, caplog):
    import logging

    data_file = tmp_path / "data.json"
    snap_file = tmp_path / "data.json.pre-restore-snap"
    corrupt_live = "{broken-live"
    data_file.write_text(corrupt_live, encoding="utf-8")
    snap_file.write_text("also-broken", encoding="utf-8")

    with (
        patch(
            "vault.iter_journal_sweep_targets",
            return_value=[(str(data_file), str(tmp_path))],
        ),
        caplog.at_level(logging.WARNING, logger="integral"),
    ):
        sweep_pre_restore_journal_snaps_at_startup()

    assert data_file.read_text(encoding="utf-8") == corrupt_live
    assert snap_file.is_file()
    assert list(tmp_path.glob("data.json.unreadable-*")) == []


def test_startup_transient_live_read_skips_snap_apply(tmp_path, monkeypatch, caplog):
    import logging

    data_file = tmp_path / "data.json"
    snap_file = tmp_path / "data.json.pre-restore-snap"
    live = _minimal_v2_payload()
    with open(data_file, "w", encoding="utf-8") as handle:
        json.dump(live, handle)
    stale = storage.empty_data()
    with open(snap_file, "w", encoding="utf-8") as handle:
        json.dump(stale, handle)

    with (
        patch(
            "vault.iter_journal_sweep_targets",
            return_value=[(str(data_file), str(tmp_path))],
        ),
        patch("vault.confirmed_live_journal_encrypted", return_value=None),
        patch(
            "backup_dialog_ui._startup_live_journal_transient_failure",
            return_value=True,
        ),
        caplog.at_level(logging.WARNING, logger="integral"),
    ):
        sweep_pre_restore_journal_snaps_at_startup()

    with open(data_file, encoding="utf-8") as handle:
        assert json.load(handle) == live
    assert snap_file.is_file()


def test_failed_fitness_snapshot_then_rollback_keeps_live_db(tmp_path, monkeypatch):
    import shutil as shutil_mod

    db_path = tmp_path / "fitness.db"
    _write_sqlite_stub(db_path, b"LIVE-FITNESS-BYTES")
    live_bytes = db_path.read_bytes()

    real_copy2 = shutil_mod.copy2

    def fail_snap_copy(src, dst, *args, **kwargs):
        if str(dst).endswith(".pre-restore-snap"):
            raise OSError("snapshot denied")
        return real_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr(backup_dialog_ui.shutil, "copy2", fail_snap_copy)
    assert _snapshot_file_if_present(str(db_path)) is None
    assert db_path.read_bytes() == live_bytes

    _rollback_journal_copies(
        str(tmp_path / "data.json"),
        None,
        None,
        None,
        fitness_rollbacks=[(str(db_path), None, True)],
    )
    assert db_path.read_bytes() == live_bytes
    assert backup_dialog_ui.RestoreSnapshotBundle(
        journal_snap=None,
        journal_existed=False,
        profile_snap=None,
        profile_existed=False,
        profile_path=None,
        fitness_rollbacks=[(str(db_path), None, True)],
    ).live_snapshot_incomplete()


def test_corrupt_rollback_marker_keeps_snap_live_data_and_blocks_restore(tmp_path):
    data_path = tmp_path / "data.json"
    container = str(tmp_path)
    live = _minimal_v2_payload()
    live["entries"]["2020-01-01"] = {
        "Emotional Wellbeing": {"rating": 3, "checklist": {}, "metrics": {}, "notes": "live-keep"}
    }
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(live, handle)
    live_bytes = data_path.read_bytes()
    snap_path = tmp_path / "data.json.pre-restore-snap"
    stale = storage.empty_data()
    with open(snap_path, "w", encoding="utf-8") as handle:
        json.dump(stale, handle)

    pathlib.Path(_rollback_pending_marker_path(container)).write_text(
        "{corrupt", encoding="utf-8"
    )

    with patch(
        "vault.iter_journal_sweep_targets",
        return_value=[(str(data_path), container)],
    ):
        sweep_pre_restore_journal_snaps_at_startup()
        assert restore_blocked_by_pending_rollback()
        assert _artifact_has_pending_rollback(container, "data.json")

    assert data_path.read_bytes() == live_bytes
    assert snap_path.is_file()