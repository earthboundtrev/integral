"""Restore must not snapshot or write through linked profile folders (#275 security #5)."""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("cryptography")

import backup
import backup_dialog_ui
import personal_dev_tracker
import profile_journal_sync
import profiles
from backup_dialog_ui import GENERIC_RESTORE_ERROR
import paths
import personal_dev_tracker as pdt_mod
from profile_journal_sync import ProfileJournalSyncError
from tests.conftest import pump_tk, pump_tk_until
from tests.test_backup import temp_app  # noqa: F401
from tests.test_backup_dialog_pr275_ui import _find_button, _label_texts, _walk
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file


@pytest.fixture(autouse=True)
def _sync_data_file(monkeypatch):
    monkeypatch.setattr(pdt_mod, "DATA_FILE", paths.data_file())


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
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def _outside_sentinel(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "SENTINEL"
    sentinel.write_text("untouched", encoding="utf-8")
    return outside, sentinel


def _link_default_profile_dir(outside: os.PathLike[str]) -> str:
    profiles_root = profiles.get_profiles_root()
    profile_dir = os.path.join(profiles_root, "default")
    if os.path.lexists(profile_dir):
        if os.path.islink(profile_dir):
            os.unlink(profile_dir)
        elif os.path.isdir(profile_dir):
            for name in list(os.listdir(profile_dir)):
                os.remove(os.path.join(profile_dir, name))
            os.rmdir(profile_dir)
    if sys.platform == "win32":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", profile_dir, str(outside)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            pytest.skip(f"junction creation unsupported: {result.stderr or result.stdout}")
    else:
        os.symlink(str(outside), profile_dir, target_is_directory=True)
    return profile_dir


def _unlink_profile_dir(profile_dir: str) -> None:
    if sys.platform == "win32":
        if os.path.isdir(profile_dir):
            subprocess.run(["cmd", "/c", "rmdir", profile_dir], check=False, capture_output=True)
    elif os.path.islink(profile_dir):
        os.unlink(profile_dir)


def _outside_unchanged(sentinel) -> None:
    assert sentinel.read_text(encoding="utf-8") == "untouched"
    parent = sentinel.parent
    names = sorted(p.name for p in parent.iterdir())
    assert names == ["SENTINEL"]


@pytest.mark.skipif(sys.platform == "win32", reason="Unix symlink variant")
def test_restore_snapshots_abort_linked_profile_symlink(temp_app, tmp_path):
    outside, sentinel = _outside_sentinel(tmp_path)
    profiles.set_active_profile("default")
    profile_dir = _link_default_profile_dir(outside)
    try:
        tracker = MagicMock()
        tracker.data_path = paths.data_file()
        _seed_data_file(_minimal_v2_payload())
        with pytest.raises(ProfileJournalSyncError):
            backup_dialog_ui._restore_snapshots_for_vault(tracker)  # noqa: SLF001
        _outside_unchanged(sentinel)
    finally:
        _unlink_profile_dir(profile_dir)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction variant")
def test_restore_snapshots_abort_linked_profile_junction(temp_app, tmp_path):
    outside, sentinel = _outside_sentinel(tmp_path)
    profiles.set_active_profile("default")
    profile_dir = _link_default_profile_dir(outside)
    try:
        tracker = MagicMock()
        tracker.data_path = paths.data_file()
        _seed_data_file(_minimal_v2_payload())
        with pytest.raises(ProfileJournalSyncError):
            backup_dialog_ui._restore_snapshots_for_vault(tracker)  # noqa: SLF001
        _outside_unchanged(sentinel)
    finally:
        _unlink_profile_dir(profile_dir)


@pytest.mark.skipif(sys.platform == "win32", reason="Unix symlink variant for UI restore")
def test_ui_restore_aborts_linked_profile_before_import(temp_app, tmp_path, tk_root, immediate_threads):
    enc = str(tmp_path / "linked-restore.enc")
    outside, sentinel = _outside_sentinel(tmp_path)
    profiles.set_active_profile("default")
    profile_dir = _link_default_profile_dir(outside)
    try:
        _seed_data_file(_minimal_v2_payload())
        backup.export_backup(enc, passphrase="twelve-char-pp")
        with patch("personal_dev_tracker.prompt_vault_unlock") as unlock:

            def _unlock(tr):
                tr.vault_passphrase = "twelve-char-pp"
                return True

            unlock.side_effect = _unlock
            tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
        tracker.settings["encryption_enabled"] = True
        tracker.vault_passphrase = "twelve-char-pp"
        banner = tracker.ensure_status_banner()

        import_called: list[int] = []

        real_import = backup.import_backup

        def track_import(*args, **kwargs):
            import_called.append(1)
            return real_import(*args, **kwargs)

        backup_dialog_ui.show_backup_dialog(tracker)
        pump_tk(tk_root)
        dialog = next(w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel))
        with (
            patch("backup_dialog_ui.filedialog.askopenfilename", return_value=enc),
            patch("backup_dialog_ui.backup.import_backup", side_effect=track_import),
        ):
            _find_button(dialog, "Restore from").invoke()
            pump_tk(tk_root, 30)
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
            pump_tk(tk_root, 20)
            pump_tk_until(
                tk_root,
                lambda: "backup from" in " ".join(_label_texts(dialog)).lower(),
                timeout_s=3.0,
            )
            _find_button(dialog, "Restore", exclude="from").invoke()
            pump_tk_until(
                tk_root,
                lambda: GENERIC_RESTORE_ERROR in (banner._message_var.get() or ""),
                timeout_s=5.0,
            )

        assert GENERIC_RESTORE_ERROR in banner._message_var.get()
        assert not import_called
        _outside_unchanged(sentinel)
    finally:
        _unlink_profile_dir(profile_dir)
