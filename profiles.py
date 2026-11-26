import json
import os
import re
import sqlite3
from dataclasses import dataclass
from enum import Enum

import paths

APP_DIR_NAME = paths.APP_SLUG
PROFILES_DIR_NAME = "profiles"
CONFIG_FILE_NAME = "config.json"
DEFAULT_PROFILE_ID = "default"
DEFAULT_PROFILE_NAME = "Default"
_SAFE_PROFILE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")

GENERIC_LEGACY_FITNESS_NOTICE = (
    "Workout storage could not be read. Try restarting the app."
)

_legacy_fitness_notices: list[str] = []

_FITNESS_DB_WRITABLE_SIDECARS = ("-wal", "-shm", "-journal")


def consume_legacy_fitness_notices() -> list[str]:
    """Return and clear user-facing messages from the last legacy fitness pass."""
    global _legacy_fitness_notices
    notes = list(_legacy_fitness_notices)
    _legacy_fitness_notices.clear()
    return notes


def _queue_legacy_fitness_notice() -> None:
    if GENERIC_LEGACY_FITNESS_NOTICE not in _legacy_fitness_notices:
        _legacy_fitness_notices.append(GENERIC_LEGACY_FITNESS_NOTICE)


class SessionCountOutcome(Enum):
    MISSING = "missing"
    OK = "ok"
    LOCKED = "locked"
    UNREADABLE = "unreadable"


@dataclass(frozen=True)
class WorkoutSessionCountResult:
    outcome: SessionCountOutcome
    count: int = 0

    @property
    def has_sessions(self) -> bool:
        return self.outcome == SessionCountOutcome.OK and self.count > 0

    @property
    def is_genuine_zero(self) -> bool:
        return self.outcome == SessionCountOutcome.OK and self.count == 0

    @property
    def is_error(self) -> bool:
        return self.outcome in (SessionCountOutcome.LOCKED, SessionCountOutcome.UNREADABLE)


def _fitness_busy_timeout_ms() -> int:
    raw = os.environ.get("INTEGRAL_FITNESS_BUSY_TIMEOUT_MS")
    if raw is not None:
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return 250


def _close_sqlite(conn: sqlite3.Connection | None) -> None:
    if conn is None:
        return
    try:
        conn.close()
    except sqlite3.Error:
        pass


def _open_fitness_sqlite(db_path: str, *, readonly: bool) -> sqlite3.Connection:
    busy_ms = _fitness_busy_timeout_ms()
    timeout_s = busy_ms / 1000.0 if busy_ms else 0.0
    if readonly:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=timeout_s)
    else:
        conn = sqlite3.connect(db_path, timeout=timeout_s)
    if busy_ms:
        conn.execute(f"PRAGMA busy_timeout = {int(busy_ms)}")
    return conn


def _classify_sqlite_error(exc: sqlite3.Error) -> SessionCountOutcome:
    if isinstance(exc, sqlite3.OperationalError):
        text = str(exc).lower()
        if "locked" in text or "busy" in text:
            return SessionCountOutcome.LOCKED
    return SessionCountOutcome.UNREADABLE


def require_safe_profile_id(profile_id: object) -> str:
    """Reject path traversal or odd characters in backup manifest profile ids."""
    if not isinstance(profile_id, str):
        raise ValueError("Backup profile id must be a string.")
    pid = profile_id.strip()
    if not pid or not _SAFE_PROFILE_ID_RE.match(pid):
        raise ValueError(f"Backup contains an invalid profile id: {profile_id!r}")
    return pid


def validate_manifest_profile_ids(manifest: dict) -> list[str]:
    """Validate profile ids declared in a backup manifest (if present)."""
    if "profiles" not in manifest:
        return []
    raw = manifest["profiles"]
    if not isinstance(raw, list):
        raise ValueError("Backup manifest profiles must be a list.")
    ids = [require_safe_profile_id(pid) for pid in raw]
    active = manifest.get("active_profile_id")
    if active is not None and str(active).strip():
        require_safe_profile_id(active)
    return ids


def get_app_dir() -> str:
    return paths.user_data_dir()


def get_profiles_root() -> str:
    return os.path.join(get_app_dir(), PROFILES_DIR_NAME)


def get_config_path() -> str:
    return os.path.join(get_app_dir(), CONFIG_FILE_NAME)


def slugify_profile_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "profile"


def default_config() -> dict:
    return {
        "active_profile_id": DEFAULT_PROFILE_ID,
        "profiles": [{"id": DEFAULT_PROFILE_ID, "name": DEFAULT_PROFILE_NAME}],
    }


