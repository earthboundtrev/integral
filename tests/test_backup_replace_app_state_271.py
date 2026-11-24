"""Exact replace import for undo restore (#271) — aside moves, no rmtree."""

from __future__ import annotations

import json
import os

import pytest

import backup
import profiles
import storage

from tests.test_backup import temp_app  # noqa: F401


def _write_profile_note(profile_id: str, marker: str) -> None:
    data = storage.load()
    data.setdefault("entries", {})["2099-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": marker}
    }
    path = os.path.join(profiles.get_profile_dir(profile_id), "data.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def test_replace_removes_extra_profile_and_creative_preserves_bak(temp_app, tmp_path, monkeypatch):
    app_dir = temp_app["app_dir"]
    creative_root = os.path.join(app_dir, "creative")
    os.makedirs(creative_root, exist_ok=True)
    monkeypatch.setattr(backup.paths, "creative_projects_dir", lambda: creative_root)

    profiles.set_active_profile("default")
    _write_profile_note("default", "before-restore")
    zip_path = str(tmp_path / "safety-default-only.zip")
    backup.export_backup(zip_path, profile_id="default", creative_root=creative_root)

    profiles.create_profile("extra")
    profiles.set_active_profile("extra")
    _write_profile_note("extra", "extra-profile-live")

    default_dir = profiles.get_profile_dir("default")
    bak_path = os.path.join(default_dir, "data.json.bak")
    with open(bak_path, "w", encoding="utf-8") as handle:
        handle.write('{"bak": true}')
    marker_path = os.path.join(default_dir, "data.json.rolled-back-test")
    with open(marker_path, "w", encoding="utf-8") as handle:
        handle.write("snap")

    unlisted_dir = os.path.join(profiles.get_profiles_root(), "unlisted-off-config")
    os.makedirs(unlisted_dir, exist_ok=True)
    with open(os.path.join(unlisted_dir, "data.json"), "w", encoding="utf-8") as handle:
        handle.write("{}")

    only_live = os.path.join(creative_root, "only-live.txt")
    with open(only_live, "w", encoding="utf-8") as handle:
        handle.write("orphan")

    manifest = backup.import_backup(
        zip_path, merge_profiles=False, replace_app_state=True, creative_root=creative_root
    )
    backup.commit_replace_aside_ledger(manifest[backup.REPLACE_LEDGER_MANIFEST_KEY])
    manifest.pop(backup.REPLACE_LEDGER_MANIFEST_KEY, None)

    config = profiles.load_config()
    ids = {p["id"] for p in config["profiles"]}
    assert ids == {"default"}
    profile_root = profiles.get_profiles_root()
    assert "extra" not in os.listdir(profile_root)
    assert not os.path.isfile(only_live)
    assert os.path.isfile(bak_path)
    assert os.path.isfile(marker_path)
    assert os.path.isdir(unlisted_dir)

    restored = storage.load()
    assert restored["entries"]["2099-01-01"]["Emotional Wellbeing"]["notes"] == "before-restore"


def test_replace_failure_rolls_back_aside_moves(temp_app, tmp_path, monkeypatch):
    creative_root = os.path.join(temp_app["app_dir"], "creative")
    monkeypatch.setattr(backup.paths, "creative_projects_dir", lambda: creative_root)
    profiles.set_active_profile("default")
    _write_profile_note("default", "marker-live")
    zip_path = str(tmp_path / "snap.zip")
    backup.export_backup(zip_path, profile_id="default")

    profiles.create_profile("extra")
    _write_profile_note("extra", "extra-live")
    extra_data = os.path.join(profiles.get_profiles_root(), "extra", "data.json")
    assert os.path.isfile(extra_data)
    live_text = open(extra_data, encoding="utf-8").read()

    original_aside_profiles = backup._aside_config_profile_dirs

    def aside_then_fail(config_ids, backup_ids, ledger):
        original_aside_profiles(config_ids, backup_ids, ledger)
        raise OSError("injected failure")

    monkeypatch.setattr(backup, "_aside_config_profile_dirs", aside_then_fail)

    with pytest.raises(OSError, match="injected"):
        backup.import_backup(
            zip_path,
            merge_profiles=False,
            replace_app_state=True,
            creative_root=creative_root,
        )

    assert os.path.isfile(extra_data)
    assert open(extra_data, encoding="utf-8").read() == live_text
    assert len(profiles.load_config()["profiles"]) >= 2
    parent = os.path.join(profiles.get_app_dir(), backup.BACKUP_REPLACE_ASIDE_DIRNAME)
    if os.path.isdir(parent):
        for run_name in os.listdir(parent):
            aside_profile = os.path.join(parent, run_name, "profiles-removed", "extra")
            assert not os.path.isdir(aside_profile), "extra profile should not remain in aside"


def test_replace_leaves_profile_sidecar_files(temp_app, tmp_path, monkeypatch):
    creative_root = os.path.join(temp_app["app_dir"], "creative")
    monkeypatch.setattr(backup.paths, "creative_projects_dir", lambda: creative_root)
    profiles.set_active_profile("default")
    default_dir = profiles.get_profile_dir("default")
    data_path = os.path.join(default_dir, "data.json")
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump({"entries": {}, "categories": storage.get_default_categories()}, handle)

    zip_path = str(tmp_path / "s.zip")
    backup.export_backup(zip_path, profile_id="default")

    aside_file = os.path.join(default_dir, "data.json.unreadable-abc")
    with open(aside_file, "w", encoding="utf-8") as handle:
        handle.write("aside")
    _write_profile_note("default", "after-export")

    manifest = backup.import_backup(
        zip_path, merge_profiles=False, replace_app_state=True, creative_root=creative_root
    )
    backup.commit_replace_aside_ledger(manifest[backup.REPLACE_LEDGER_MANIFEST_KEY])
    manifest.pop(backup.REPLACE_LEDGER_MANIFEST_KEY, None)
    assert os.path.isfile(aside_file)
    restored = storage.load()
    assert "2099-01-01" not in restored.get("entries", {})