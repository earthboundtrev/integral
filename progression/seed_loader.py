import json

import paths
from progression.db import FitnessRepository
from progression.models import ProgressionEdge
from progression.validate import ProgressionCycleError, would_create_cycle

SEED_DIR = paths.app_resource("progression", "seed", "v1")
STEP_PROGRESSION_SEQUENTIAL = "sequential"
STEP_PROGRESSION_PARALLEL = "parallel"


def load_seed_file(filename: str) -> dict:
    path = SEED_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_seed_files() -> list[str]:
    files = sorted(
        path.name
        for path in SEED_DIR.glob("*.json")
        if path.name not in {"cross_links.json", "exercise_videos.json"}
    )
    files.append("cross_links.json")
    return files


def seed_step_progression(payload: dict) -> str:
    value = payload.get("step_progression", STEP_PROGRESSION_SEQUENTIAL)
    if value not in {STEP_PROGRESSION_SEQUENTIAL, STEP_PROGRESSION_PARALLEL}:
        raise ValueError(f"Invalid step_progression in seed: {value}")
    return value


def _resolve_exercise_id(repo: FitnessRepository, key: str, key_to_id: dict[str, str]) -> str | None:
    if key in key_to_id:
        return key_to_id[key]
    exercise = repo.get_exercise(key)
    return exercise.id if exercise else None


def _exercise_metadata(payload: dict, item: dict, filename: str) -> dict:
    return {
        "seed_key": item["key"],
        "step": item.get("step"),
        "seed_version": payload["version"],
        "seed_file": filename,
        "step_progression": seed_step_progression(payload),
    }


def apply_step_progression_policy(
    repo: FitnessRepository,
    payload: dict,
    key_to_id: dict[str, str],
) -> None:
    """Enforce parallel vs sequential unlock rules from the seed dataset."""
    if seed_step_progression(payload) != STEP_PROGRESSION_PARALLEL:
        return
    repo.delete_prerequisite_edges_among(set(key_to_id.values()))


def seed_from_file(
    repo: FitnessRepository,
    filename: str,
    force: bool = False,
) -> dict[str, str]:
    """Load one seed file. Returns map of seed key -> exercise id.

    Uses one SQLite connection/transaction so seeding many ladders stays fast.
    """
    payload = load_seed_file(filename)
    key_to_id: dict[str, str] = {}
    step_progression = seed_step_progression(payload)
    repo.initialize()

    with repo.connect() as conn:
        for item in payload.get("exercises", []):
            key = item["key"]
            metadata = _exercise_metadata(payload, item, filename)
            row = conn.execute(
                """
                SELECT id FROM exercises
                WHERE id = ? AND deleted_at IS NULL
                """,
                (key,),
            ).fetchone()
            if row and not force:
                conn.execute(
                    """
                    UPDATE exercises
                    SET metadata = ?
                    WHERE id = ? AND deleted_at IS NULL
                    """,
                    (json.dumps(metadata), key),
                )
                key_to_id[key] = row["id"]
                continue

            conn.execute(
                """
                INSERT INTO exercises (
                    id, name, source_book, family, mastery_criteria, metadata
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    item["name"],
                    payload["source_book"],
                    payload["family"],
                    json.dumps(item["mastery_criteria"]),
                    json.dumps(metadata),
                ),
            )
            key_to_id[key] = key

        if step_progression == STEP_PROGRESSION_SEQUENTIAL:
            for edge in payload.get("edges", []):
                from_key = edge["from"]
                to_key = edge["to"]
                from_id = key_to_id.get(from_key)
                to_id = key_to_id.get(to_key)
                if from_id is None or to_id is None:
                    # Cross-file keys (e.g. recommended edges): resolve from DB
                    if from_id is None:
                        row = conn.execute(
                            "SELECT id FROM exercises WHERE id = ? AND deleted_at IS NULL",
                            (from_key,),
                        ).fetchone()
                        from_id = row["id"] if row else None
                    if to_id is None:
                        row = conn.execute(
                            "SELECT id FROM exercises WHERE id = ? AND deleted_at IS NULL",
                            (to_key,),
                        ).fetchone()
                        to_id = row["id"] if row else None
                if from_id is None or to_id is None:
                    continue
                edge_type = edge.get("edge_type", "prerequisite")
                exists = conn.execute(
                    """
                    SELECT 1 FROM progression_edges
                    WHERE from_exercise_id = ? AND to_exercise_id = ? AND edge_type = ?
                    """,
                    (from_id, to_id, edge_type),
                ).fetchone()
                if exists:
                    continue
                if edge_type == "prerequisite" and would_create_cycle(conn, from_id, to_id):
                    raise ProgressionCycleError(
                        f"Adding {from_id} -> {to_id} would create a cycle"
                    )
                edge_model = ProgressionEdge(
                    from_exercise_id=from_id,
                    to_exercise_id=to_id,
                    edge_type=edge_type,
                    unlock_condition=edge["unlock_condition"],
                )
                conn.execute(
                    """
                    INSERT INTO progression_edges (
                        id, from_exercise_id, to_exercise_id, edge_type, unlock_condition
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        edge_model.id,
                        edge_model.from_exercise_id,
                        edge_model.to_exercise_id,
                        edge_model.edge_type,
                        json.dumps(edge_model.unlock_condition),
                    ),
                )

    apply_step_progression_policy(repo, payload, key_to_id)
    return key_to_id


def seed_all_fitness(repo: FitnessRepository, force: bool = False) -> dict[str, str]:
    """Load all fitness seed files. Returns combined seed key -> exercise id map."""
    combined: dict[str, str] = {}
    for filename in list_seed_files():
        combined.update(seed_from_file(repo, filename, force=force))
    return combined


def seed_cc1_push(repo: FitnessRepository, force: bool = False) -> dict[str, str]:
    """Load CC1 push progression. Returns map of seed key -> exercise id."""
    return seed_from_file(repo, "cc1_push.json", force=force)
