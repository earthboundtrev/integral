"""Build programs/overcoming-gravity.json from OG2 progression chart data."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "programs" / "overcoming-gravity.json"

# OG2 chart data (Steven Low, 2nd ed.) — levels 1-16 per column; empty cells omitted as repeats.


def steps_for_levels(level_map: dict[int, str]) -> list[dict]:
    steps: list[dict] = []
    last_name = ""
    for level in range(1, 17):
        name = level_map.get(level, last_name) or f"Level {level}"
        last_name = name
        steps.append(
            {
                "step": level,
                "name": name,
                "beginner": f"FIG Beg — L{level}",
                "intermediate": f"FIG Int — L{level}",
                "progression": f"FIG Adv — L{level}",
                "og_level": level,
            }
        )
    return steps


def movement(movement_id: str, name: str, chart: str, level_map: dict[int, str]) -> dict:
    return {
        "id": movement_id,
        "name": name,
        "chart": chart,
        "master_step": level_map.get(16, level_map.get(10, "Elite")),
        "steps": steps_for_levels(level_map),
    }


PROGRAM = {
    "id": "overcoming-gravity",
    "name": "Overcoming Gravity",
    "author": "Steven Low",
    "source": "Overcoming Gravity, 2nd Edition (2017) — official progression charts",
    "program_type": "reference",
    "description": "Gymnastics-style bodyweight progressions across handstand, pulling, pushing, and misc charts. "
    "Levels map to FIG tiers (Beginner / Intermediate A-B / Advanced / Elite). Use Program detail for full ladder.",
    "progression_model": "step_ladder",
    "notation": "Levels 1–16 per chart column; advance using Methods of Progression (Ch. 10)",
    "charts": [
        {"id": "handstand", "name": "Handstand Chart", "emphasis": "Anterior delts, traps, triceps, body control"},
        {"id": "pulling", "name": "Pulling Chart", "emphasis": "Posterior chain, scapular muscles, biceps"},
        {"id": "pushing", "name": "Pushing Chart", "emphasis": "Chest, anterior delts, triceps, planche"},
        {"id": "misc", "name": "Miscellaneous Chart", "emphasis": "Muscle-ups, flags, core, legs"},
    ],
    "movements": [
        movement(
            "og-hs-handstands",
            "Handstands",
            "handstand",
            {
                1: "Wall Handstand",
                2: "Wall Handstand",
                3: "Wall Handstand",
                4: "Free Handstand",
                5: "Free Handstand / Shoulder Stand",
                6: "Ring Strap Handstand",
                7: "Progressions to One-Arm Handstand",
                8: "Ring Strap Handstand (int)",
                9: "Ring Free Handstand",
                10: "One-Arm Handstand",
            },
        ),
        movement(
            "og-hs-hspu",
            "Handstand Pushups",
            "handstand",
            {
                1: "Pike Headstand Pushup (HeSPU)",
                2: "Box HeSPU",
                3: "Wall HeSPU Eccentric",
                4: "Wall Handstand Pushup",
                5: "Wall HSPU",
                6: "Free HeSPU",
                7: "Ring Handstand Free HSPU",
                8: "Ring Strap HSPU",
                9: "Ring Free HSPU",
                10: "1.15x BW HSPU variants",
            },
        ),
        movement(
            "og-hs-press",
            "Press to Handstand",
            "handstand",
            {
                1: "0.3x BW Bent-Arm Press",
                2: "0.43x BW Press",
                3: "0.55x BW Press",
                4: "0.68x BW Press",
                5: "Bent-Arm Bent-Body Press",
                6: "0.8x BW L-Sit Press",
                7: "0.9x BW Chair Press",
                8: "1.0x BW Bent-Arm Press",
                9: "1.08x BW Handstand Elbow Lever Press",
                10: "1.15x BW Parallel Bar Dip to HS",
            },
        ),
        movement(
            "og-hs-core",
            "L-Sit / V-Sit / Manna",
            "handstand",
            {
                1: "Tuck L-Sit",
                2: "One-Leg Bent L-Sit",
                3: "L-Sit",
                4: "Straddle L-Sit",
                5: "RTO L-Sit",
                6: "45° V-Sit",
                7: "75° V-Sit",
                8: "100° V-Sit",
                9: "120° V-Sit",
                10: "140° V-Sit",
                11: "155° V-Sit",
                12: "170° V-Sit",
                13: "Manna",
            },
        ),
        movement(
            "og-pull-back-lever",
            "Back Lever",
            "pulling",
            {
                1: "German Hang",
                2: "Skin the Cat",
                3: "Tuck Back Lever",
                4: "Advanced Tuck Back Lever",
                5: "Straddle Back Lever",
                6: "Half Lay / One-Leg Back Lever",
                7: "Full Back Lever",
                8: "Back Lever Pullout",
                9: "German Hang Pullout",
                10: "Bent-Arm Pull-up to Back Lever",
                11: "Handstand Lower to Back Lever",
            },
        ),
        movement(
            "og-pull-front-lever",
            "Front Lever / Rows",
            "pulling",
            {
                1: "Row Eccentric",
                2: "Jump Pull-ups",
                3: "Ring Rows",
                4: "Bar Pull-up Eccentric",
                5: "Wide Rows",
                6: "Tuck Front Lever",
                7: "Advanced Tuck Front Lever",
                8: "Straddle Front Lever",
                9: "Half Lay / One-Leg Front Lever",
                10: "Full Front Lever",
                11: "Front Lever to Inverted",
                12: "Circle Front Lever",
            },
        ),
        movement(
            "og-pull-pullups",
            "Pull-ups / OAC",
            "pulling",
            {
                1: "Assisted Pull-ups",
                2: "Kip Pull-ups",
                3: "Bar Pull-ups",
                4: "Archer Rows / L-Pull-ups",
                5: "1x Bodyweight Pull-ups",
                6: "Ring Wide Pull-ups",
                7: "1.35x BW / Clap Pull-ups",
                8: "One-Arm Chin Eccentric",
                9: "One-Arm Chin-up",
                10: "OAC + 15 lbs",
                11: "2x Bodyweight Pull-ups",
                12: "Iron Cross Hold",
            },
        ),
        movement(
            "og-push-planche",
            "Planche",
            "pushing",
            {
                1: "Frog Stand",
                2: "Tuck Planche",
                3: "Advanced Tuck Planche",
                4: "Straddle Planche",
                5: "Half Lay / One-Leg Planche",
                6: "Full Planche",
                7: "Straight-Arm Straddle Planche to HS",
                8: "Straight-Arm Planche to HS",
            },
        ),
        movement(
            "og-push-pushups",
            "Pushups / Planche Pushups",
            "pushing",
            {
                1: "Regular Pushups",
                2: "Diamond Pushups",
                3: "Ring Wide Pushups",
                4: "Ring Pushups",
                5: "RTO Pushups",
                6: "Tuck Planche Pushups",
                7: "Advanced Tuck PL Pushups",
                8: "Straddle Planche Pushups",
                9: "Wall Pseudo Planche Pushups",
                10: "Wall Maltese Pushups",
            },
        ),
        movement(
            "og-push-dips",
            "Dips / One-Arm Pushups",
            "pushing",
            {
                1: "Parallel Bar Jump Dips",
                2: "Support Hold",
                3: "PB Dips Eccentric",
                4: "Ring Dips Eccentric",
                5: "Parallel Bar Dips",
                6: "Elevated One-Arm Pushup",
                7: "Straight-Body One-Arm Pushup",
                8: "Ring Straight-Body OA Pushup",
                9: "RTO 90° Dips",
                10: "2x BW Dips",
            },
        ),
        movement(
            "og-misc-muscleup",
            "Muscle-ups / Flags / Core",
            "misc",
            {
                1: "25s Plank",
                2: "Muscle-up Negative",
                3: "60s Plank",
                4: "Kipping Muscle-up",
                5: "Muscle-up",
                6: "Wide / No False Grip MU",
                7: "Strict Bar Muscle-up",
                8: "One-Arm Muscle-up",
                9: "Ab Wheel",
                10: "Front Lever Muscle-up",
            },
        ),
        movement(
            "og-misc-elbow-lever",
            "Elbow Levers / Flags",
            "misc",
            {
                1: "Two-Arm Elbow Lever",
                2: "Tuck Flag (knees)",
                3: "Advanced Tuck Flag",
                4: "Straddle Flag",
                5: "Full Flag",
                6: "One-Arm Straddle Elbow Lever",
                7: "One-Arm Straight Elbow Lever",
                8: "Full Ab Wheel",
            },
        ),
        movement(
            "og-misc-legs",
            "Squats / Pistols / Skills",
            "misc",
            {
                1: "Parallel Squat",
                2: "Full Squat",
                3: "Side-to-Side Squat",
                4: "Pistol Squat",
                5: "1.2x BW Pistol",
                6: "Felge Forward to L-Sit",
                7: "1.35x BW Pistol",
                8: "1.5x BW Pistol",
                9: "1.8x BW Pistol",
                10: "2x BW Pistol",
            },
        ),
    ],
}


def main() -> None:
    OUT.write_text(json.dumps(PROGRAM, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(PROGRAM['movements'])} movement ladders)")


if __name__ == "__main__":
    main()
