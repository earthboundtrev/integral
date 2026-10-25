"""Migrate legacy data.json fitness sessions to fitness.db.

Per issue #116: idempotent, backed up, tested migration of program-based sessions
from data.json into the new workout_sessions/workout_sets SQLite schema.

Issues #152 / #154: migrate decrypted in-memory sessions only; persist flags via
the app save path; backup on-disk data.json bytes (encrypted when applicable).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime
from typing import Any

from progression.db import FitnessRepository
from progression.models import WorkoutSession

VOLATILE_SESSION_KEYS = frozenset({"migrated_to_fitness_db"})


def session_for_hash(sess: dict) -> dict:
    """Session dict used for stable idempotency hashing (volatile keys stripped)."""
    return {k: v for k, v in sess.items() if k not in VOLATILE_SESSION_KEYS}


def legacy_source_hash(sess: dict) -> str:
    return hashlib.sha256(
        json.dumps(session_for_hash(sess), sort_keys=True).encode()
    ).hexdigest()[:12]


def _migration_backup_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _secure_copy(src: str, dest: str) -> None:
    shutil.copy2(src, dest)
    try:
        os.chmod(dest, 0o600)
    except (OSError, AttributeError):
        pass


def _backup_sqlite_db(db_path: str, backup_path: str) -> None:
    with sqlite3.connect(db_path) as source:
        with sqlite3.connect(backup_path) as dest:
            source.backup(dest)
    try:
        os.chmod(backup_path, 0o600)
    except (OSError, AttributeError):
        pass


def _list_migration_backup_files(directory: str) -> list[str]:
    if not os.path.isdir(directory):
        return []
    return [
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if ".migration_backup_" in name
    ]


def prune_migration_backups(directory: str, keep_timestamp: str | None = None) -> None:
    """Keep at most one migration backup pair (newest, or the given timestamp suffix)."""
    files = _list_migration_backup_files(directory)
    if not files:
        return

    def suffix(path: str) -> str:
        marker = ".migration_backup_"
        idx = path.rfind(marker)
        if idx < 0:
            return ""
        return path[idx + len(marker) :]

    by_suffix: dict[str, list[str]] = {}
    for path in files:
        suf = suffix(path)
        if suf:
            by_suffix.setdefault(suf, []).append(path)

    if not by_suffix:
        return

    if keep_timestamp and keep_timestamp in by_suffix:
        keep = keep_timestamp
    else:
        keep = max(by_suffix.keys())

    for suf, paths in by_suffix.items():
        if suf == keep:
            continue
        for path in paths:
            try:
                os.remove(path)
            except OSError:
                pass


def backup_files_for_migration(data_path: str, db_path: str) -> tuple[str, str | None]:
    """Create timestamped backups of data.json (on-disk bytes) and fitness.db.

    Returns:
        (data_backup_path, db_backup_path or None)
    """
    timestamp = _migration_backup_timestamp()
    data_backup = f"{data_path}.migration_backup_{timestamp}"
    try:
        _secure_copy(data_path, data_backup)
    except Exception as e:
        raise Exception(f"Failed to backup data.json: {e}") from e

    db_backup = None
    if os.path.exists(db_path):
        db_backup = f"{db_path}.migration_backup_{timestamp}"
        try:
            _backup_sqlite_db(db_path, db_backup)
        except Exception as e:
            try:
                os.remove(data_backup)
            except OSError:
                pass
            raise Exception(f"Failed to backup fitness.db: {e}") from e

    prune_migration_backups(os.path.dirname(os.path.abspath(data_path)), keep_timestamp=timestamp)
    return (data_backup, db_backup)


def _existing_legacy_hashes(conn: sqlite3.Connection) -> set[str]:
    existing = conn.execute(
        "SELECT notes FROM workout_sessions WHERE notes LIKE '[LEGACY:%'"
    ).fetchall()
    return {
        row["notes"].split("[LEGACY:")[1].split("]")[0]
        for row in existing
        if row["notes"] and "[LEGACY:" in row["notes"]
    }


def migrate_legacy_sessions(
    data: dict,
    repo: FitnessRepository,
    dry_run: bool = False,
    *,
    include_free_text_notes: bool = True,
) -> dict[str, Any]:
    """Migrate legacy data.json 'sessions' to fitness.db workout_sessions/workout_sets."""
    legacy_sessions = data.get("sessions", [])

    result: dict[str, Any] = {
        "migrated_count": 0,
        "skipped_count": 0,
        "flagged_count": 0,
        "errors": [],
        "session_ids": [],
        "sessions_to_flag": [],
    }

    if not legacy_sessions:
        return result

    repo.initialize()

    with repo.connect(timeout=10.0) as conn:
        existing_hashes = _existing_legacy_hashes(conn)

        sessions_to_flag: list[dict] = []
        for sess in legacy_sessions:
            if sess.get("migrated_to_fitness_db"):
                continue
            source_hash = legacy_source_hash(sess)
            if source_hash in existing_hashes:
                sessions_to_flag.append(sess)
                continue
            if not sess.get("date"):
                result["errors"].append(f"Session missing date: {sess}")
                result["skipped_count"] += 1

        if dry_run:
            for sess in legacy_sessions:
                if sess.get("migrated_to_fitness_db"):
                    result["skipped_count"] += 1
                    continue
                source_hash = legacy_source_hash(sess)
                if source_hash in existing_hashes:
                    result["skipped_count"] += 1
                    if sess not in sessions_to_flag:
                        sessions_to_flag.append(sess)
                    continue
                if not sess.get("date"):
                    continue
                result["migrated_count"] += 1
            result["sessions_to_flag"] = sessions_to_flag
            return result

        try:
            for sess in legacy_sessions:
                try:
                    if sess.get("migrated_to_fitness_db"):
                        result["skipped_count"] += 1
                        continue

                    source_hash = legacy_source_hash(sess)
                    if source_hash in existing_hashes:
                        result["skipped_count"] += 1
                        sessions_to_flag.append(sess)
                        continue

                    date = sess.get("date")
                    if not date:
                        continue

                    notes_parts = [f"[LEGACY:{source_hash}]"]
                    program_id = sess.get("program_id", sess.get("program", ""))
                    if program_id:
                        notes_parts.append(f"Program: {program_id}")

                    rpe = sess.get("session_rpe")
                    if rpe:
                        notes_parts.append(f"RPE: {rpe}")

                    duration = sess.get("duration_min", sess.get("duration_minutes"))
                    if duration:
                        notes_parts.append(f"Duration: {duration}min")

                    movement_logs = sess.get("movement_logs", [])
                    if movement_logs:
                        for log in movement_logs:
                            movement_name = (
                                log.get("movement_name")
                                or log.get("chain_name")
                                or log.get("movement_key", "")
                            )
                            if movement_name:
                                notes_parts.append(f"- {movement_name}")
                                if log.get("step"):
                                    notes_parts.append(f"  Step {log['step']}")
                                if log.get("reps_per_set"):
                                    notes_parts.append(f"  Reps: {log['reps_per_set']}")
                                if log.get("hold_seconds"):
                                    notes_parts.append(f"  Hold: {log['hold_seconds']}s")
                                if log.get("height_cm"):
                                    notes_parts.append(f"  Height: {log['height_cm']}cm")
                                if log.get("form_quality"):
                                    notes_parts.append(f"  Form: {log['form_quality']}/10")

                    if include_free_text_notes:
                        user_notes = sess.get("notes", "")
                        if user_notes:
                            notes_parts.append(f"\n{user_notes}")

                    notes = "\n".join(notes_parts)

                    session = WorkoutSession(
                        date=date,
                        notes=notes,
                        duration_minutes=duration if isinstance(duration, int) else None,
                        body_weight_kg=None,
                    )

                    conn.execute(
                        """
                        INSERT INTO workout_sessions (id, date, notes, duration_minutes, body_weight_kg)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            session.id,
                            session.date,
                            session.notes,
                            session.duration_minutes,
                            session.body_weight_kg,
                        ),
                    )

                    result["migrated_count"] += 1
                    result["session_ids"].append(session.id)
                    existing_hashes.add(source_hash)
                    sessions_to_flag.append(sess)

                except Exception as e:
                    result["errors"].append(
                        f"Error migrating session {sess.get('date', 'unknown')}: {e}"
                    )
                    result["skipped_count"] += 1

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise Exception(f"Migration transaction failed: {e}") from e

    result["sessions_to_flag"] = sessions_to_flag
    return result


