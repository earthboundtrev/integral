"""Regression #335: legacy root fitness.db import runs once then retires."""

from __future__ import annotations

import gc
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from unittest.mock import patch

import profiles
import pytest
from integral_io import atomic_copy_file
from progression.db import FITNESS_DB_NAME, FitnessRepository
from progression.models import Exercise
from progression.sessions import create_workout_session

import paths


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
        monkeypatch.setattr(
            profiles,
            "get_active_profile_id",
            lambda: profiles.DEFAULT_PROFILE_ID,
        )
        try:
            yield {"app_dir": app_dir, "default_dir": default_dir, "config_path": config_path}
        finally:
            gc.collect()


def _seed_session(db_path: str, session_date: str, *, session_id: str | None = None) -> str:
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
    session = create_workout_session(
        repo,
        session_date,
        [{"exercise_id": ex_id, "sets": 1, "reps": 5}],
    )
    sid = session_id or session.id
    del repo
    gc.collect()
    return sid


def _list_retired_roots(app_dir: str) -> list[str]:
    return sorted(
        name
        for name in os.listdir(app_dir)
        if name.startswith("fitness.db.retired-") and not name.endswith(("-wal", "-shm", "-journal"))
    )


def test_first_copy_retires_root_and_sidecars(temp_app):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    open(f"{legacy_path}-wal", "wb").close()
    open(f"{legacy_path}-shm", "wb").close()

    profiles.migrate_legacy_layout_if_needed()

    assert not os.path.exists(legacy_path)
    assert _list_retired_roots(app_dir)
    assert os.path.exists(profile_path)
    assert profiles._workout_session_count(profile_path) == 1


def test_retired_root_skips_second_merge(temp_app):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    _seed_session(legacy_path, "2026-10-02")
    profiles.migrate_legacy_layout_if_needed()
    assert not os.path.exists(legacy_path)

    with sqlite3.connect(profile_path) as conn:
        conn.execute("DELETE FROM workout_sessions")
        conn.commit()

    merge_calls: list[tuple[str, str]] = []

    def _track_merge(legacy: str, profile: str) -> bool:
        merge_calls.append((legacy, profile))
        return profiles._merge_legacy_fitness_db_into_profile(legacy, profile)

    with patch.object(profiles, "_merge_legacy_fitness_db_into_profile", side_effect=_track_merge):
        profiles.migrate_legacy_layout_if_needed()

    assert merge_calls == []
    assert profiles._workout_session_count(profile_path) == 0


def test_merge_failure_skips_empty_profile_overwrite(temp_app):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    FitnessRepository(db_path=profile_path).initialize()

    with patch.object(
        profiles,
        "_merge_legacy_fitness_db_into_profile",
        return_value=False,
    ):
        profiles.migrate_legacy_layout_if_needed()

    assert os.path.exists(legacy_path)
    assert profiles._workout_session_count(profile_path) == 0


def test_failed_merge_does_not_retire_root(temp_app):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    _seed_session(profile_path, "2026-11-01")

    with patch.object(
        profiles,
        "_merge_legacy_fitness_db_into_profile",
        return_value=False,
    ):
        profiles.migrate_legacy_layout_if_needed()

    assert os.path.exists(legacy_path)
    assert profiles._workout_session_count(profile_path) == 1


def test_failed_rename_retries_and_keeps_root_until_success(temp_app, monkeypatch):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    _seed_session(profile_path, "2026-11-01")

    original_replace = os.replace
    attempts = {"count": 0}

    def flaky_replace(src, dest):
        if src == legacy_path and attempts["count"] == 0:
            attempts["count"] += 1
            raise OSError("simulated lock")
        return original_replace(src, dest)

    monkeypatch.setattr(os, "replace", flaky_replace)
    profiles.migrate_legacy_layout_if_needed()
    assert os.path.exists(legacy_path)

    monkeypatch.setattr(os, "replace", original_replace)
    profiles.migrate_legacy_layout_if_needed()
    assert not os.path.exists(legacy_path)
    assert profiles._workout_session_count(profile_path) == 2


