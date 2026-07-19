"""Generate CC2 sequential seed JSON from programs/convict-conditioning-2.json Hub tables."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "programs" / "convict-conditioning-2.json"
OUT = ROOT / "progression" / "seed" / "v1"

FAMILY_MAP = {
    "cc2-hang-progressions": ("hang", "hang"),
    "cc2-fingertip-pushups": ("fingertip_pushup", "fingertip_pushup"),
    "cc2-clutch-flag": ("clutch_flag", "clutch_flag"),
    "cc2-press-flag": ("press_flag", "press_flag"),
    "cc2-neck-bridges": ("neck_bridge", "neck_bridge"),
    "cc2-calf-training": ("calf", "calf"),
    "cc2-bridge-hold": ("trifecta_bridge", "trifecta_bridge"),
    "cc2-l-hold": ("trifecta_l_hold", "trifecta_l_hold"),
    "cc2-twist": ("trifecta_twist", "trifecta_twist"),
}


def parse_progression(standard: str) -> dict:
    """Map Hub progression column (B/I/P notation) to mastery_criteria."""
    text = (standard or "").strip().lower().replace("–", "-").replace("—", "-")
    text = text.replace(" hold", "").strip()

    # NxMmin
    match = re.fullmatch(r"(\d+)\s*x\s*(\d+)\s*min", text)
    if match:
        return {"sets": int(match.group(1)), "hold_seconds": int(match.group(2)) * 60}

    # NxMs
    match = re.fullmatch(r"(\d+)\s*x\s*(\d+)\s*s", text)
    if match:
        return {"sets": int(match.group(1)), "hold_seconds": int(match.group(2))}

    # Nmin
    match = re.fullmatch(r"(\d+)\s*min", text)
    if match:
        return {"sets": 1, "hold_seconds": int(match.group(1)) * 60}

    # Ns
    match = re.fullmatch(r"(\d+)\s*s", text)
    if match:
        return {"sets": 1, "hold_seconds": int(match.group(1))}

    # NxM reps style
    match = re.fullmatch(r"(\d+)\s*x\s*(\d+)", text)
    if match:
        return {"sets": int(match.group(1)), "reps": int(match.group(2))}

    # N reps
    match = re.fullmatch(r"(\d+)\s*reps?", text)
    if match:
        return {"sets": 1, "reps": int(match.group(1))}

    # N steps (bridge walk)
    match = re.fullmatch(r"(\d+)\s*steps?", text)
    if match:
        return {"sets": 1, "reps": int(match.group(1))}

    raise ValueError(f"Unrecognized progression standard: {standard!r}")


def build_seed(movement: dict, family: str, key_prefix: str) -> dict:
    steps = movement["steps"]
    exercises = []
    for step in steps:
        n = int(step["step"])
        key = f"cc2_{key_prefix}_{n:02d}"
        criteria = parse_progression(step["progression"])
        exercises.append(
            {
                "key": key,
                "name": step["name"],
                "step": n,
                "mastery_criteria": criteria,
            }
        )
    edges = []
    for i in range(len(exercises) - 1):
        edges.append(
            {
                "from": exercises[i]["key"],
                "to": exercises[i + 1]["key"],
                "edge_type": "prerequisite",
                "unlock_condition": {"requires": "mastered"},
            }
        )
    return {
        "source_book": "CC2",
        "family": family,
        "step_progression": "sequential",
        "version": "v1",
        "source": "programs/convict-conditioning-2.json",
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
        out_path = OUT / f"cc2_{prefix}.json"
        out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        total += len(payload["exercises"])
        print(f"Wrote {out_path.name} ({len(payload['exercises'])} steps)")
    sample = OUT / "cc2_sample.json"
    if sample.exists():
        sample.unlink()
        print("Removed cc2_sample.json")
    print(f"Total CC2 exercises: {total}")


if __name__ == "__main__":
    main()
