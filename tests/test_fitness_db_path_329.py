"""Regression: fitness DB must live with the active profile (#329)."""

from __future__ import annotations

import gc
import json
import os
import tempfile

import profiles
import pytest
from progression.db import FITNESS_DB_NAME, FitnessRepository, get_fitness_db_path


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
        try:
            yield {"app_dir": app_dir}
        finally:
            gc.collect()


def test_get_fitness_db_path_uses_active_profile_dir(temp_app):
    expected = os.path.join(profiles.get_profile_dir("default"), FITNESS_DB_NAME)
    assert get_fitness_db_path() == expected


def test_workout_save_visible_via_default_repo_after_profile_migration(temp_app):
    """Simulate legacy root DB + migrated profile copy — app must write the profile DB."""
    app_dir = temp_app["app_dir"]
    legacy = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_db = get_fitness_db_path()

    # Legacy root + empty profile: migration copies on ensure_app_structure (already ran).
    open(legacy, "wb").close()
    profiles.migrate_legacy_layout_if_needed()
    assert os.path.isfile(profile_db)

    repo = FitnessRepository()
    assert os.path.normcase(repo.db_path) == os.path.normcase(profile_db)
    repo.initialize()
    ex_id = "cc1_push_01"
    from progression.models import Exercise

    if not repo.get_exercise(ex_id):
        repo.add_exercise(
            Exercise(
                id=ex_id,
                name="Wall Pushup",
                source_book="CC1",
                family="push",
                mastery_criteria={"sets": 1, "reps": 1},
            )
        )
    from progression.sessions import create_workout_session

    create_workout_session(
        repo,
        "2026-11-24",
        [{"exercise_id": ex_id, "sets": 1, "reps": 5}],
    )
    with repo.connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM workout_sessions").fetchone()[0]
    assert count == 1
    del repo
    gc.collect()