def load_config() -> dict:
    ensure_app_structure()
    path = get_config_path()
    if not os.path.exists(path):
        config = default_config()
        save_config(config)
        return config
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)
    config.setdefault("active_profile_id", DEFAULT_PROFILE_ID)
    config.setdefault("profiles", default_config()["profiles"])
    return config


def save_config(config: dict) -> None:
    os.makedirs(get_app_dir(), exist_ok=True)
    with open(get_config_path(), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def list_profiles() -> list[dict]:
    return load_config()["profiles"]


def get_active_profile_id() -> str:
    return load_config()["active_profile_id"]


def get_active_profile() -> dict:
    config = load_config()
    active_id = config["active_profile_id"]
    for profile in config["profiles"]:
        if profile["id"] == active_id:
            return profile
    return config["profiles"][0]


def set_active_profile(profile_id: str) -> dict:
    config = load_config()
    if not any(p["id"] == profile_id for p in config["profiles"]):
        raise ValueError(f"Unknown profile: {profile_id}")
    config["active_profile_id"] = profile_id
    save_config(config)
    return get_profile(profile_id)


def get_profile(profile_id: str) -> dict:
    for profile in load_config()["profiles"]:
        if profile["id"] == profile_id:
            return profile
    raise ValueError(f"Unknown profile: {profile_id}")


def get_profile_dir(profile_id: str | None = None) -> str:
    pid = profile_id or get_active_profile_id()
    return os.path.join(get_profiles_root(), pid)


def create_profile(name: str, profile_id: str | None = None) -> dict:
    config = load_config()
    base_id = profile_id or slugify_profile_id(name)
    candidate = base_id
    suffix = 2
    existing_ids = {p["id"] for p in config["profiles"]}
    while candidate in existing_ids:
        candidate = f"{base_id}-{suffix}"
        suffix += 1

    profile = {"id": candidate, "name": name.strip()}
    config["profiles"].append(profile)
    save_config(config)
    os.makedirs(get_profile_dir(candidate), exist_ok=True)
    return profile


def ensure_app_structure() -> None:
    import user_data_migration

    user_data_migration.run_at_startup()
    os.makedirs(get_profiles_root(), exist_ok=True)
    try:
        migrate_legacy_layout_if_needed()
    except (OSError, sqlite3.Error):
        pass


def _workout_session_count_result(db_path: str) -> WorkoutSessionCountResult:
    if not os.path.isfile(db_path):
        return WorkoutSessionCountResult(SessionCountOutcome.MISSING, 0)
    if os.path.getsize(db_path) == 0:
        return WorkoutSessionCountResult(SessionCountOutcome.OK, 0)
    conn = None
    try:
        conn = _open_fitness_sqlite(db_path, readonly=True)
        count = int(conn.execute("SELECT COUNT(*) FROM workout_sessions").fetchone()[0])
        return WorkoutSessionCountResult(SessionCountOutcome.OK, count)
    except (sqlite3.Error, TypeError, ValueError) as exc:
        if isinstance(exc, sqlite3.Error):
            return WorkoutSessionCountResult(_classify_sqlite_error(exc), 0)
        return WorkoutSessionCountResult(SessionCountOutcome.UNREADABLE, 0)
    finally:
        _close_sqlite(conn)


def _workout_session_count(db_path: str) -> int:
    result = _workout_session_count_result(db_path)
    if result.outcome in (SessionCountOutcome.OK, SessionCountOutcome.MISSING):
        return result.count
    return 0


def _next_nonexistent_path(base_path: str) -> str:
    if not os.path.exists(base_path):
        return base_path
    n = 1
    while True:
        candidate = f"{base_path}.{n}"
        if not os.path.exists(candidate):
            return candidate
        n += 1


def _live_fitness_db_is_truly_empty(live_db_path: str) -> bool:
    if not os.path.isfile(live_db_path):
        return True
    if os.path.getsize(live_db_path) == 0:
        return True
    return _workout_session_count_result(live_db_path).is_genuine_zero


def _fitness_backup_has_sessions(bak_path: str) -> bool:
    """True when the backup file holds readable workout session rows."""
    if not os.path.isfile(bak_path) or os.path.getsize(bak_path) == 0:
        return False
    return _workout_session_count_result(bak_path).has_sessions


def _prepare_pre_legacy_restore_bak(live_db_path: str) -> str:
    """Rotate an existing fixed-name bak aside, then allocate that name for a new backup."""
    fixed_bak = f"{live_db_path}.pre-legacy-restore.bak"
    live_empty = _live_fitness_db_is_truly_empty(live_db_path)
    if (
        live_empty
        and os.path.isfile(fixed_bak)
        and _fitness_backup_has_sessions(fixed_bak)
    ):
        return _next_nonexistent_path(fixed_bak)
    if os.path.isfile(fixed_bak):
        os.replace(fixed_bak, _next_nonexistent_path(fixed_bak))
    return _next_nonexistent_path(fixed_bak)


def _copy_fitness_db_with_sidecars(src_base: str, dest_base: str) -> None:
    from integral_io import atomic_copy_file

    atomic_copy_file(src_base, dest_base)
    for suffix in _FITNESS_DB_WRITABLE_SIDECARS:
        src_side = f"{src_base}{suffix}"
        if os.path.isfile(src_side):
            atomic_copy_file(src_side, f"{dest_base}{suffix}")


def _remove_writable_fitness_sidecars(db_path: str) -> None:
    """Remove stale WAL/SHM/journal files only — never the live database file."""
    for suffix in _FITNESS_DB_WRITABLE_SIDECARS:
        sidecar = f"{db_path}{suffix}"
        if os.path.exists(sidecar):
            os.remove(sidecar)


def _fitness_paths_are_safe(profile_path: str, staged_path: str) -> bool:
    if os.path.islink(profile_path):
        return False
    parent = os.path.dirname(profile_path) or "."
    if os.path.islink(parent):
        return False
    if os.path.islink(staged_path):
        return False
    return True


def _replace_empty_profile_fitness_from_legacy(profile_path: str, legacy_path: str) -> bool:
    """Copy legacy root fitness.db over an empty profile db with bak-first safety."""
    from integral_io import atomic_copy_file

    staged = f"{profile_path}.legacy-restore-incoming.tmp"
    if not _fitness_paths_are_safe(profile_path, staged):
        return False

    try:
        backup_path = _prepare_pre_legacy_restore_bak(profile_path)
        _copy_fitness_db_with_sidecars(profile_path, backup_path)
        atomic_copy_file(legacy_path, staged)
        _remove_writable_fitness_sidecars(profile_path)
        os.replace(staged, profile_path)
        return True
    except OSError:
        if os.path.isfile(staged):
            try:
                os.remove(staged)
            except OSError:
                pass
        return False


def _workout_session_ids(db_path: str) -> list[str] | None:
    """Session ids in a fitness database, or None when the database cannot be read."""
    if not os.path.isfile(db_path):
        return []
    conn = None
    try:
        conn = _open_fitness_sqlite(db_path, readonly=True)
        rows = conn.execute("SELECT id FROM workout_sessions").fetchall()
        return [str(row[0]) for row in rows]
    except (sqlite3.Error, TypeError, ValueError):
        return None
    finally:
        _close_sqlite(conn)


_LEGACY_FITNESS_SIDECARS = ("", "-wal", "-shm", "-journal")


def _unique_retired_fitness_basename(app_dir: str) -> str:
    for index in range(1, 10_000):
        candidate = f"fitness.db.retired-{index}"
        if not os.path.exists(os.path.join(app_dir, candidate)):
            return candidate
    raise RuntimeError("Could not allocate a unique retired fitness database name.")


def _fitness_db_verified(profile_path: str, expected_legacy_session_ids: list[str]) -> bool:
    if not os.path.isfile(profile_path):
        return False
    conn = None
    try:
        conn = _open_fitness_sqlite(profile_path, readonly=True)
        row = conn.execute("PRAGMA integrity_check").fetchone()
        if not row or str(row[0]).lower() != "ok":
            return False
        for session_id in expected_legacy_session_ids:
            found = conn.execute(
                "SELECT 1 FROM workout_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if not found:
                return False
        return True
    except sqlite3.Error:
        return False
    finally:
        _close_sqlite(conn)


def _legacy_fitness_sidecars_still_present(legacy_fitness: str) -> bool:
    return any(
        os.path.exists(f"{legacy_fitness}{suffix}")
        for suffix in _LEGACY_FITNESS_SIDECARS
        if suffix
    )


def _retired_fitness_basename_for_sidecars(app_dir: str) -> str | None:
    pattern = re.compile(r"^fitness\.db\.retired-(\d+)$")
    best_index = -1
    best_name: str | None = None
    for name in os.listdir(app_dir):
        match = pattern.match(name)
        if match and int(match.group(1)) > best_index:
            best_index = int(match.group(1))
            best_name = name
    return best_name


def _finish_orphan_legacy_fitness_sidecars(legacy_fitness: str) -> bool:
    """After the main file was retired, move any leftover root sidecars beside it."""
    if os.path.exists(legacy_fitness) or not _legacy_fitness_sidecars_still_present(legacy_fitness):
        return True
    app_dir = os.path.dirname(legacy_fitness)
    retired_base = _retired_fitness_basename_for_sidecars(app_dir)
    if not retired_base:
        return False
    ok = True
    for suffix in ("-wal", "-shm", "-journal"):
        src = f"{legacy_fitness}{suffix}"
        if not os.path.exists(src):
            continue
        dest = os.path.join(app_dir, f"{retired_base}{suffix}")
        try:
            os.replace(src, dest)
        except OSError:
            ok = False
    return ok and not _legacy_fitness_sidecars_still_present(legacy_fitness)


def _retire_legacy_root_fitness_db(legacy_fitness: str) -> bool:
    """Rename legacy root fitness.db and sidecars aside. True when the root copy is gone."""
    if not os.path.exists(legacy_fitness):
        return _finish_orphan_legacy_fitness_sidecars(legacy_fitness)
    app_dir = os.path.dirname(legacy_fitness)
    retired_base = _unique_retired_fitness_basename(app_dir)
    main_dest = os.path.join(app_dir, retired_base)
    try:
        os.replace(legacy_fitness, main_dest)
    except OSError:
        return False
    ok = True
    for suffix in ("-wal", "-shm", "-journal"):
        src = f"{legacy_fitness}{suffix}"
        if not os.path.exists(src):
            continue
        dest = os.path.join(app_dir, f"{retired_base}{suffix}")
        try:
            os.replace(src, dest)
        except OSError:
            ok = False
    if not ok:
        return False
    return not os.path.exists(legacy_fitness) and not _legacy_fitness_sidecars_still_present(
        legacy_fitness
    )


def _maybe_retire_legacy_fitness_after_import(
    legacy_fitness: str,
    profile_fitness: str,
    legacy_session_ids: list[str],
    *,
    import_attempted: bool,
    replace_succeeded: bool,
    profile_started_empty: bool = False,
) -> None:
    if not os.path.exists(legacy_fitness):
        return
    if replace_succeeded:
        if not _fitness_db_verified(profile_fitness, legacy_session_ids):
            return
        _retire_legacy_root_fitness_db(legacy_fitness)
        return
    if not import_attempted:
        return
    if profile_started_empty:
        post = _workout_session_count_result(profile_fitness)
        if post.is_error or post.is_genuine_zero:
            return
    elif legacy_session_ids:
        post = _workout_session_count_result(profile_fitness)
        if post.outcome == SessionCountOutcome.OK and post.count == 0:
            return
    if not _fitness_db_verified(profile_fitness, legacy_session_ids):
        return
    _retire_legacy_root_fitness_db(legacy_fitness)


_FITNESS_DB_MERGE_TABLES = (
    "exercises",
    "progression_edges",
    "user_exercise_progress",
    "workout_sessions",
    "workout_sets",
    "body_composition_logs",
)


def _table_column_names(conn: sqlite3.Connection, schema: str, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA {schema}.table_info({table})").fetchall()
    return [row[1] for row in rows]


def _merge_legacy_fitness_db_into_profile(legacy_path: str, profile_path: str) -> bool:
    """Copy missing rows from legacy root fitness.db into the profile database."""
    conn = None
    try:
        conn = _open_fitness_sqlite(profile_path, readonly=False)
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("ATTACH DATABASE ? AS legacy", (legacy_path,))
        merge_failed = False
        for table in _FITNESS_DB_MERGE_TABLES:
            try:
                main_cols = set(_table_column_names(conn, "main", table))
                legacy_cols = _table_column_names(conn, "legacy", table)
                shared = [column for column in legacy_cols if column in main_cols]
                if not shared:
                    continue
                columns_sql = ", ".join(shared)
                conn.execute(
                    f"INSERT OR IGNORE INTO main.{table} ({columns_sql}) "
                    f"SELECT {columns_sql} FROM legacy.{table}"
                )
            except sqlite3.OperationalError:
                merge_failed = True
                break
        if merge_failed:
            conn.rollback()
            return False
        conn.commit()
        try:
            conn.execute("DETACH DATABASE legacy")
        except sqlite3.Error:
            pass
        conn.execute("PRAGMA foreign_keys = ON")
        return True
    except sqlite3.OperationalError:
        return False
    except sqlite3.DatabaseError:
        return False
    finally:
        _close_sqlite(conn)


def _maybe_replace_empty_profile_fitness(
    default_fitness: str, legacy_fitness: str, *, merge_succeeded: bool
) -> bool:
    if not merge_succeeded:
        return False
    recount = _workout_session_count_result(default_fitness)
    if recount.outcome == SessionCountOutcome.UNREADABLE:
        _queue_legacy_fitness_notice()
        return False
    if recount.outcome == SessionCountOutcome.LOCKED:
        return False
    if not recount.is_genuine_zero:
        return False
    return _replace_empty_profile_fitness_from_legacy(default_fitness, legacy_fitness)


def _import_both_legacy_and_profile_fitness(
    legacy_fitness: str,
    default_fitness: str,
    legacy_session_ids: list[str],
) -> None:
    profile_count = _workout_session_count_result(default_fitness)
    if profile_count.outcome == SessionCountOutcome.UNREADABLE:
        _queue_legacy_fitness_notice()
        return
    if profile_count.outcome == SessionCountOutcome.LOCKED:
        return

    legacy_count = _workout_session_count_result(legacy_fitness)
    if legacy_count.is_error:
        return
    if not legacy_count.has_sessions:
        if _fitness_db_verified(default_fitness, []):
            _retire_legacy_root_fitness_db(legacy_fitness)
        return

    profile_started_empty = profile_count.is_genuine_zero
    merge_succeeded = _merge_legacy_fitness_db_into_profile(
        legacy_fitness, default_fitness
    )
    merge_failed = not merge_succeeded
    if merge_failed:
        return

    if profile_started_empty:
        recount = _workout_session_count_result(default_fitness)
        if recount.outcome == SessionCountOutcome.UNREADABLE:
            _queue_legacy_fitness_notice()
            return
        if recount.outcome == SessionCountOutcome.LOCKED:
            return
        if recount.is_genuine_zero:
            replace_succeeded = _replace_empty_profile_fitness_from_legacy(
                default_fitness, legacy_fitness
            )
            if replace_succeeded:
                _maybe_retire_legacy_fitness_after_import(
                    legacy_fitness,
                    default_fitness,
                    legacy_session_ids,
                    import_attempted=True,
                    replace_succeeded=True,
                    profile_started_empty=True,
                )
            return
        _maybe_retire_legacy_fitness_after_import(
            legacy_fitness,
            default_fitness,
            legacy_session_ids,
            import_attempted=True,
            replace_succeeded=False,
            profile_started_empty=True,
        )
        return

    _maybe_retire_legacy_fitness_after_import(
        legacy_fitness,
        default_fitness,
        legacy_session_ids,
        import_attempted=True,
        replace_succeeded=False,
        profile_started_empty=False,
    )


def migrate_legacy_layout_if_needed() -> None:
    """Migrate data.json and fitness.db from app root to default profile directory.

    One-time migration using atomic copy. When #329 created an empty profile
    fitness.db while legacy root still holds sessions, restore or merge.
    """
    from integral_io import atomic_copy_file

    app_dir = get_app_dir()
    legacy_data = os.path.join(app_dir, "data.json")
    default_dir = get_profile_dir(DEFAULT_PROFILE_ID)
    default_data = os.path.join(default_dir, "data.json")

    os.makedirs(default_dir, exist_ok=True)

    try:
        if os.path.exists(legacy_data) and not os.path.exists(default_data):
            atomic_copy_file(legacy_data, default_data)

        legacy_fitness = os.path.join(app_dir, "fitness.db")
        default_fitness = os.path.join(default_dir, "fitness.db")
        if not os.path.exists(legacy_fitness):
            _finish_orphan_legacy_fitness_sidecars(legacy_fitness)
        if os.path.exists(legacy_fitness) and not os.path.exists(default_fitness):
            legacy_session_ids = _workout_session_ids(legacy_fitness)
            try:
                atomic_copy_file(legacy_fitness, default_fitness)
            except OSError:
                pass
            else:
                if legacy_session_ids is not None:
                    _maybe_retire_legacy_fitness_after_import(
                        legacy_fitness,
                        default_fitness,
                        legacy_session_ids,
                        import_attempted=True,
                        replace_succeeded=False,
                    )
        elif os.path.exists(legacy_fitness) and os.path.exists(default_fitness):
            legacy_session_ids = _workout_session_ids(legacy_fitness)
            if legacy_session_ids is None:
                pass
            elif not legacy_session_ids:
                if _fitness_db_verified(default_fitness, []):
                    _retire_legacy_root_fitness_db(legacy_fitness)
            else:
                _import_both_legacy_and_profile_fitness(
                    legacy_fitness, default_fitness, legacy_session_ids
                )
    except (OSError, sqlite3.Error):
        pass

    if not os.path.exists(get_config_path()):
        save_config(default_config())