def apply_migrated_flags(sessions: list[dict], sessions_to_flag: list[dict]) -> int:
    """Set migrated_to_fitness_db on in-memory session dicts (after DB commit)."""
    flagged = 0
    now = datetime.now().isoformat()
    for sess in sessions_to_flag:
        if "migrated_to_fitness_db" not in sess:
            sess["migrated_to_fitness_db"] = now
            flagged += 1
    return flagged


def run_in_memory_migration(
    sessions: list[dict],
    fitness_db_path: str,
    *,
    data_path: str,
    include_free_text_notes: bool = True,
) -> dict[str, Any]:
    """Migrate legacy sessions from an in-memory list; never writes data.json."""
    data = {"sessions": sessions}
    repo = FitnessRepository(db_path=fitness_db_path)

    plan = migrate_legacy_sessions(
        data,
        repo,
        dry_run=True,
        include_free_text_notes=include_free_text_notes,
    )
    work = plan["migrated_count"] > 0 or bool(plan.get("sessions_to_flag"))

    if not work:
        return {
            **plan,
            "flagged_count": 0,
            "backed_up": False,
        }

    data_backup: str | None = None
    db_backup: str | None = None
    try:
        data_backup, db_backup = backup_files_for_migration(data_path, fitness_db_path)
        result = migrate_legacy_sessions(
            data,
            repo,
            dry_run=False,
            include_free_text_notes=include_free_text_notes,
        )
        flagged = apply_migrated_flags(sessions, result.get("sessions_to_flag", []))
        result["flagged_count"] = flagged
        result["backed_up"] = True
        result["data_backup"] = data_backup
        result["db_backup"] = db_backup
        return result
    except Exception as e:
        raise Exception(
            f"Migration failed (backups preserved at {data_backup}, {db_backup}): {e}"
        ) from e


