import json
import os
import re
import shutil
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
    migrate_legacy_layout_if_needed()


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
                continue
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

    if os.path.exists(legacy_data) and not os.path.exists(default_data):
        atomic_copy_file(legacy_data, default_data)

    legacy_fitness = os.path.join(app_dir, "fitness.db")
    default_fitness = os.path.join(default_dir, "fitness.db")
    if os.path.exists(legacy_fitness) and not os.path.exists(default_fitness):
        try:
            atomic_copy_file(legacy_fitness, default_fitness)
        except OSError:
            pass
    elif os.path.exists(legacy_fitness) and os.path.exists(default_fitness):
        profile_count = _workout_session_count_result(default_fitness)
        if profile_count.outcome == SessionCountOutcome.UNREADABLE:
            _queue_legacy_fitness_notice()
        elif profile_count.outcome == SessionCountOutcome.LOCKED:
            pass
        else:
            legacy_count = _workout_session_count_result(legacy_fitness)
            if legacy_count.outcome == SessionCountOutcome.UNREADABLE:
                pass
            elif legacy_count.outcome == SessionCountOutcome.LOCKED:
                pass
            else:
                if legacy_count.has_sessions:
                    _merge_legacy_fitness_db_into_profile(legacy_fitness, default_fitness)
                if profile_count.is_genuine_zero and legacy_count.has_sessions:
                    recount = _workout_session_count_result(default_fitness)
                    if recount.outcome == SessionCountOutcome.UNREADABLE:
                        _queue_legacy_fitness_notice()
                    elif recount.outcome == SessionCountOutcome.LOCKED:
                        pass
                    elif recount.is_genuine_zero:
                        backup = f"{default_fitness}.pre-legacy-restore.bak"
                        try:
                            atomic_copy_file(default_fitness, backup)
                            for suffix in ("", "-wal", "-shm"):
                                sidecar = f"{default_fitness}{suffix}"
                                if os.path.exists(sidecar):
                                    os.remove(sidecar)
                            atomic_copy_file(legacy_fitness, default_fitness)
                        except OSError:
                            pass

    if not os.path.exists(get_config_path()):
        save_config(default_config())