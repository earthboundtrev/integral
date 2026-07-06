"""Group fitness exercises into expandable program series."""

from __future__ import annotations

from progression.db import FitnessRepository

STATUS_PRIORITY = {
    "in_progress": 0,
    "available": 1,
    "mastered": 2,
    "locked": 3,
}

BOOK_LABELS = {
    "CC1": "Convict Conditioning 1",
    "CC2": "Convict Conditioning 2",
    "OG": "Overcoming Gravity",
    "SS": "Starting Strength",
    "EC": "Explosive Calisthenics",
    "FTR": "Five Tibetan Rites",
}

FAMILY_LABELS = {
    "push": "Push",
    "pull": "Pull",
    "squat": "Squat",
    "leg_raise": "Leg Raises",
    "bridge": "Bridge",
    "handstand_pushup": "Handstand Push-up",
    "main": "Main Lifts",
    "explosive": "Explosive Push",
    "rites": "Daily Rites",
}


def format_family_label(family: str) -> str:
    return FAMILY_LABELS.get(family, family.replace("_", " ").title())


def format_program_title(source_book: str, family: str) -> str:
    book = BOOK_LABELS.get(source_book, source_book)
    family_label = format_family_label(family)
    return f"{source_book} · {family_label}"


def format_program_summary(steps: list[dict]) -> str:
    current = pick_current_step(steps)
    if current is None:
        return "No steps loaded"
    total = len(steps)
    step_num = current.get("step") or "?"
    status = current.get("status", "locked")
    return f"Step {step_num} of {total}: {current['name']} ({status.replace('_', ' ')})"


def pick_current_step(steps: list[dict]) -> dict | None:
    if not steps:
        return None

    for step in steps:
        if step.get("status") == "in_progress":
            return step
    for step in steps:
        if step.get("status") == "available":
            return step

    mastered_steps = [step for step in steps if step.get("status") == "mastered"]
    if mastered_steps:
        last_mastered = max(mastered_steps, key=lambda step: step.get("step") or 0)
        next_step = next(
            (step for step in steps if (step.get("step") or 0) > (last_mastered.get("step") or 0)),
            None,
        )
        if next_step is not None:
            return next_step
        return last_mastered

    return steps[0]


def build_program_groups(
    rows: list[dict],
    *,
    expand_current: bool = False,
) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (row["source_book"], row["family"])
        grouped.setdefault(key, []).append(row)

    programs = []
    for (source_book, family), steps in sorted(grouped.items()):
        steps.sort(key=lambda step: (step.get("step") if step.get("step") != "" else 999, step["name"]))
        current = pick_current_step(steps)
        programs.append(
            {
                "id": f"{source_book}:{family}",
                "title": format_program_title(source_book, family),
                "source_book": source_book,
                "family": family,
                "steps": steps,
                "current_step_id": current["id"] if current else None,
                "expanded": expand_current and current is not None,
                "summary": format_program_summary(steps),
            }
        )
    return programs


def build_program_hierarchy(
    rows: list[dict],
    *,
    expand_current: bool = False,
) -> list[dict]:
    """Nest programs under book (CC1, CC2, …) then family (Pull, Push, …)."""
    programs = build_program_groups(rows, expand_current=False)
    for program in programs:
        program["title"] = format_family_label(program["family"])
        program["expanded"] = expand_current

    by_book: dict[str, list[dict]] = {}
    for program in programs:
        by_book.setdefault(program["source_book"], []).append(program)

    hierarchy: list[dict] = []
    for source_book in sorted(by_book.keys()):
        book_programs = by_book[source_book]
        hierarchy.append(
            {
                "id": f"book:{source_book}",
                "source_book": source_book,
                "title": source_book,
                "subtitle": BOOK_LABELS.get(source_book, source_book),
                "programs": book_programs,
                "expanded": expand_current,
                "summary": f"{len(book_programs)} programs",
            }
        )
    return hierarchy


