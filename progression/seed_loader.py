import json
from pathlib import Path

import paths
from progression.db import FitnessRepository
from progression.models import Exercise, ProgressionEdge

SEED_DIR = paths.app_resource("progression", "seed", "v1")


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


def _resolve_exercise_id(repo: FitnessRepository, key: str, key_to_id: dict[str, str]) -> str | None:
    if key in key_to_id:
        return key_to_id[key]
    exercise = repo.get_exercise(key)
    return exercise.id if exercise else None


def seed_from_file(
    repo: FitnessRepository,
    filename: str,
    force: bool = False,
) -> dict[str, str]:
    """Load one seed file. Returns map of seed key -> exercise id."""
    payload = load_seed_file(filename)
    key_to_id: dict[str, str] = {}

    for item in payload.get("exercises", []):
        key = item["key"]
        existing = repo.get_exercise(key)
        if existing and not force:
            key_to_id[key] = existing.id
            continue

        exercise = repo.add_exercise(
            Exercise(
                id=key,
                name=item["name"],
                source_book=payload["source_book"],
                family=payload["family"],
                mastery_criteria=item["mastery_criteria"],
                metadata={
                    "seed_key": key,
                    "step": item.get("step"),
                    "seed_version": payload["version"],
                    "seed_file": filename,
                },
            )
        )
        key_to_id[key] = exercise.id

    for edge in payload.get("edges", []):
        from_id = _resolve_exercise_id(repo, edge["from"], key_to_id)
        to_id = _resolve_exercise_id(repo, edge["to"], key_to_id)
        if from_id is None or to_id is None:
            continue
        edge_type = edge.get("edge_type", "prerequisite")
        if repo.edge_exists(from_id, to_id, edge_type):
            continue
        repo.add_edge(
            ProgressionEdge(
                from_exercise_id=from_id,
                to_exercise_id=to_id,
                edge_type=edge_type,
                unlock_condition=edge["unlock_condition"],
            )
        )

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
