"""Undo failure schedules UI rollback after ledger rollback (#271)."""

from __future__ import annotations

import os
import threading

import pytest

import backup
import backup_dialog_ui
import paths

from tests.conftest import create_tk_root, pump_tk_until
from tests.test_backup import temp_app  # noqa: F401
from tests.test_backup_replace_ledger_271 import _seed_replace_scenario


@pytest.fixture
def tk_root():
    root = create_tk_root(withdraw=True)
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_load_data_runs_only_after_data_json_exists_on_undo_failure(
    tk_root, temp_app, tmp_path, monkeypatch,
):
    _seed_replace_scenario(temp_app, tmp_path, monkeypatch)
    data_path = paths.data_file()
    safety_zip = str(tmp_path / "safety.zip")
    creative_root = os.path.join(temp_app["app_dir"], "creative")
    backup.export_backup(safety_zip, profile_id="default", creative_root=creative_root)

    import personal_dev_tracker as pdt_mod

    monkeypatch.setattr(pdt_mod, "DATA_FILE", data_path)
    tracker = pdt_mod.PersonalDevelopmentTracker(tk_root)

    rollback_started = threading.Event()
    rollback_done = threading.Event()
    load_while_rollback_missing: list[bool] = []
    real_rollback = backup.ReplaceAsideLedger.rollback

    def rollback_tracked(self: backup.ReplaceAsideLedger) -> bool:
        rollback_started.set()
        try:
            return real_rollback(self)
        finally:
            rollback_done.set()

    monkeypatch.setattr(backup.ReplaceAsideLedger, "rollback", rollback_tracked)

    real_load = tracker.load_data

    def load_data_tracked() -> None:
        if rollback_started.is_set() and not rollback_done.is_set():
            load_while_rollback_missing.append(os.path.isfile(data_path))
        real_load()

    tracker.load_data = load_data_tracked  # type: ignore[method-assign]

    real_import = backup.import_backup

    def import_fail(*args, **kwargs):
        real_import(*args, **kwargs)
        raise RuntimeError("post-import check failed")

    monkeypatch.setattr(backup, "import_backup", import_fail)
    monkeypatch.setattr(
        backup_dialog_ui.profile_journal_sync,
        "sync_active_profile_journal_to_tracker",
        lambda _p: None,
    )
    monkeypatch.setattr(
        backup_dialog_ui,
        "reencrypt_restored_journal_from_disk",
        lambda _t: (False, "fail"),
    )

    backup_dialog_ui.apply_undo_from_safety_backup(tracker, safety_zip)
    assert pump_tk_until(tk_root, lambda: rollback_done.is_set(), timeout_s=3.0)
    assert not any(not exists for exists in load_while_rollback_missing)


def test_deferred_save_flushes_after_restore_operation(temp_app, tmp_path, monkeypatch):
    from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file
    import personal_dev_tracker as pdt_mod

    _seed_data_file(_minimal_v2_payload())
    data_path = paths.data_file()
    monkeypatch.setattr(pdt_mod, "DATA_FILE", data_path)
    root = create_tk_root(withdraw=True)
    try:
        tracker = pdt_mod.PersonalDevelopmentTracker(root)
        tracker.data_path = data_path
        before_busy = open(data_path, encoding="utf-8").read()
        backup_dialog_ui.begin_restore_operation(tracker)
        tracker.entries["2099-01-01"] = {
            "Emotional Wellbeing": {"rating": 8, "checklist": {}, "metrics": {}, "notes": "deferred"}
        }
        done = threading.Event()
        tracker.save_data(flush=True, on_complete=lambda _ok, _err: done.set())
        assert open(data_path, encoding="utf-8").read() == before_busy
        backup_dialog_ui.end_restore_operation()
        assert tracker.wait_for_save_idle(timeout_s=2.0)
        assert done.is_set()
        assert not tracker._restore_deferred_saves
    finally:
        root.destroy()