def filter_program_hierarchy(hierarchy: list[dict], query: str) -> list[dict]:
    needle = query.strip().lower()
    if not needle:
        return hierarchy

    filtered: list[dict] = []
    for book in hierarchy:
        book_blob = f"{book['title']} {book.get('subtitle', '')} {book['id']}".lower()
        book_match = needle in book_blob

        matching_programs: list[dict] = []
        for program in book["programs"]:
            program_blob = f"{program['title']} {program.get('summary', '')} {program['id']}".lower()
            if needle in program_blob:
                matching_programs.append({**program, "expanded": True})
                continue

            matching_steps = [step for step in program["steps"] if needle in _row_search_blob(step)]
            if not matching_steps:
                continue

            current_id = program.get("current_step_id")
            if current_id not in {step["id"] for step in matching_steps}:
                current_id = matching_steps[0]["id"]

            matching_programs.append(
                {
                    **program,
                    "steps": matching_steps,
                    "current_step_id": current_id,
                    "expanded": True,
                    "summary": f"{len(matching_steps)} matching step(s)",
                }
            )

        if book_match:
            filtered.append({**book, "programs": [{**p, "expanded": True} for p in book["programs"]], "expanded": True})
        elif matching_programs:
            filtered.append({**book, "programs": matching_programs, "expanded": True})

    return filtered


def format_step_label(step: dict) -> str:
    step_num = step.get("step")
    prefix = f"Step {step_num}: " if step_num not in (None, "") else ""
    status = step.get("status", "locked").replace("_", " ")
    marker = " ◀ current" if step.get("is_current") else ""
    return f"{prefix}{step['name']} ({status}){marker}"


def _row_search_blob(row: dict) -> str:
    parts = [
        row.get("name", ""),
        row.get("source_book", ""),
        row.get("family", ""),
        str(row.get("step", "")),
        row.get("status", ""),
        row.get("id", ""),
    ]
    criteria = row.get("criteria") or {}
    parts.extend(f"{key}={value}" for key, value in criteria.items())
    return " ".join(parts).lower()


def filter_rows_by_search(rows: list[dict], query: str) -> list[dict]:
    needle = query.strip().lower()
    if not needle:
        return rows
    return [row for row in rows if needle in _row_search_blob(row)]


def filter_program_groups(programs: list[dict], query: str) -> list[dict]:
    needle = query.strip().lower()
    if not needle:
        return programs

    filtered: list[dict] = []
    for program in programs:
        program_blob = f"{program['title']} {program.get('summary', '')} {program['id']}".lower()
        if needle in program_blob:
            filtered.append({**program, "expanded": True})
            continue

        matching_steps = [step for step in program["steps"] if needle in _row_search_blob(step)]
        if not matching_steps:
            continue

        current_id = program.get("current_step_id")
        if current_id not in {step["id"] for step in matching_steps}:
            current_id = matching_steps[0]["id"]

        filtered.append(
            {
                **program,
                "steps": matching_steps,
                "current_step_id": current_id,
                "expanded": True,
                "summary": f"{len(matching_steps)} matching step(s)",
            }
        )
    return filtered


def ensure_entry_points_available(repo: FitnessRepository) -> list[str]:
    """Mark root exercises in each prerequisite chain as available."""
    from progression.engine import unlock_available_targets
    from progression.models import UserExerciseProgress

    repo.initialize()
    incoming: set[str] = set()
    for edge in repo.list_edges("prerequisite"):
        incoming.add(edge.to_exercise_id)

    unlocked: list[str] = []
    for exercise in repo.list_exercises():
        if exercise.id in incoming:
            continue
        progress = repo.get_user_progress(exercise.id)
        if progress is None or progress.status == "locked":
            repo.upsert_user_progress(
                UserExerciseProgress(exercise_id=exercise.id, status="available")
            )
            unlocked.append(exercise.id)
            unlock_available_targets(repo, exercise.id)

    return unlocked
