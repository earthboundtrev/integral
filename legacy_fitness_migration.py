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

import paths
from progression.db import FitnessRepository
from progression.models import Exercise, WorkoutSession, WorkoutSet
from progression.fitness_settings import (
    CURRENT_LEGACY_MOVEMENT_SETS_VERSION,
    LEGACY_MOVEMENT_SETS_VERSION_KEY,
    legacy_movement_sets_backfill_pending,
    mark_legacy_movement_sets_version_done,
)

VOLATILE_SESSION_KEYS = frozenset({"migrated_to_fitness_db"})


class LegacyMigrationValidationError(Exception):
    """One or more legacy sessions failed validation; migration must not commit."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def session_needs_legacy_migration(sess: Any) -> bool:
    """True if this session entry should be considered for legacy DB migration."""
    if not isinstance(sess, dict):
        return True
    return not sess.get("migrated_to_fitness_db")


def format_session_ref(index: int, sess: Any) -> str:
    """User-safe session label (index and date only — no notes or full payload)."""
    if isinstance(sess, dict):
        date_val = sess.get("date")
        date_part = str(date_val) if date_val not in (None, "") else "(no date)"
    else:
        date_part = "(no date)"
    return f"session at index {index} (date {date_part})"


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_legacy_session(sess: Any, index: int) -> str | None:
    """Return an error message or None if the session is valid for migration."""
    ref = format_session_ref(index, sess)
    if not isinstance(sess, dict):
        return f"Invalid {ref}: expected a session object"
    date = sess.get("date")
    if not date:
        return f"Invalid {ref}: missing date"
    if not isinstance(date, str):
        return f"Invalid {ref}: date must be a string"
    try:
        datetime.strptime(date.strip(), "%Y-%m-%d")
    except ValueError:
        return f"Invalid {ref}: date is not parseable (expected YYYY-MM-DD)"

    for field in ("session_rpe", "duration_min", "duration_minutes"):
        if field in sess and sess[field] is not None and not _is_numeric(sess[field]):
            return f"Invalid {ref}: {field} must be numeric"

    movement_logs = sess.get("movement_logs", [])
    if movement_logs is None:
        movement_logs = []
    if not isinstance(movement_logs, list):
        return f"Invalid {ref}: movement_logs must be a list"
    for log_index, log in enumerate(movement_logs):
        if not isinstance(log, dict):
            return f"Invalid {ref}: movement_logs[{log_index}] must be an object"
        for key in ("step", "hold_seconds", "height_cm", "form_quality"):
            if key in log and log[key] is not None and not _is_numeric(log[key]):
                return f"Invalid {ref}: movement_logs[{log_index}].{key} must be numeric"
        if "reps_per_set" in log and log["reps_per_set"] is not None:
            reps_val = log["reps_per_set"]
            if isinstance(reps_val, list):
                for rep_index, rep in enumerate(reps_val):
                    if not _is_numeric(rep):
                        return (
                            f"Invalid {ref}: movement_logs[{log_index}]."
                            f"reps_per_set[{rep_index}] must be numeric"
                        )
            elif not _is_numeric(reps_val):
                return f"Invalid {ref}: movement_logs[{log_index}].reps_per_set must be numeric"
    return None


def collect_legacy_session_errors(sessions: list[Any]) -> list[str]:
    errors: list[str] = []
    for index, sess in enumerate(sessions):
        if isinstance(sess, dict) and sess.get("migrated_to_fitness_db"):
            continue
        err = validate_legacy_session(sess, index)
        if err:
            errors.append(err)
    return errors


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
            try:
                os.remove(db_backup)
            except OSError:
                pass
            raise Exception(f"Failed to backup fitness.db: {e}") from e

    prune_migration_backups(os.path.dirname(os.path.abspath(data_path)), keep_timestamp=timestamp)
    return (data_backup, db_backup)


_CC1_MOVEMENT_SUFFIX_TO_STEM: dict[str, str] = {
    "pushups": "push",
    "squats": "squat",
    "pullups": "pull",
    "leg-raises": "leg_raise",
    "bridge": "bridge",
    "handstand-pushups": "handstand_pushup",
}

_PROGRAM_ID_ALIASES: dict[str, str] = {
    "cc1": "convict-conditioning",
    "cc1_push": "convict-conditioning",
    "cc1_pull": "convict-conditioning",
    "cc1_squat": "convict-conditioning",
    "cc1_squats": "convict-conditioning",
    "cc1_leg_raise": "convict-conditioning",
    "cc1_bridge": "convict-conditioning",
    "cc1_handstand_pushup": "convict-conditioning",
    "cc2": "convict-conditioning-2",
    "sm": "strong-medicine",
    "og": "overcoming-gravity",
}

_PROGRAM_MOVEMENT_LADDER: dict[tuple[str, str], tuple[str, str]] | None = None


def _normalize_program_id(program_id: str | None) -> str:
    if not program_id or not isinstance(program_id, str):
        return ""
    key = program_id.strip().lower()
    return _PROGRAM_ID_ALIASES.get(key, key)


def _load_program_movement_ladder_map() -> dict[tuple[str, str], tuple[str, str]]:
    """Map (program_id, movement_key) -> (source_book, seed_file_stem) within one program."""
    global _PROGRAM_MOVEMENT_LADDER
    if _PROGRAM_MOVEMENT_LADDER is not None:
        return _PROGRAM_MOVEMENT_LADDER

    mapping: dict[tuple[str, str], tuple[str, str]] = {}
    seed_root = paths.app_resource("progression", "seed", "v1")
    skip = {"cross_links.json", "exercise_videos.json"}
    if os.path.isdir(seed_root):
        for filename in sorted(os.listdir(seed_root)):
            if not filename.endswith(".json") or filename in skip:
                continue
            path = os.path.join(seed_root, filename)
            try:
                with open(path, encoding="utf-8") as handle:
                    payload = json.load(handle)
            except (OSError, json.JSONDecodeError):
                continue
            source_book = payload.get("source_book")
            hub = payload.get("hub_movement_id")
            source_path = payload.get("source", "")
            if not isinstance(source_book, str) or not isinstance(hub, str):
                continue
            program_id = ""
            if isinstance(source_path, str) and source_path.startswith("programs/"):
                program_id = os.path.splitext(os.path.basename(source_path))[0]
            if program_id:
                stem = filename[:-5]
                mapping[(program_id, hub)] = (source_book, stem)

    cc1_path = os.path.join(paths.programs_dir(), "convict-conditioning.json")
    if os.path.isfile(cc1_path):
        try:
            with open(cc1_path, encoding="utf-8") as handle:
                cc1_program = json.load(handle)
        except (OSError, json.JSONDecodeError):
            cc1_program = {}
        program_id = cc1_program.get("id", "convict-conditioning")
        for movement in cc1_program.get("movements", []) or []:
            movement_id = movement.get("id")
            if not isinstance(movement_id, str) or not movement_id.startswith("cc-"):
                continue
            suffix = movement_id[3:]
            stem_suffix = _CC1_MOVEMENT_SUFFIX_TO_STEM.get(
                suffix, suffix.replace("-", "_")
            )
            mapping[(program_id, movement_id)] = ("CC1", f"cc1_{stem_suffix}")

    _PROGRAM_MOVEMENT_LADDER = mapping
    return mapping


def _infer_family_from_movement_key(movement_key: str, movement_name: str = "") -> str:
    key = (movement_key or "").lower().replace("_", "-")
    name = (movement_name or "").lower()
    hints = (
        ("handstand", "handstand_pushup"),
        ("leg-raise", "leg_raise"),
        ("leg_raise", "leg_raise"),
        ("pullup", "pull"),
        ("pull-up", "pull"),
        ("squat", "squat"),
        ("pushup", "push"),
        ("push-up", "push"),
        ("bridge", "bridge"),
        ("flag", "flag"),
        ("hang", "hang"),
        ("plank", "core"),
        ("deadlift", "hinge"),
        ("row", "pull"),
        ("press", "push"),
        ("bench", "push"),
    )
    for needle, family in hints:
        if needle in key or needle in name:
            return family
    return "legacy"


def _movement_log_label(log: dict) -> str:
    return (
        log.get("movement_name")
        or log.get("chain_name")
        or log.get("movement_key")
        or log.get("chain_key")
        or "movement"
    )


def _normalize_reps_per_set(value: Any) -> list[int | float]:
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if _is_numeric(v)]
    if _is_numeric(value):
        return [value]
    return []


class LegacyExerciseResolver:
    """Resolve legacy movement_logs entries to fitness.db exercise ids."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._by_seed_key: dict[str, str] = {}
        self._by_ladder_step: dict[tuple[str, str, int], str] = {}
        self._program_ladder_map = _load_program_movement_ladder_map()
        self._legacy_cache: dict[tuple[Any, ...], str] = {}
        self._index_exercises()

    def _index_exercises(self) -> None:
        rows = self._conn.execute(
            """
            SELECT id, name, source_book, family, metadata
            FROM exercises
            WHERE deleted_at IS NULL
            """
        ).fetchall()
        for row in rows:
            exercise_id = row["id"]
            source_book = row["source_book"]
            try:
                metadata = json.loads(row["metadata"] or "{}")
            except json.JSONDecodeError:
                metadata = {}
            seed_key = metadata.get("seed_key")
            if isinstance(seed_key, str) and seed_key:
                self._by_seed_key[seed_key] = exercise_id
            step = metadata.get("step")
            seed_file = metadata.get("seed_file")
            if (
                isinstance(source_book, str)
                and isinstance(seed_file, str)
                and isinstance(step, int)
            ):
                stem = os.path.splitext(seed_file)[0]
                self._by_ladder_step[(source_book, stem, step)] = exercise_id

    def _infer_family(self, log: dict) -> str:
        movement_key = log.get("movement_key") or log.get("chain_key") or ""
        return _infer_family_from_movement_key(
            movement_key if isinstance(movement_key, str) else "",
            _movement_log_label(log),
        )

    def _scoped_ladder_match(
        self, program_id: str | None, movement_key: str | None, step: int | None
    ) -> str | None:
        if not movement_key or step is None:
            return None
        norm_program = _normalize_program_id(program_id)
        if not norm_program:
            return None
        ladder = self._program_ladder_map.get((norm_program, movement_key))
        if not ladder:
            return None
        source_book, ladder_stem = ladder
        return self._by_ladder_step.get((source_book, ladder_stem, step))

    def resolve(self, log: dict, program_id: str | None = None) -> str:
        movement_key = log.get("movement_key") or log.get("chain_key")
        step_raw = log.get("step")
        step = int(step_raw) if _is_numeric(step_raw) else None
        norm_program = _normalize_program_id(program_id)
        cache_key = (norm_program, movement_key, step)
        if cache_key in self._legacy_cache:
            return self._legacy_cache[cache_key]

        if isinstance(movement_key, str) and movement_key in self._by_seed_key:
            exercise_id = self._by_seed_key[movement_key]
            self._legacy_cache[cache_key] = exercise_id
            return exercise_id

        hit = self._scoped_ladder_match(program_id, movement_key, step)
        if hit:
            self._legacy_cache[cache_key] = hit
            return hit

        family = self._infer_family(log)
        label = _movement_log_label(log)
        if step is not None:
            name = f"{label} (step {step})"
        else:
            name = str(label)
        exercise = Exercise(
            name=name,
            source_book="Legacy",
            family=family,
            mastery_criteria={},
            metadata={"legacy": True, "step": step},
        )
        self._conn.execute(
            """
            INSERT INTO exercises (
                id, name, source_book, family, mastery_criteria, metadata
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                exercise.id,
                exercise.name,
                exercise.source_book,
                exercise.family,
                json.dumps(exercise.mastery_criteria),
                json.dumps(exercise.metadata),
            ),
        )
        self._legacy_cache[cache_key] = exercise.id
        return exercise.id


def _append_movement_to_notes(notes_parts: list[str], log: dict) -> None:
    movement_name = _movement_log_label(log)
    if not movement_name:
        return
    notes_parts.append(f"- {movement_name}")
    if log.get("step"):
        notes_parts.append(f"  Step {log['step']}")
    if log.get("reps_per_set") is not None:
        notes_parts.append(f"  Reps: {log['reps_per_set']}")
    if log.get("hold_seconds"):
        notes_parts.append(f"  Hold: {log['hold_seconds']}s")
    if log.get("height_cm"):
        notes_parts.append(f"  Height: {log['height_cm']}cm")
    if log.get("form_quality"):
        notes_parts.append(f"  Form: {log['form_quality']}/10")


def build_legacy_session_notes(
    sess: dict,
    source_hash: str,
    *,
    include_free_text_notes: bool = True,
) -> str:
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

    movement_logs = sess.get("movement_logs") or []
    for log in movement_logs:
        if isinstance(log, dict):
            _append_movement_to_notes(notes_parts, log)

    if include_free_text_notes:
        user_notes = sess.get("notes", "")
        if user_notes:
            notes_parts.append(f"\n{user_notes}")

    return "\n".join(notes_parts)


def _sets_from_movement_log(
    log: dict,
    resolver: LegacyExerciseResolver,
    session_id: str,
    *,
    program_id: str | None,
    created_at: str,
    start_ordinal: int,
) -> tuple[list[WorkoutSet], int]:
    exercise_id = resolver.resolve(log, program_id=program_id)
    form_quality = log.get("form_quality")
    fq = int(form_quality) if _is_numeric(form_quality) else None
    reps_list = _normalize_reps_per_set(log.get("reps_per_set"))
    hold = log.get("hold_seconds")
    sets_out: list[WorkoutSet] = []
    ordinal = start_ordinal

    if reps_list:
        for rep in reps_list:
            sets_out.append(
                WorkoutSet(
                    session_id=session_id,
                    exercise_id=exercise_id,
                    reps=int(rep),
                    hold_seconds=None,
                    form_quality=fq,
                    ordinal=ordinal,
                    created_at=created_at,
                )
            )
            ordinal += 1
    elif _is_numeric(hold):
        sets_out.append(
            WorkoutSet(
                session_id=session_id,
                exercise_id=exercise_id,
                hold_seconds=float(hold),
                form_quality=fq,
                ordinal=ordinal,
                created_at=created_at,
            )
        )
        ordinal += 1
    return sets_out, ordinal


def _insert_workout_sets(conn: sqlite3.Connection, workout_sets: list[WorkoutSet]) -> None:
    for workout_set in workout_sets:
        conn.execute(
            """
            INSERT INTO workout_sets (
                id, session_id, exercise_id, sets, reps, hold_seconds,
                weight_kg, form_quality, ordinal, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workout_set.id,
                workout_set.session_id,
                workout_set.exercise_id,
                workout_set.sets,
                workout_set.reps,
                workout_set.hold_seconds,
                workout_set.weight_kg,
                workout_set.form_quality,
                workout_set.ordinal,
                workout_set.created_at,
            ),
        )