def run_migration(
    data_path: str,
    fitness_db_path: str,
    mark_migrated: bool = True,
    *,
    passphrase: str | None = None,
    include_free_text_notes: bool = True,
) -> dict[str, Any]:
    """CLI/test helper: load via vault, migrate in memory, optionally flag (not save).

    Callers must persist flagged sessions through save_data() / save_data_file().
    """
    from vault import load_data_file

    data = load_data_file(data_path, passphrase)
    sessions = data.get("sessions", [])
    if not sessions:
        return {
            "migrated_count": 0,
            "skipped_count": 0,
            "flagged_count": 0,
            "errors": [],
            "session_ids": [],
            "backed_up": False,
        }

    result = run_in_memory_migration(
        sessions,
        fitness_db_path,
        data_path=data_path,
        include_free_text_notes=include_free_text_notes,
    )
    if mark_migrated and result.get("flagged_count", 0) > 0:
        # Flags are already on the loaded session dicts in `data`; tests that
        # need persistence must save separately.
        pass
    return result


def mark_migrated_in_data_json(data_path: str) -> None:
    """Deprecated: direct data.json rewrite bypasses vault save path (#154).

    Kept for backward compatibility in older tests only.
    """
    from vault import load_data_file, save_data_file

    data = load_data_file(data_path, None)
    sessions = data.get("sessions", [])
    apply_migrated_flags(sessions, sessions)
    encrypted = False
    try:
        with open(data_path, encoding="utf-8") as handle:
            raw = json.load(handle)
        encrypted = isinstance(raw, dict) and raw.get("integral_encrypted") is True
    except (json.JSONDecodeError, OSError):
        pass
    if encrypted:
        raise RuntimeError(
            "mark_migrated_in_data_json cannot write encrypted data; use save_data_file"
        )
    save_data_file(data_path, data, encrypted=False, passphrase=None)