def test_deleted_sessions_stay_gone_after_subprocess_restart(temp_app):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    _seed_session(legacy_path, "2026-10-02")
    profiles.migrate_legacy_layout_if_needed()

    with sqlite3.connect(profile_path) as conn:
        conn.execute("DELETE FROM workout_sessions")
        conn.commit()

    script = (
        "import os, sqlite3\n"
        f"os.environ[{paths.INTEGRAL_DATA_DIR_ENV!r}] = {app_dir!r}\n"
        "import profiles\n"
        "profiles.migrate_legacy_layout_if_needed()\n"
        "import sqlite3\n"
        f"conn = sqlite3.connect({profile_path!r})\n"
        "count = conn.execute('SELECT COUNT(*) FROM workout_sessions').fetchone()[0]\n"
        "conn.close()\n"
        "raise SystemExit(0 if count == 0 else 1)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_replaced_profile_db_not_remerged_from_root(temp_app):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    profiles.migrate_legacy_layout_if_needed()
    assert not os.path.exists(legacy_path)

    replacement_path = os.path.join(default_dir, "replacement-fitness.db")
    _seed_session(replacement_path, "2019-01-01")
    atomic_copy_file(replacement_path, profile_path)

    profiles.migrate_legacy_layout_if_needed()
    with sqlite3.connect(profile_path) as conn:
        dates = {
            row[0] for row in conn.execute("SELECT date FROM workout_sessions").fetchall()
        }
    assert dates == {"2019-01-01"}


def test_second_pass_does_not_merge_write(temp_app):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    profiles.migrate_legacy_layout_if_needed()

    merge_writes: list[str] = []

    original_connect = sqlite3.connect

    def tracking_connect(database, *args, **kwargs):
        conn = original_connect(database, *args, **kwargs)
        if os.path.normcase(str(database)) == os.path.normcase(profile_path):

            class WriterConn:
                def __init__(self, inner):
                    self._inner = inner

                def execute(self, sql, *params, **kw):
                    if "INSERT" in str(sql).upper() or "ATTACH" in str(sql).upper():
                        merge_writes.append(str(sql))
                    return self._inner.execute(sql, *params, **kw)

                def __getattr__(self, name):
                    return getattr(self._inner, name)

            return WriterConn(conn)
        return conn

    with patch("profiles.sqlite3.connect", tracking_connect):
        profiles.migrate_legacy_layout_if_needed()

    assert merge_writes == []


def test_verification_failure_does_not_retire(temp_app, monkeypatch):
    app_dir = temp_app["app_dir"]
    default_dir = temp_app["default_dir"]
    legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
    profile_path = os.path.join(default_dir, FITNESS_DB_NAME)

    _seed_session(legacy_path, "2026-10-01")
    monkeypatch.setattr(profiles, "_fitness_db_verified", lambda *_a, **_k: False)
    profiles.migrate_legacy_layout_if_needed()
    assert os.path.exists(legacy_path)


def test_long_user_data_path_retire_retry(temp_app, monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        long_root = os.path.join(tmp, "u" * 120, "nested", "data-store")
        os.makedirs(long_root, exist_ok=True)
        app_dir = os.path.join(long_root, "app")
        profiles_root = os.path.join(app_dir, "profiles")
        default_dir = os.path.join(profiles_root, "default")
        os.makedirs(default_dir, exist_ok=True)
        config_path = os.path.join(app_dir, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(profiles.default_config(), f)

        monkeypatch.setattr(profiles, "get_app_dir", lambda: app_dir)
        monkeypatch.setattr(profiles, "get_profiles_root", lambda: profiles_root)
        monkeypatch.setattr(profiles, "get_config_path", lambda: config_path)
        monkeypatch.setattr(profiles, "get_profile_dir", lambda pid=None: default_dir)

        legacy_path = os.path.join(app_dir, FITNESS_DB_NAME)
        _seed_session(legacy_path, "2026-10-03")
        profiles.migrate_legacy_layout_if_needed()
        assert not os.path.exists(legacy_path)