def _legacy_session_id_for_hash(conn: sqlite3.Connection, source_hash: str) -> str | None:
    marker = f"[LEGACY:{source_hash}]"
    row = conn.execute(
        """
        SELECT id FROM workout_sessions
        WHERE notes LIKE ?
        ORDER BY date DESC, id DESC
        LIMIT 1
        """,
        (f"{marker}%",),
    ).fetchone()
    return row["id"] if row else None


def _session_workout_set_count(conn: sqlite3.Connection, session_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM workout_sets WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return int(row["c"]) if row else 0


def insert_legacy_workout_sets_for_session(
    conn: sqlite3.Connection,
    resolver: LegacyExerciseResolver,
    sess: dict,
    session_id: str,
) -> int:
    """Insert workout_sets for a migrated legacy session when none exist yet."""
    if _session_workout_set_count(conn, session_id) > 0:
        return 0
    movement_logs = sess.get("movement_logs") or []
    if not movement_logs:
        return 0
    program_id = sess.get("program_id", sess.get("program"))
    session_date = sess.get("date") or ""
    created_at = f"{session_date}T12:00:00" if session_date else datetime.now().isoformat()
    ordinal = 0
    all_sets: list[WorkoutSet] = []
    for log in movement_logs:
        if not isinstance(log, dict):
            continue
        batch, ordinal = _sets_from_movement_log(
            log,
            resolver,
            session_id,
            program_id=program_id if isinstance(program_id, str) else None,
            created_at=created_at,
            start_ordinal=ordinal,
        )
        all_sets.extend(batch)
    if not all_sets:
        return 0
    _insert_workout_sets(conn, all_sets)
    return len(all_sets)


def _sessions_needing_legacy_set_backfill(
    sessions: list[Any], conn: sqlite3.Connection
) -> list[tuple[dict, str]]:
    pending: list[tuple[dict, str]] = []
    for sess in sessions:
        if not isinstance(sess, dict):
            continue
        movement_logs = sess.get("movement_logs") or []
        if not movement_logs:
            continue
        source_hash = legacy_source_hash(sess)
        session_id = _legacy_session_id_for_hash(conn, source_hash)
        if not session_id:
            continue
        if _session_workout_set_count(conn, session_id) > 0:
            continue
        pending.append((sess, session_id))
    return pending


def backfill_legacy_workout_sets(
    sessions: list[dict],
    repo: FitnessRepository,
) -> dict[str, int]:
    """One-time backfill of workout_sets for sessions already in fitness.db (#191)."""
    repo.initialize()
    validation_errors = collect_legacy_session_errors(sessions)
    if validation_errors:
        raise LegacyMigrationValidationError(validation_errors)

    inserted = 0
    with repo.connect(timeout=10.0) as conn:
        pending = _sessions_needing_legacy_set_backfill(sessions, conn)
        if not pending:
            return {"sets_inserted": 0, "sessions_updated": 0}

        resolver = LegacyExerciseResolver(conn)
        try:
            for sess, session_id in pending:
                inserted += insert_legacy_workout_sets_for_session(
                    conn, resolver, sess, session_id
                )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise Exception(f"Legacy set backfill failed: {e}") from e

    return {
        "sets_inserted": inserted,
        "sessions_updated": len(pending),
    }


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

    validation_errors = collect_legacy_session_errors(legacy_sessions)
    if validation_errors:
        raise LegacyMigrationValidationError(validation_errors)

    repo.initialize()

    with repo.connect(timeout=10.0) as conn:
        existing_hashes = _existing_legacy_hashes(conn)

        sessions_to_flag: list[dict] = []

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
                result["migrated_count"] += 1
            result["sessions_to_flag"] = sessions_to_flag
            return result

        resolver = LegacyExerciseResolver(conn)
        try:
            for sess in legacy_sessions:
                if sess.get("migrated_to_fitness_db"):
                    result["skipped_count"] += 1
                    continue

                source_hash = legacy_source_hash(sess)
                if source_hash in existing_hashes:
                    session_id = _legacy_session_id_for_hash(conn, source_hash)
                    if session_id:
                        insert_legacy_workout_sets_for_session(
                            conn, resolver, sess, session_id
                        )
                    result["skipped_count"] += 1
                    sessions_to_flag.append(sess)
                    continue

                date = sess.get("date")
                duration = sess.get("duration_min", sess.get("duration_minutes"))
                notes = build_legacy_session_notes(
                    sess,
                    source_hash,
                    include_free_text_notes=include_free_text_notes,
                )

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
                insert_legacy_workout_sets_for_session(
                    conn, resolver, sess, session.id
                )

                result["migrated_count"] += 1
                result["session_ids"].append(session.id)
                existing_hashes.add(source_hash)
                sessions_to_flag.append(sess)

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
    app_settings: dict | None = None,
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
    needs_insert = plan["migrated_count"] > 0
    needs_flag = bool(plan.get("sessions_to_flag"))
    needs_set_backfill = legacy_movement_sets_backfill_pending(app_settings)
    if not needs_insert and not needs_flag and not needs_set_backfill:
        return {
            **plan,
            "flagged_count": 0,
            "backed_up": False,
        }

    data_backup: str | None = None
    db_backup: str | None = None
    data_dir = os.path.dirname(os.path.abspath(data_path))
    try:
        if needs_insert:
            data_backup, db_backup = backup_files_for_migration(data_path, fitness_db_path)
        else:
            prune_migration_backups(data_dir)
        if needs_insert or needs_flag:
            result = migrate_legacy_sessions(
                data,
                repo,
                dry_run=False,
                include_free_text_notes=include_free_text_notes,
            )
            flagged = apply_migrated_flags(sessions, result.get("sessions_to_flag", []))
            result["flagged_count"] = flagged
        else:
            result = {**plan, "flagged_count": 0}
        if needs_set_backfill and app_settings is not None:
            backfill = backfill_legacy_workout_sets(sessions, repo)
            result["sets_backfilled"] = backfill.get("sets_inserted", 0)
            mark_legacy_movement_sets_version_done(app_settings)
        elif app_settings is not None and (needs_insert or needs_flag):
            mark_legacy_movement_sets_version_done(app_settings)
        result["backed_up"] = needs_insert
        if needs_insert:
            result["data_backup"] = data_backup
            result["db_backup"] = db_backup
        return result
    except LegacyMigrationValidationError:
        raise
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
