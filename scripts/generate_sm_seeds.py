"""Generate Strong Medicine sequential seed JSON from programs/strong-medicine.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "programs" / "strong-medicine.json"
OUT = ROOT / "progression" / "seed" / "v1"

FAMILY_MAP = {
    "sm-squat": ("squat", "squat"),
    "sm-deadlift": ("sumo_deadlift", "sumo_deadlift"),
    "sm-bench-press": ("db_bench", "db_bench"),
    "sm-overhead-press": ("db_overhead_press", "db_overhead_press"),
    "sm-row": ("statue_row", "statue_row"),
    "sm-ab-training": ("plank_core", "plank_core"),
}

# Qualitative Hub progression notes — use Hub intermediate for loggable criteria.
_QUALITATIVE = {
    "parallel depth",
    "ultra-deep",
    "minimal assist",
    "silent touch-down",
}


def _strip_qualifiers(text: str) -> str:
    text = text.strip().lower().replace("–", "-").replace("—", "-")
    for suffix in (" grind", " perfect"):
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
    return text


def parse_standard(standard: str) -> dict | None:
    """Parse a Hub B/I/P cell into mastery_criteria, or None if not loggable."""
    text = _strip_qualifiers(standard or "")
    if not text or text in _QUALITATIVE:
        return None

    match = re.fullmatch(r"(\d+)\s*x\s*(\d+)\s*min", text)
    if match:
        return {"sets": int(match.group(1)), "hold_seconds": int(match.group(2)) * 60}

    match = re.fullmatch(r"(\d+)\s*x\s*(\d+)\s*s", text)
    if match:
        return {"sets": int(match.group(1)), "hold_seconds": int(match.group(2))}

    match = re.fullmatch(r"(\d+)\s*min", text)
    if match:
        return {"sets": 1, "hold_seconds": int(match.group(1)) * 60}

    match = re.fullmatch(r"(\d+)\s*s", text)
    if match:
        return {"sets": 1, "hold_seconds": int(match.group(1))}

    match = re.fullmatch(r"(\d+)\s*x\s*(\d+)", text)
    if match:
        return {"sets": int(match.group(1)), "reps": int(match.group(2))}

    match = re.fullmatch(r"(\d+)\s*reps?", text)
    if match:
        return {"sets": 1, "reps": int(match.group(1))}

    return None


def mastery_for_step(step: dict) -> tuple[dict, str | None]:
    """Return (criteria, hub_progression_note_if_qualitative)."""
    progression = (step.get("progression") or "").strip()
    parsed = parse_standard(progression)
    if parsed is not None:
        note = progression if _strip_qualifiers(progression) != progression.lower() else None
        # Keep technique words like "grind" as notes even when reps parsed
        if progression.lower() != _strip_qualifiers(progression):
            note = progression
        return parsed, note

    intermediate = (step.get("intermediate") or "").strip()
    parsed_i = parse_standard(intermediate)
    if parsed_i is None:
        raise ValueError(
            f"No loggable Hub standard for step {step.get('name')!r}: "
            f"progression={progression!r} intermediate={intermediate!r}"
        )
    return parsed_i, progression or None


def build_seed(movement: dict, family: str, key_prefix: str) -> dict:
    steps = movement["steps"]
    exercises = []
    for step in steps:
        n = int(step["step"])
        key = f"sm_{key_prefix}_{n:02d}"
        criteria, note = mastery_for_step(step)
        item: dict = {
            "key": key,
            "name": step["name"],
            "step": n,
            "mastery_criteria": criteria,
        }
        if note:
            item["hub_progression_note"] = note
        exercises.append(item)
    edges = [
        {
            "from": exercises[i]["key"],
            "to": exercises[i + 1]["key"],
            "edge_type": "prerequisite",
            "unlock_condition": {"requires": "mastered"},
        }
        for i in range(len(exercises) - 1)
    ]
    return {
        "source_book": "SM",
        "family": family,
        "step_progression": "sequential",
        "version": "v1",
        "source": "programs/strong-medicine.json",
        "hub_movement_id": movement["id"],
        "exercises": exercises,
        "edges": edges,
    }


def main() -> None:
    hub = json.loads(HUB.read_text(encoding="utf-8"))
    total = 0
    for movement in hub["movements"]:
        mid = movement["id"]
        if mid not in FAMILY_MAP:
            raise SystemExit(f"Unmapped movement: {mid}")
        family, prefix = FAMILY_MAP[mid]
        payload = build_seed(movement, family, prefix)
        out_path = OUT / f"sm_{prefix}.json"
        out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        total += len(payload["exercises"])
        print(f"Wrote {out_path.name} ({len(payload['exercises'])} steps)")
    print(f"Total SM exercises: {total}")


if __name__ == "__main__":
    main()
