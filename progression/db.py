import json
import os
import sqlite3

import storage
import profiles
from progression.models import (
    BodyCompositionLog,
    Exercise,
    ProgressionEdge,
    UserExerciseProgress,
    WorkoutSession,
    WorkoutSet,
)
from progression.validate import ProgressionCycleError, would_create_cycle

FITNESS_DB_NAME = "fitness.db"


def get_fitness_db_path(profile_id: str | None = None) -> str:
    if profile_id:
        return os.path.join(profiles.get_profile_dir(profile_id), FITNESS_DB_NAME)
    try:
        from paths import ensure_data_file

        base = os.path.dirname(ensure_data_file())
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, FITNESS_DB_NAME)
    except ImportError:
        return os.path.join(storage.get_data_dir(), FITNESS_DB_NAME)


class FitnessRepository:
    def __init__(self, db_path: str | None = None, fitness_settings: dict | None = None):
        self.db_path = db_path or get_fitness_db_path()
        self.fitness_settings = fitness_settings

    def connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS exercises (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_book TEXT NOT NULL,
                    family TEXT NOT NULL,
                    mastery_criteria TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    deleted_at TEXT
                );

                CREATE TABLE IF NOT EXISTS progression_edges (
                    id TEXT PRIMARY KEY,
                    from_exercise_id TEXT NOT NULL,
                    to_exercise_id TEXT NOT NULL,
                    edge_type TEXT NOT NULL DEFAULT 'prerequisite'
                        CHECK (edge_type IN ('prerequisite', 'recommended', 'alternative')),
                    unlock_condition TEXT NOT NULL,
                    FOREIGN KEY (from_exercise_id) REFERENCES exercises(id),
                    FOREIGN KEY (to_exercise_id) REFERENCES exercises(id)
                );

                CREATE INDEX IF NOT EXISTS idx_progression_edges_from
                    ON progression_edges(from_exercise_id);
                CREATE INDEX IF NOT EXISTS idx_progression_edges_to
                    ON progression_edges(to_exercise_id);

                CREATE TABLE IF NOT EXISTS user_exercise_progress (
                    exercise_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'locked'
                        CHECK (status IN ('locked', 'available', 'in_progress', 'mastered')),
                    current_step INTEGER,
                    best_reps INTEGER,
                    best_hold_time REAL,
                    best_weight REAL,
                    last_logged_at TEXT,
                    achieved_at TEXT,
                    FOREIGN KEY (exercise_id) REFERENCES exercises(id)
                );

                CREATE TABLE IF NOT EXISTS workout_sessions (
                    id TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    duration_minutes INTEGER,
                    body_weight_kg REAL
                );

                CREATE INDEX IF NOT EXISTS idx_workout_sessions_date
                    ON workout_sessions(date);

                CREATE TABLE IF NOT EXISTS workout_sets (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    exercise_id TEXT NOT NULL,
                    sets INTEGER,
                    reps INTEGER,
                    hold_seconds REAL,
                    weight_kg REAL,
                    FOREIGN KEY (session_id) REFERENCES workout_sessions(id),
                    FOREIGN KEY (exercise_id) REFERENCES exercises(id)
                );

                CREATE INDEX IF NOT EXISTS idx_workout_sets_session
                    ON workout_sets(session_id);

                CREATE TABLE IF NOT EXISTS body_composition_logs (
                    id TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    weight_kg REAL,
                    measurements TEXT NOT NULL DEFAULT '{}',
                    photo_path TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_body_composition_date
                    ON body_composition_logs(date);
                """
            )
            self._ensure_workout_set_form_quality_column(conn)

    def _ensure_workout_set_form_quality_column(self, conn: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(workout_sets)").fetchall()
        }
        if "form_quality" not in columns:
            conn.execute("ALTER TABLE workout_sets ADD COLUMN form_quality INTEGER")

    def add_exercise(self, exercise: Exercise) -> Exercise:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
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
        return exercise

    def get_exercise(self, exercise_id: str) -> Exercise | None:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, name, source_book, family, mastery_criteria, metadata
                FROM exercises
                WHERE id = ? AND deleted_at IS NULL
                """,
                (exercise_id,),
            ).fetchone()
        if row is None:
            return None
        return Exercise(
            id=row["id"],
            name=row["name"],
            source_book=row["source_book"],
            family=row["family"],
            mastery_criteria=json.loads(row["mastery_criteria"]),
            metadata=json.loads(row["metadata"]),
        )

    def list_exercises(self) -> list[Exercise]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, source_book, family, mastery_criteria, metadata
                FROM exercises
                WHERE deleted_at IS NULL
                ORDER BY source_book, family, name
                """
            ).fetchall()
        return [
            Exercise(
                id=row["id"],
                name=row["name"],
                source_book=row["source_book"],
                family=row["family"],
                mastery_criteria=json.loads(row["mastery_criteria"]),
                metadata=json.loads(row["metadata"]),
            )
            for row in rows
        ]

    def add_edge(self, edge: ProgressionEdge) -> ProgressionEdge:
        self.initialize()
        with self.connect() as conn:
            if edge.edge_type == "prerequisite" and would_create_cycle(
                conn,
                edge.from_exercise_id,
                edge.to_exercise_id,
            ):
                raise ProgressionCycleError(
                    f"Adding {edge.from_exercise_id} -> {edge.to_exercise_id} would create a cycle"
                )
            conn.execute(
                """
                INSERT INTO progression_edges (
                    id, from_exercise_id, to_exercise_id, edge_type, unlock_condition
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    edge.id,
                    edge.from_exercise_id,
                    edge.to_exercise_id,
                    edge.edge_type,
                    json.dumps(edge.unlock_condition),
                ),
            )
        return edge

    def list_edges(self, edge_type: str | None = None) -> list[ProgressionEdge]:
        self.initialize()
        query = """
            SELECT id, from_exercise_id, to_exercise_id, edge_type, unlock_condition
            FROM progression_edges
        """
        params: tuple[str, ...] = ()
        if edge_type is not None:
            query += " WHERE edge_type = ?"
            params = (edge_type,)
        query += " ORDER BY from_exercise_id, to_exercise_id"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            ProgressionEdge(
                id=row["id"],
                from_exercise_id=row["from_exercise_id"],
                to_exercise_id=row["to_exercise_id"],
                edge_type=row["edge_type"],
                unlock_condition=json.loads(row["unlock_condition"]),
            )
            for row in rows
        ]

    def list_outgoing_edges(self, exercise_id: str) -> list[ProgressionEdge]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, from_exercise_id, to_exercise_id, edge_type, unlock_condition
                FROM progression_edges
                WHERE from_exercise_id = ?
                ORDER BY edge_type, to_exercise_id
                """,
                (exercise_id,),
            ).fetchall()
        return [
            ProgressionEdge(
                id=row["id"],
                from_exercise_id=row["from_exercise_id"],
                to_exercise_id=row["to_exercise_id"],
                edge_type=row["edge_type"],
                unlock_condition=json.loads(row["unlock_condition"]),
            )
            for row in rows
        ]

    def get_user_progress(self, exercise_id: str) -> UserExerciseProgress | None:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT exercise_id, status, current_step, best_reps, best_hold_time,
                       best_weight, last_logged_at, achieved_at
                FROM user_exercise_progress
                WHERE exercise_id = ?
                """,
                (exercise_id,),
            ).fetchone()
        if row is None:
            return None
        return UserExerciseProgress(
            exercise_id=row["exercise_id"],
            status=row["status"],
            current_step=row["current_step"],
            best_reps=row["best_reps"],
            best_hold_time=row["best_hold_time"],
            best_weight=row["best_weight"],
            last_logged_at=row["last_logged_at"],
            achieved_at=row["achieved_at"],
        )

    def upsert_user_progress(self, progress: UserExerciseProgress) -> UserExerciseProgress:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO user_exercise_progress (
                    exercise_id, status, current_step, best_reps, best_hold_time,
                    best_weight, last_logged_at, achieved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(exercise_id) DO UPDATE SET
                    status = excluded.status,
                    current_step = excluded.current_step,
                    best_reps = excluded.best_reps,
                    best_hold_time = excluded.best_hold_time,
                    best_weight = excluded.best_weight,
                    last_logged_at = excluded.last_logged_at,
                    achieved_at = excluded.achieved_at
                """,
                (
                    progress.exercise_id,
                    progress.status,
                    progress.current_step,
                    progress.best_reps,
                    progress.best_hold_time,
                    progress.best_weight,
                    progress.last_logged_at,
                    progress.achieved_at,
                ),
            )
        return progress

    def edge_exists(
        self,
        from_exercise_id: str,
        to_exercise_id: str,
        edge_type: str,
    ) -> bool:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM progression_edges
                WHERE from_exercise_id = ? AND to_exercise_id = ? AND edge_type = ?
                """,
                (from_exercise_id, to_exercise_id, edge_type),
            ).fetchone()
        return row is not None

    def list_incoming_edges(self, exercise_id: str) -> list[ProgressionEdge]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, from_exercise_id, to_exercise_id, edge_type, unlock_condition
                FROM progression_edges
                WHERE to_exercise_id = ?
                ORDER BY edge_type, from_exercise_id
                """,
                (exercise_id,),
            ).fetchall()
        return [
            ProgressionEdge(
                id=row["id"],
                from_exercise_id=row["from_exercise_id"],
                to_exercise_id=row["to_exercise_id"],
                edge_type=row["edge_type"],
                unlock_condition=json.loads(row["unlock_condition"]),
            )
            for row in rows
        ]

    def delete_prerequisite_edges_among(self, exercise_ids: set[str]) -> int:
        if not exercise_ids:
            return 0
        self.initialize()
        placeholders = ",".join("?" for _ in exercise_ids)
        params = tuple(exercise_ids)
        with self.connect() as conn:
            cursor = conn.execute(
                f"""
                DELETE FROM progression_edges
                WHERE edge_type = 'prerequisite'
                  AND from_exercise_id IN ({placeholders})
                  AND to_exercise_id IN ({placeholders})
                """,
                params + params,
            )
            return cursor.rowcount

    def update_exercise_metadata(self, exercise_id: str, metadata: dict) -> None:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE exercises
                SET metadata = ?
                WHERE id = ? AND deleted_at IS NULL
                """,
                (json.dumps(metadata), exercise_id),
            )

    def add_workout_session(self, session: WorkoutSession) -> WorkoutSession:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO workout_sessions (id, date, notes, duration_minutes, body_weight_kg)
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
        return session

    def add_workout_set(self, workout_set: WorkoutSet) -> WorkoutSet:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO workout_sets (
                    id, session_id, exercise_id, sets, reps, hold_seconds, weight_kg, form_quality
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
        return workout_set

    def workout_session_exists(self, session_id: str) -> bool:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM workout_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return row is not None

    def has_workout_set(self, session_id: str, exercise_id: str) -> bool:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM workout_sets
                WHERE session_id = ? AND exercise_id = ?
                """,
                (session_id, exercise_id),
            ).fetchone()
        return row is not None

    def list_workout_sessions(self, limit: int = 50) -> list[WorkoutSession]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, date, notes, duration_minutes, body_weight_kg
                FROM workout_sessions
                ORDER BY date DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            WorkoutSession(
                id=row["id"],
                date=row["date"],
                notes=row["notes"],
                duration_minutes=row["duration_minutes"],
                body_weight_kg=row["body_weight_kg"],
            )
            for row in rows
        ]

    def list_workout_sets(self, session_id: str) -> list[WorkoutSet]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, exercise_id, sets, reps, hold_seconds, weight_kg, form_quality
                FROM workout_sets
                WHERE session_id = ?
                ORDER BY id
                """,
                (session_id,),
            ).fetchall()
        return [
            WorkoutSet(
                id=row["id"],
                session_id=row["session_id"],
                exercise_id=row["exercise_id"],
                sets=row["sets"],
                reps=row["reps"],
                hold_seconds=row["hold_seconds"],
                weight_kg=row["weight_kg"],
                form_quality=row["form_quality"],
            )
            for row in rows
        ]

    def add_body_composition_log(self, log: BodyCompositionLog) -> BodyCompositionLog:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO body_composition_logs (id, date, weight_kg, measurements, photo_path)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    log.id,
                    log.date,
                    log.weight_kg,
                    json.dumps(log.measurements),
                    log.photo_path,
                ),
            )
        return log

    def list_body_composition_logs(self, limit: int = 50) -> list[BodyCompositionLog]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, date, weight_kg, measurements, photo_path
                FROM body_composition_logs
                ORDER BY date DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            BodyCompositionLog(
                id=row["id"],
                date=row["date"],
                weight_kg=row["weight_kg"],
                measurements=json.loads(row["measurements"]),
                photo_path=row["photo_path"],
            )
            for row in rows
        ]
