"""Regression #336: legacy layout must not raise when profile fitness.db is locked or unreadable."""

from __future__ import annotations

import gc
import hashlib
import json
import os
import sqlite3
import tempfile

import profiles
import pytest
from progression.db import FITNESS_DB_NAME, FitnessRepository
from progression.sessions import create_workout_session
from progression.models import Exercise


@pytest.fixture(autouse=True)
def reset_legacy_fitness_notices():
    profiles.consume_legacy_fitness_notices()
    yield
    profiles.consume_legacy_fitness_notices()


@pytest.fixture
def short_busy_timeout(monkeypatch):
    monkeypatch.setenv("INTEGRAL_FITNESS_BUSY_TIMEOUT_MS", "50")
    yield


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
            pid = profile_id or profiles.DEFAULT_PROFILE_ID
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


def _file_digest(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def test_locked_profile_db_does_not_raise_from_ensure_app_structure(
    temp_app, short_busy_timeout
):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    _seed_session(profile_path, "2026-11-01")
    before = _file_digest(profile_path)

    holder = sqlite3.connect(profile_path)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        profiles.ensure_app_structure()
        profiles.migrate_legacy_layout_if_needed()
    finally:
        holder.close()
        gc.collect()

    assert os.path.isfile(profile_path)
    assert _file_digest(profile_path) == before
    assert profiles.consume_legacy_fitness_notices() == []


def test_unreadable_profile_db_queues_notice_without_raising(temp_app, short_busy_timeout):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    with open(profile_path, "wb") as handle:
        handle.write(b"NOT-A-SQLITE-FILE-336")

    before = _file_digest(profile_path)
    profiles.ensure_app_structure()
    profiles.migrate_legacy_layout_if_needed()

    assert os.path.isfile(profile_path)
    assert _file_digest(profile_path) == before
    notices = profiles.consume_legacy_fitness_notices()
    assert notices == [profiles.GENERIC_LEGACY_FITNESS_NOTICE]
    assert "NOT-A-SQLITE" not in notices[0]
    assert "fitness" not in notices[0].lower()


def test_load_config_survives_locked_profile_db(temp_app, short_busy_timeout):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    _seed_session(profile_path, "2026-11-01")

    holder = sqlite3.connect(profile_path)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        config = profiles.load_config()
        assert config["active_profile_id"] == profiles.DEFAULT_PROFILE_ID
    finally:
        holder.close()
        gc.collect()

    assert profiles.consume_legacy_fitness_notices() == []


def test_locked_profile_still_merges_after_lock_released(temp_app, short_busy_timeout):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    empty_repo = FitnessRepository(db_path=profile_path)
    empty_repo.initialize()
    del empty_repo
    gc.collect()

    holder = sqlite3.connect(profile_path)
    holder.execute("BEGIN EXCLUSIVE")
    profiles.migrate_legacy_layout_if_needed()
    holder.close()
    gc.collect()

    profiles.migrate_legacy_layout_if_needed()
    assert profiles._workout_session_count(profile_path) == 1


def test_count_result_distinguishes_lock_from_genuine_zero(temp_app, short_busy_timeout):
    default_dir = temp_app["default_dir"]
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)
    _seed_session(profile_path, "2026-10-01")

    holder = sqlite3.connect(profile_path)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        result = profiles._workout_session_count_result(profile_path)
        assert result.outcome == profiles.SessionCountOutcome.LOCKED
        assert not result.is_genuine_zero
    finally:
        holder.close()
        gc.collect()

    ok = profiles._workout_session_count_result(profile_path)
    assert ok.outcome == profiles.SessionCountOutcome.OK
    assert ok.has_sessions


def test_unreadable_count_does_not_take_overwrite_path(temp_app, short_busy_timeout):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    with open(profile_path, "wb") as handle:
        handle.write(b"GARBAGE-BYTES")

    profiles.migrate_legacy_layout_if_needed()
    assert _file_digest(profile_path) == hashlib.sha256(b"GARBAGE-BYTES").hexdigest()