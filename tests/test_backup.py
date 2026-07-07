import gc
import json
import os
import zipfile

import pytest

import backup
import profiles
import storage
from progression.db import FitnessRepository
from progression.engine import record_performance
from progression.seed_loader import seed_all_fitness


@pytest.fixture
def temp_app(monkeypatch):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        app_dir = os.path.join(tmp, "app")
        profiles_root = os.path.join(app_dir, "profiles")
        default_dir = os.path.join(profiles_root, "default")
        os.makedirs(default_dir, exist_ok=True)

        config = profiles.default_config()
        config_path = os.path.join(app_dir, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f)

        def profile_dir(profile_id=None):
            pid = profile_id or profiles.get_active_profile_id()
            path = os.path.join(profiles_root, pid)
            os.makedirs(path, exist_ok=True)
            return path

        monkeypatch.setattr(profiles, "get_app_dir", lambda: app_dir)
        monkeypatch.setattr(profiles, "get_profiles_root", lambda: profiles_root)
        monkeypatch.setattr(profiles, "get_config_path", lambda: config_path)
        monkeypatch.setattr(profiles, "get_profile_dir", profile_dir)

        try:
            yield {"app_dir": app_dir}
        finally:
            gc.collect()


def test_export_and_import_profile_roundtrip(temp_app, tmp_path):
    profiles.set_active_profile("default")
    data = storage.load()
    data["entries"]["2026-07-05"] = {
        "Body & Presence": {"rating": 8, "checklist": {}, "metrics": {}, "notes": "test backup"}
    }
    storage.save(data)

    db_path = os.path.join(profiles.get_profile_dir("default"), "fitness.db")
    repo = FitnessRepository(db_path)
    seed_all_fitness(repo)
    record_performance(repo, "cc1_push_01", {"sets": 3, "reps": 50}, session_id="s1")
    record_performance(repo, "cc1_push_01", {"sets": 3, "reps": 50}, session_id="s2")
    del repo
    gc.collect()

    zip_path = str(tmp_path / "profile-backup.zip")
    manifest = backup.export_backup(zip_path, profile_id="default")
    assert manifest["profiles"] == ["default"]
    assert "profiles/default/data.json" in manifest["files"]
    assert "profiles/default/fitness.db" in manifest["files"]

    storage.save({"categories": storage.get_default_categories(), "entries": {}})

    backup.import_backup(zip_path, merge_profiles=True)

    restored = storage.load()
    assert restored["entries"]["2026-07-05"]["Body & Presence"]["notes"] == "test backup"

    restored_repo = FitnessRepository(db_path)
    progress = restored_repo.get_user_progress("cc1_push_01")
    assert progress is not None
    assert progress.status == "mastered"
    del restored_repo
    gc.collect()


def test_validate_backup_rejects_missing_data(temp_app, tmp_path):
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(
            backup.MANIFEST_NAME,
            json.dumps({"backup_version": 1, "profiles": ["default"]}),
        )
        zf.writestr("config.json", json.dumps(profiles.load_config()))

    try:
        backup.validate_backup(str(zip_path))
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "data.json" in str(exc)


def test_export_all_profiles_includes_config(temp_app, tmp_path):
    profiles.create_profile("Alice")
    zip_path = str(tmp_path / "full-backup.zip")
    manifest = backup.export_backup(zip_path)
    assert len(manifest["profiles"]) >= 2

    contents = backup.list_backup_contents(zip_path)
    assert "config.json" in contents["files"]
    assert any(name.endswith("data.json") for name in contents["files"])
