"""Restore must reload tracker journal from profile path after import."""

from __future__ import annotations

import json
import os
import tkinter as tk
from unittest.mock import patch

import pytest

pytest.importorskip("cryptography")

import backup
import paths
import personal_dev_tracker
import profile_journal_sync
import profiles
import storage
from tests.test_backup import temp_app  # noqa: F401
from tests.test_data_payload_registry_177 import _minimal_v2_payload, _seed_data_file


@pytest.fixture(autouse=True)
def _sync_data_file(monkeypatch):
    monkeypatch.setattr(personal_dev_tracker, "DATA_FILE", paths.data_file())


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def test_export_includes_tracker_journal_after_sync(temp_app, tmp_path):
    profiles.set_active_profile("default")
    tracker_path = paths.data_file()
    marker = storage.empty_data()
    marker["entries"]["2099-06-01"] = {
        "Emotional Wellbeing": {"rating": 8, "checklist": {}, "metrics": {}, "notes": "export-me"}
    }
    os.makedirs(os.path.dirname(tracker_path), exist_ok=True)
    with open(tracker_path, "w", encoding="utf-8") as handle:
        json.dump(marker, handle)
    profile_journal_sync.sync_tracker_journal_to_active_profile(tracker_path)
    enc = str(tmp_path / "m.enc")
    out = backup.export_backup(enc, passphrase="twelve-char-pp")
    assert out.get("encrypted") is True
    with backup._backup_zipfile(enc, passphrase="twelve-char-pp") as zf:  # noqa: SLF001
        import zip_import_safety

        budget = zip_import_safety.prepare_zip_import(zf)
        raw = zip_import_safety.read_zip_member_bytes(
            zf, "profiles/default/data.json", budget
        ).decode("utf-8")
    payload = json.loads(raw)
    assert payload["entries"]["2099-06-01"]["Emotional Wellbeing"]["notes"] == "export-me"


def test_restore_sync_updates_tracker_entries(tk_root, temp_app, tmp_path):
    import os

    profiles.set_active_profile("default")
    data = storage.empty_data()
    data["entries"]["2099-07-01"] = {
        "Emotional Wellbeing": {"rating": 9, "checklist": {}, "metrics": {}, "notes": "restore-me"}
    }
    storage.save(data)
    enc = str(tmp_path / "r.enc")
    backup.export_backup(enc, passphrase="twelve-char-pp")
    storage.save(storage.empty_data())

    _seed_data_file(_minimal_v2_payload())
    with patch("personal_dev_tracker.prompt_vault_unlock", return_value=True):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(tk_root)
    assert "2099-07-01" not in tracker.entries

    backup.import_backup(enc, merge_profiles=True, passphrase="twelve-char-pp")
    profile_journal_sync.sync_active_profile_journal_to_tracker(tracker.data_path)
    tracker.load_data()
    assert tracker.entries.get("2099-07-01", {}).get("Emotional Wellbeing", {}).get("notes") == "restore-me"
