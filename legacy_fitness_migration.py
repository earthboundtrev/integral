"""Migrate legacy data.json fitness sessions to fitness.db.

Per issue #116: idempotent, backed up, tested migration of program-based sessions
from data.json into the new workout_sessions/workout_sets SQLite schema.
"""

import json
import os
import shutil
from datetime import datetime
from typing import Any

from progression.db import FitnessRepository
from progression.models import WorkoutSession, WorkoutSet


def backup_files_for_migration(data_path: str, db_path: str) -> tuple[str, str]:
    """Create timestamped backups of data.json and fitness.db before migration.
    
    Returns:
        (data_backup_path, db_backup_path)
    
    Raises:
        Exception if backup fails
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Backup data.json
    data_backup = f"{data_path}.migration_backup_{timestamp}"
    try:
        shutil.copy2(data_path, data_backup)
    except Exception as e:
        raise Exception(f"Failed to backup data.json: {e}")
    
    # Backup fitness.db if it exists
    db_backup = None
    if os.path.exists(db_path):
        db_backup = f"{db_path}.migration_backup_{timestamp}"
        try:
            shutil.copy2(db_path, db_backup)
        except Exception as e:
            # Clean up data backup if DB backup fails
            try:
                os.remove(data_backup)
            except Exception:
                pass
            raise Exception(f"Failed to backup fitness.db: {e}")
    
    return (data_backup, db_backup)


def migrate_legacy_sessions(
    data: dict,
    repo: FitnessRepository,
    dry_run: bool = False
) -> dict[str, Any]:
    """Migrate legacy data.json 'sessions' to fitness.db workout_sessions/workout_sets.
    
    Real program sessions use: date, program_id, movement_logs, notes, session_rpe, duration_min.
    
    Args:
        data: Loaded data.json dict
        repo: FitnessRepository
        dry_run: If True, return what would be migrated without writing
    
    Returns:
        Dict with keys:
            - migrated_count: int
            - skipped_count: int  
            - errors: list of error messages
            - session_ids: list of migrated session IDs
    """
    import hashlib
    
    legacy_sessions = data.get("sessions", [])
    
    result = {
        "migrated_count": 0,
        "skipped_count": 0,
        "errors": [],
        "session_ids": [],
    }
    
    if not legacy_sessions:
        return result
    
    repo.initialize()
    
    with repo.connect(timeout=10.0) as conn:
        # Get existing legacy_source_hash to check for duplicates (stable idempotency)
        existing = conn.execute(
            "SELECT notes FROM workout_sessions WHERE notes LIKE '[LEGACY:%'"
        ).fetchall()
        existing_hashes = {
            row["notes"].split("[LEGACY:")[1].split("]")[0]
            for row in existing
            if "[LEGACY:" in row["notes"]
        }
        
        if dry_run:
            for sess in legacy_sessions:
                source_hash = hashlib.sha256(
                    json.dumps(sess, sort_keys=True).encode()
                ).hexdigest()[:12]
                if source_hash not in existing_hashes:
                    result["migrated_count"] += 1
                else:
                    result["skipped_count"] += 1
            return result
        
        # Single transaction for all sessions
        try:
            for sess in legacy_sessions:
                try:
                    # Stable idempotency key: hash of the legacy session dict
                    source_hash = hashlib.sha256(
                        json.dumps(sess, sort_keys=True).encode()
                    ).hexdigest()[:12]
                    
                    if source_hash in existing_hashes:
                        result["skipped_count"] += 1
                        continue
                    
                    date = sess.get("date")
                    if not date:
                        result["errors"].append(f"Session missing date: {sess}")
                        result["skipped_count"] += 1
                        continue
                    
                    # Build notes with program, RPE, duration, and movements
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
                            movement_name = log.get("movement_name") or log.get("chain_name") or log.get("movement_key", "")
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
                    
                    user_notes = sess.get("notes", "")
                    if user_notes:
                        notes_parts.append(f"\n{user_notes}")
                    
                    notes = "\n".join(notes_parts)
                    
                    # Create workout session (using repo methods which handle their own connections)
                    # Note: This is still not fully transactional due to repo.add_workout_session
                    # opening its own connection. For true atomicity, would need to refactor
                    # repo methods to accept a connection parameter.
                    session = WorkoutSession(
                        date=date,
                        notes=notes,
                        duration_minutes=duration if isinstance(duration, int) else None,
                        body_weight_kg=None,
                    )
                    
                    # For true transaction, insert directly via this connection
                    conn.execute(
                        """
                        INSERT INTO workout_sessions (id, date, notes, duration_minutes, body_weight_kg)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (session.id, session.date, session.notes, session.duration_minutes, session.body_weight_kg)
                    )
                    
                    result["migrated_count"] += 1
                    result["session_ids"].append(session.id)
                    existing_hashes.add(source_hash)
                    
                except Exception as e:
                    result["errors"].append(f"Error migrating session {sess.get('date', 'unknown')}: {e}")
                    result["skipped_count"] += 1
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Migration transaction failed: {e}")
    
    return result


def mark_migrated_in_data_json(data_path: str) -> None:
    """Mark sessions in data.json as migrated (add flag, don't delete).
    
    Modifies data.json to add a 'migrated_to_fitness_db' flag to each session.
    """
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        sessions = data.get("sessions", [])
        for sess in sessions:
            if "migrated_to_fitness_db" not in sess:
                sess["migrated_to_fitness_db"] = datetime.now().isoformat()
        
        # Atomic write
        temp_path = f"{data_path}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        os.replace(temp_path, data_path)
        
    except Exception as e:
        raise Exception(f"Failed to mark sessions as migrated: {e}")


def run_migration(data_path: str, fitness_db_path: str, mark_migrated: bool = True) -> dict[str, Any]:
    """Run the complete migration with backup.
    
    Args:
        data_path: Path to data.json
        fitness_db_path: Path to fitness.db
        mark_migrated: If True, mark sessions in data.json as migrated
    
    Returns:
        Migration result dict with counts and errors
    
    Raises:
        Exception if backup or migration fails
    """
    # Step 1: Backup
    data_backup, db_backup = backup_files_for_migration(data_path, fitness_db_path)
    
    try:
        # Step 2: Load data.json
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Step 3: Migrate
        repo = FitnessRepository(db_path=fitness_db_path)
        result = migrate_legacy_sessions(data, repo, dry_run=False)
        
        # Step 4: Mark as migrated (optional)
        if mark_migrated and result["migrated_count"] > 0:
            try:
                mark_migrated_in_data_json(data_path)
            except Exception as e:
                result["errors"].append(f"Warning: Failed to mark sessions as migrated: {e}")
        
        return result
        
    except Exception as e:
        # Migration failed - backups are preserved
        raise Exception(f"Migration failed (backups preserved at {data_backup}, {db_backup}): {e}")
