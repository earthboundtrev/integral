"""Fitness Hub settings stored in Integral data.json under settings.fitness."""

from __future__ import annotations

from progression.seed_loader import STEP_PROGRESSION_SEQUENTIAL

PLACEMENT_WARNING = (
    "Integral tracks honest progression. Skipping steps you have not earned weakens "
    "the guidance this app gives you and increases injury risk. Only set a higher "
    "starting step if you already have real training history at that level."
)

LOCK_BYPASS_WARNING = (
    "Turning off progression locks lets you log any step immediately. This is for "
    "experienced athletes importing prior logs — not for rushing ahead before your "
    "body is ready."
)


def default_fitness_settings() -> dict:
    return {
        "tibetan_advance_consecutive_days": 7,
        "cc_sessions_for_advance": 2,
        "cc_min_form_quality": 7,
        "disable_progression_locks": False,
        "manual_placement_enabled": True,
        "placements": {},
    }


def get_fitness_settings(settings: dict | None) -> dict:
    merged = default_fitness_settings()
    if not settings:
        return merged
    if "fitness" in settings:
        stored = settings.get("fitness") or {}
    else:
        stored = settings
    if isinstance(stored, dict):
        merged.update({key: stored[key] for key in stored if key in merged or key == "placements"})
    placements = stored.get("placements") if isinstance(stored, dict) else None
    if isinstance(placements, dict):
        merged["placements"] = {str(key): int(value) for key, value in placements.items()}
    return merged


def is_sequential_exercise(exercise) -> bool:
    return exercise.metadata.get("step_progression") == STEP_PROGRESSION_SEQUENTIAL


def progression_locks_enabled(fitness_settings: dict | None) -> bool:
    return not bool(get_fitness_settings(fitness_settings).get("disable_progression_locks"))
