"""Regression #332: restore workout history when profile fitness.db is empty but legacy root has sessions."""

from __future__ import annotations

import gc
import json
import os
import sqlite3
import tempfile

import profiles
import pytest
from progression.db import FITNESS_DB_NAME, FitnessRepository
from progression.models import Exercise
from progression.sessions import create_workout_session


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
            yield {"app_dir": app_dir, "default_dir": default_dir}
        finally:
            gc.collect()


def _seed_session(db_path: str, session_date: str) -> None:
    repo = FitnessRepository(db_path=db_path)
    repo.initialize()
    ex_id = "cc1_push_01"
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
    create_workout_session(
        repo,
        session_date,
        [{"exercise_id": ex_id, "sets": 1, "reps": 5}],
    )
    del repo
    gc.collect()


def test_empty_profile_db_restored_from_legacy_root(temp_app):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    # Simulate #329: empty profile DB created by initialize() while legacy file still has data.
    empty_repo = FitnessRepository(db_path=profile_path)
    empty_repo.initialize()
    del empty_repo
    gc.collect()

    assert profiles._workout_session_count(legacy_path) == 1
    assert profiles._workout_session_count(profile_path) == 0

    gc.collect()
    profiles.migrate_legacy_layout_if_needed()

    assert profiles._workout_session_count(profile_path) == 1
    with sqlite3.connect(profile_path) as conn:
        row = conn.execute(
            "SELECT date FROM workout_sessions WHERE date = ?", ("2026-10-01",)
        ).fetchone()
    assert row is not None


def test_merge_keeps_profile_sessions_and_adds_legacy(temp_app):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    _seed_session(legacy_path, "2026-10-02")
    _seed_session(profile_path, "2026-11-01")

    profiles.migrate_legacy_layout_if_needed()

    assert profiles._workout_session_count(profile_path) == 3
    with sqlite3.connect(profile_path) as conn:
        dates = {
            row[0]
            for row in conn.execute("SELECT date FROM workout_sessions").fetchall()
        }
    assert dates == {"2026-10-01", "2026-10-02", "2026-11-01"}