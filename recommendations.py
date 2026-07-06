"""Local rule-based recommendations — no cloud or LLM."""

from datetime import datetime
from typing import Any

from progression.db import FitnessRepository


def build_recommendations(
    entries: dict[str, Any],
    categories: dict[str, Any],
    repo: FitnessRepository | None = None,
) -> list[str]:
    recs: list[str] = []
    today = datetime.now().strftime("%Y-%m-%d")
    today_entries = entries.get(today, {})

    today_recs = []
    for cat_name in categories:
        if cat_name not in today_entries:
            today_recs.append(f"Log today's entry for {cat_name}.")
    recs.extend(today_recs[:3])

    if repo is not None:
        repo.initialize()
        available = []
        in_progress = []
        for exercise in repo.list_exercises():
            progress = repo.get_user_progress(exercise.id)
            status = progress.status if progress else "locked"
            if status == "available":
                available.append(exercise.name)
            elif status == "in_progress":
                in_progress.append(exercise.name)

        for name in available[:3]:
            recs.append(f"Fitness: try {name} — it's unlocked and ready.")
        for name in in_progress[:2]:
            recs.append(f"Fitness: keep working on {name}.")

        if not available and not in_progress and repo.list_exercises():
            first = min(
                repo.list_exercises(),
                key=lambda ex: (ex.metadata.get("step") or 999, ex.name),
            )
            recs.append(f"Fitness: start with {first.name} to begin your progression.")

    low_cats = []
    for cat_name in categories:
        ratings = [
            day[cat_name].get("rating", 0)
            for day in entries.values()
            if cat_name in day and isinstance(day[cat_name].get("rating"), int | float)
        ]
        if ratings:
            avg = sum(ratings) / len(ratings)
            if avg < 5:
                low_cats.append((cat_name, avg))
    for cat_name, avg in sorted(low_cats, key=lambda item: item[1])[:2]:
        recs.append(f"Focus on {cat_name} — average rating is {avg:.1f}/10.")

    if not recs:
        recs.append("You're on track today — keep the momentum going.")

    return recs[:8]
