"""Regression #337: safe legacy fitness.db overwrite when profile db is genuinely empty."""

from __future__ import annotations

import gc
import json
import os
import sqlite3
import tempfile
from unittest.mock import patch

import profiles
import pytest
from progression.db import FITNESS_DB_NAME, FitnessRepository
from progression.models import Exercise
from progression.sessions import create_workout_session


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


def _empty_profile_db(profile_path: str) -> None:
    empty_repo = FitnessRepository(db_path=profile_path)
    empty_repo.initialize()
    del empty_repo
    gc.collect()


def test_session_count_error_skips_overwrite(temp_app, short_busy_timeout, monkeypatch):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    _empty_profile_db(profile_path)
    live_mtime_before = os.path.getmtime(profile_path)

    real_result = profiles._workout_session_count_result

    def flaky_result(db_path: str):
        if os.path.normpath(db_path) == os.path.normpath(profile_path):
            return profiles.WorkoutSessionCountResult(profiles.SessionCountOutcome.UNREADABLE, 0)
        return real_result(db_path)

    monkeypatch.setattr(profiles, "_workout_session_count_result", flaky_result)

    profiles.migrate_legacy_layout_if_needed()

    assert os.path.isfile(profile_path)
    assert os.path.getmtime(profile_path) == live_mtime_before
    assert profiles._workout_session_count(profile_path) == 0


def test_genuine_empty_profile_still_restores_from_legacy(temp_app, short_busy_timeout):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    _empty_profile_db(profile_path)

    profiles.migrate_legacy_layout_if_needed()

    assert profiles._workout_session_count(profile_path) == 1
    with sqlite3.connect(profile_path) as conn:
        row = conn.execute(
            "SELECT date FROM workout_sessions WHERE date = ?", ("2026-10-01",)
        ).fetchone()
    assert row is not None


def test_journal_sidecar_removed_before_db_reopen(temp_app):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)
    journal_path = f"{profile_path}-journal"

    _seed_session(legacy_path, "2026-10-01")
    _empty_profile_db(profile_path)
    with open(journal_path, "wb") as handle:
        handle.write(b"stale-journal-marker")

    sidecars_cleared: list[bool] = []
    live_present: list[bool] = []

    original_remove = profiles._remove_writable_fitness_sidecars

    def spy_remove(db_path: str) -> None:
        live_present.append(os.path.isfile(db_path))
        original_remove(db_path)
        sidecars_cleared.append(not os.path.exists(journal_path))

    with patch.object(profiles, "_remove_writable_fitness_sidecars", spy_remove):
        assert profiles._replace_empty_profile_fitness_from_legacy(profile_path, legacy_path)

    assert live_present and live_present[0]
    assert sidecars_cleared and sidecars_cleared[0]
    assert not os.path.exists(journal_path)
    profiles._workout_session_count(profile_path)


def test_replace_keeps_live_db_until_os_replace(temp_app):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    _empty_profile_db(profile_path)
    live_bytes = open(profile_path, "rb").read()

    live_at_swap: list[bool] = []

    real_replace = os.replace

    def spy_replace(src: str, dst: str) -> None:
        if os.path.normpath(dst) == os.path.normpath(profile_path):
            live_at_swap.append(os.path.isfile(dst) and open(dst, "rb").read() == live_bytes)
        real_replace(src, dst)

    with patch.object(profiles.os, "replace", spy_replace):
        assert profiles._replace_empty_profile_fitness_from_legacy(profile_path, legacy_path)

    assert live_at_swap and live_at_swap[0]


def test_merge_failure_skips_overwrite(temp_app, short_busy_timeout, monkeypatch):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    _empty_profile_db(profile_path)
    before = open(profile_path, "rb").read()

    monkeypatch.setattr(
        profiles,
        "_merge_legacy_fitness_db_into_profile",
        lambda *_a, **_k: False,
    )

    profiles.migrate_legacy_layout_if_needed()

    assert open(profile_path, "rb").read() == before
    assert profiles._workout_session_count(profile_path) == 0


def test_earlier_pre_legacy_bak_rotated_to_unique_name(temp_app, short_busy_timeout, monkeypatch):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)
    fixed_bak = f"{profile_path}.pre-legacy-restore.bak"

    _seed_session(legacy_path, "2026-10-01")
    _empty_profile_db(profile_path)
    with open(fixed_bak, "wb") as handle:
        handle.write(b"previous-backup-payload")

    monkeypatch.setattr(
        profiles, "_merge_legacy_fitness_db_into_profile", lambda *_a, **_k: True
    )

    profiles.migrate_legacy_layout_if_needed()

    rotated = f"{fixed_bak}.1"
    assert os.path.isfile(rotated)
    with open(rotated, "rb") as handle:
        assert handle.read() == b"previous-backup-payload"
    assert os.path.isfile(fixed_bak)
    assert open(fixed_bak, "rb").read() != b"previous-backup-payload"


def test_incoming_copy_failure_leaves_live_db_and_backup(temp_app, short_busy_timeout, monkeypatch):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    _empty_profile_db(profile_path)
    live_bytes_before = open(profile_path, "rb").read()

    monkeypatch.setattr(
        profiles, "_merge_legacy_fitness_db_into_profile", lambda *_a, **_k: True
    )

    import integral_io

    real_copy = integral_io.atomic_copy_file

    def flaky_copy(src: str, dest: str) -> None:
        if dest.endswith(".legacy-restore-incoming.tmp"):
            raise OSError("copy blocked")
        real_copy(src, dest)

    monkeypatch.setattr(integral_io, "atomic_copy_file", flaky_copy)

    profiles.migrate_legacy_layout_if_needed()

    assert os.path.isfile(profile_path)
    assert open(profile_path, "rb").read() == live_bytes_before
    bak_dir = default_dir
    bak_files = [
        name
        for name in os.listdir(bak_dir)
        if name.startswith(f"{FITNESS_DB_NAME}.pre-legacy-restore")
    ]
    assert bak_files
    assert any(os.path.getsize(os.path.join(bak_dir, name)) > 0 for name in bak_files)


def test_merge_returns_false_when_profile_db_busy(temp_app, short_busy_timeout):
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(temp_app["app_dir"], FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    _empty_profile_db(profile_path)

    holder = sqlite3.connect(profile_path)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        assert profiles._merge_legacy_fitness_db_into_profile(legacy_path, profile_path) is False
    finally:
        holder.close()
        gc.collect()

    assert profiles._workout_session_count(profile_path) == 0