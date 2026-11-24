"""Deferred saves during restore — discard on success, replay on rollback (#271)."""

from __future__ import annotations

import json
import os
import threading

import pytest

import backup
import backup_dialog_ui
import paths
import profiles
import storage

from tests.conftest import create_tk_root, pump_tk_until
from tests.test_backup import temp_app  # noqa: F401
from tests.test_backup_replace_ledger_271 import _seed_replace_scenario, _tree_digest


def test_flush_save_during_restore_queues_without_error(tracker_with_data):
    tracker = tracker_with_data
    tracker.entries["2099-01-01"] = {
        "Emotional Wellbeing": {"rating": 7, "checklist": {}, "metrics": {}, "notes": "q"}
    }
    tracker._pending_save_payload = tracker._payload()
    tracker._save_after_callbacks = []
    backup_dialog_ui.begin_restore_operation(tracker)
    try:
        tracker._flush_save(sync=False)
        assert tracker._restore_deferred_saves
        assert tracker._pending_save_payload is None
    finally:
        backup_dialog_ui.end_restore_operation(replay_queued_saves=True)


@pytest.fixture
def tracker_with_data(tk_root, temp_app, monkeypatch):
    from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file
    import personal_dev_tracker as pdt_mod

    _seed_data_file(_minimal_v2_payload())
    monkeypatch.setattr(pdt_mod, "DATA_FILE", paths.data_file())
    return pdt_mod.PersonalDevelopmentTracker(tk_root)


@pytest.fixture
def tk_root():
    root = create_tk_root(withdraw=True)
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_undo_success_discards_queued_saves(temp_app, tmp_path, monkeypatch, tk_root):
    from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file
    import personal_dev_tracker as pdt_mod
    from backup_dialog_ui import RestoreSnapshotBundle

    app_dir, zip_path, creative_root = _seed_replace_scenario(temp_app, tmp_path, monkeypatch)
    _seed_data_file(_minimal_v2_payload())
    data_path = paths.data_file()
    monkeypatch.setattr(pdt_mod, "DATA_FILE", data_path)
    tracker = pdt_mod.PersonalDevelopmentTracker(tk_root)
    tracker.data_path = data_path

    manifest = backup.import_backup(
        zip_path,
        merge_profiles=False,
        replace_app_state=True,
        creative_root=creative_root,
    )
    backup.commit_replace_aside_ledger(manifest[backup.REPLACE_LEDGER_MANIFEST_KEY])
    restored_text = open(data_path, encoding="utf-8").read()

    backup_dialog_ui.begin_restore_operation(tracker)
    tracker.entries["2099-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": "undo-stale"}
    }
    tracker.save_data(flush=True)
    empty = RestoreSnapshotBundle(
        journal_snap=None,
        journal_existed=False,
        profile_snap=None,
        profile_existed=False,
        profile_path=None,
        fitness_rollbacks=[],
    )
    backup_dialog_ui._complete_undo_restore_ui(tracker, empty, "/tmp/unused.zip")
    backup_dialog_ui.end_restore_operation(replay_queued_saves=False)
    assert "undo-stale" not in open(data_path, encoding="utf-8").read()
    assert open(data_path, encoding="utf-8").read() == restored_text


def test_restore_success_discards_queued_saves(temp_app, tmp_path, monkeypatch, tk_root):
    from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file
    import personal_dev_tracker as pdt_mod

    app_dir, zip_path, creative_root = _seed_replace_scenario(temp_app, tmp_path, monkeypatch)
    _seed_data_file(_minimal_v2_payload())
    data_path = paths.data_file()
    monkeypatch.setattr(pdt_mod, "DATA_FILE", data_path)
    tracker = pdt_mod.PersonalDevelopmentTracker(tk_root)
    tracker.data_path = data_path

    manifest = backup.import_backup(
        zip_path,
        merge_profiles=False,
        replace_app_state=True,
        creative_root=creative_root,
    )
    backup.commit_replace_aside_ledger(manifest[backup.REPLACE_LEDGER_MANIFEST_KEY])
    restored_marker = open(data_path, encoding="utf-8").read()

    backup_dialog_ui.begin_restore_operation(tracker)
    tracker.entries.clear()
    tracker.entries["2099-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": "stale-queued"}
    }
    done = threading.Event()
    ok_flags: list[bool] = []

    def on_complete(ok: bool, _err) -> None:
        ok_flags.append(ok)
        done.set()

    tracker.save_data(flush=True, on_complete=on_complete)
    tracker.discard_deferred_saves_after_restore()
    backup_dialog_ui.end_restore_operation(replay_queued_saves=False)
    tracker.load_data()

    assert done.is_set()
    assert ok_flags == [False]
    assert "stale-queued" not in open(data_path, encoding="utf-8").read()
    assert open(data_path, encoding="utf-8").read() == restored_marker


def test_restore_rollback_replays_queued_save(temp_app, tmp_path, monkeypatch, tk_root):
    from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file
    import personal_dev_tracker as pdt_mod

    _seed_data_file(_minimal_v2_payload())
    data_path = paths.data_file()
    monkeypatch.setattr(pdt_mod, "DATA_FILE", data_path)
    tracker = pdt_mod.PersonalDevelopmentTracker(tk_root)
    tracker.data_path = data_path
    before = open(data_path, encoding="utf-8").read()

    backup_dialog_ui.begin_restore_operation(tracker)
    tracker.entries["2099-01-01"] = {
        "Emotional Wellbeing": {"rating": 5, "checklist": {}, "metrics": {}, "notes": "replay-me"}
    }
    tracker.save_data(flush=True)
    backup_dialog_ui.end_restore_operation(replay_queued_saves=True)
    assert tracker.wait_for_save_idle(timeout_s=2.0)
    assert "replay-me" in open(data_path, encoding="utf-8").read()


def test_config_crash_after_aside_recovered_on_startup(temp_app, tmp_path, monkeypatch):
    app_dir, zip_path, creative_root = _seed_replace_scenario(temp_app, tmp_path, monkeypatch)
    before_cfg = profiles.load_config()
    before = _tree_digest(app_dir)
    backup._REPLACE_TEST_HOOK = "after-config-aside"
    with pytest.raises(OSError, match="replace-test-hook"):
        backup.import_backup(
            zip_path,
            merge_profiles=False,
            replace_app_state=True,
            creative_root=creative_root,
        )
    config_path = profiles.get_config_path()
    parent = os.path.dirname(config_path)
    temps = [
        os.path.join(parent, name)
        for name in os.listdir(parent)
        if name.startswith("config.json.import-")
    ]
    profiles.ensure_app_structure()
    backup.sweep_replace_aside_pending_at_startup()
    assert profiles.load_config() == before_cfg
    assert _tree_digest(app_dir) == before
    for temp in temps:
        assert not os.path.lexists(temp)


def test_sweep_removes_finished_aside_run_dir(temp_app, tmp_path, monkeypatch):
    app_dir, zip_path, creative_root = _seed_replace_scenario(temp_app, tmp_path, monkeypatch)
    manifest = backup.import_backup(
        zip_path,
        merge_profiles=False,
        replace_app_state=True,
        creative_root=creative_root,
    )
    ledger = manifest[backup.REPLACE_LEDGER_MANIFEST_KEY]
    ledger._mark_finished(backup.REPLACE_LEDGER_STATUS_COMMITTED)
    assert os.path.isdir(ledger.root)
    backup.sweep_replace_aside_pending_at_startup()
    assert not os.path.isdir(ledger.root)