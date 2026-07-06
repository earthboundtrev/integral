import json
import os
import tempfile

import pytest

import profiles
import storage


@pytest.fixture
def temp_app(monkeypatch):
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

        yield {
            "app_dir": app_dir,
            "default_data": os.path.join(default_dir, "data.json"),
        }


def test_create_and_switch_profiles(temp_app):
    alice = profiles.create_profile("Alice")
    bob = profiles.create_profile("Bob")

    assert alice["id"] == "alice"
    assert bob["id"] == "bob"
    assert len(profiles.list_profiles()) == 3

    profiles.set_active_profile("alice")
    assert profiles.get_active_profile()["name"] == "Alice"


def test_profile_data_is_isolated(temp_app):
    profiles.set_active_profile("default")
    default_data = storage.load()
    default_data["entries"]["2026-06-27"] = {
        "Body & Presence": {"rating": 5, "checklist": {}, "metrics": {}, "notes": "default"}
    }
    storage.save(default_data)

    alice = profiles.create_profile("Alice")
    profiles.set_active_profile(alice["id"])
    alice_data = storage.load()
    alice_data["entries"]["2026-06-27"] = {
        "Body & Presence": {"rating": 9, "checklist": {}, "metrics": {}, "notes": "alice"}
    }
    storage.save(alice_data)

    profiles.set_active_profile("default")
    reloaded_default = storage.load()
    profiles.set_active_profile(alice["id"])
    reloaded_alice = storage.load()

    assert reloaded_default["entries"]["2026-06-27"]["Body & Presence"]["rating"] == 5
    assert reloaded_alice["entries"]["2026-06-27"]["Body & Presence"]["rating"] == 9


def test_migrates_legacy_root_data_json(temp_app, monkeypatch):
    app_dir = temp_app["app_dir"]
    legacy_data = os.path.join(app_dir, "data.json")
    with open(legacy_data, "w", encoding="utf-8") as f:
        json.dump({"categories": storage.get_default_categories(), "entries": {"2026-06-01": {}}}, f)

    profiles.migrate_legacy_layout_if_needed()

    migrated_path = os.path.join(app_dir, "profiles", "default", "data.json")
    assert os.path.exists(migrated_path)
    with open(migrated_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "2026-06-01" in data["entries"]
