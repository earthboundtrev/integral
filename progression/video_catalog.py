"""Exercise demonstration video lookup."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import paths

SERIES_VIDEOS: dict[str, dict[str, str]] = {
    "CC1:push": {
        "url": "https://direct.dragondoor.com/products/ddv083",
        "source": "Official — Paul Wade / Dragon Door (CC Vol 1: Push)",
        "title": "Convict Conditioning Push Series",
    },
    "CC1:squat": {
        "url": "https://direct.dragondoor.com/products/ddv084",
        "source": "Official — Paul Wade / Dragon Door (CC Vol 2: Squat)",
        "title": "Convict Conditioning Squat Series",
    },
    "CC1:leg_raise": {
        "url": "https://www.dragondoor.com/shop-by-department/dvds/dv085/",
        "source": "Official — Paul Wade / Dragon Door (CC Vol 3: Leg Raises)",
        "title": "Convict Conditioning Leg Raise Series",
    },
    "CC1:bridge": {
        "url": "https://direct.dragondoor.com/products/ddv087",
        "source": "Official — Paul Wade / Dragon Door (CC Vol 4: Bridge)",
        "title": "Convict Conditioning Bridge Series",
    },
    "CC1:pull": {
        "url": "https://direct.dragondoor.com/products/ddv088",
        "source": "Official — Paul Wade / Dragon Door (CC Vol 5: Pull-up)",
        "title": "Convict Conditioning Pull-up Series",
    },
    "CC1:handstand_pushup": {
        "url": "https://direct.dragondoor.com/products/ddv083",
        "source": "Official — Paul Wade / Dragon Door (CC push/HSPU progressions)",
        "title": "Convict Conditioning Handstand Push-up progressions",
    },
    "CC2:hang": {
        "url": "https://direct.dragondoor.com/collections/convict-conditioning",
        "source": "Official — Paul Wade / Dragon Door (CC2)",
        "title": "Convict Conditioning 2 — Hang progressions",
    },
    "CC2:fingertip_pushup": {
        "url": "https://direct.dragondoor.com/collections/convict-conditioning",
        "source": "Official — Paul Wade / Dragon Door (CC2)",
        "title": "Convict Conditioning 2 — Fingertip push-ups",
    },
    "CC2:clutch_flag": {
        "url": "https://direct.dragondoor.com/collections/convict-conditioning",
        "source": "Official — Paul Wade / Dragon Door (CC2)",
        "title": "Convict Conditioning 2 — Clutch flag",
    },
    "CC2:press_flag": {
        "url": "https://direct.dragondoor.com/collections/convict-conditioning",
        "source": "Official — Paul Wade / Dragon Door (CC2)",
        "title": "Convict Conditioning 2 — Press flag",
    },
    "CC2:neck_bridge": {
        "url": "https://direct.dragondoor.com/collections/convict-conditioning",
        "source": "Official — Paul Wade / Dragon Door (CC2)",
        "title": "Convict Conditioning 2 — Neck bridges",
    },
    "CC2:calf": {
        "url": "https://direct.dragondoor.com/collections/convict-conditioning",
        "source": "Official — Paul Wade / Dragon Door (CC2)",
        "title": "Convict Conditioning 2 — Calf training",
    },
    "CC2:trifecta_bridge": {
        "url": "https://direct.dragondoor.com/collections/convict-conditioning",
        "source": "Official — Paul Wade / Dragon Door (CC2)",
        "title": "Convict Conditioning 2 — Trifecta bridge hold",
    },
    "CC2:trifecta_l_hold": {
        "url": "https://direct.dragondoor.com/collections/convict-conditioning",
        "source": "Official — Paul Wade / Dragon Door (CC2)",
        "title": "Convict Conditioning 2 — Trifecta L-hold",
    },
    "CC2:trifecta_twist": {
        "url": "https://direct.dragondoor.com/collections/convict-conditioning",
        "source": "Official — Paul Wade / Dragon Door (CC2)",
        "title": "Convict Conditioning 2 — Trifecta twist",
    },
    "OG:push": {
        "url": "https://www.youtube.com/watch?v=UoPRqPvF4AQ",
        "source": "Tom Merrick (Bodyweight Warrior) — planche progression",
        "title": "Project Planche intro",
    },
    "OG:pull": {
        "url": "https://www.youtube.com/watch?v=AGhb8V8M758",
        "source": "FitnessFAQs — front lever tutorial",
        "title": "Front Lever Tutorial",
    },
    "SS:main": {
        "url": "https://www.youtube.com/@startingstrength",
        "source": "Official — Starting Strength / Mark Rippetoe",
        "title": "Starting Strength channel",
    },
    "EC:explosive": {
        "url": "https://www.youtube.com/watch?v=2n4UqRIJyk4",
        "source": "Al Kavadlo — explosive push-up progressions",
        "title": "Explosive Push-ups (Al Kavadlo)",
    },
    "FTR:rites": {
        "url": "https://www.youtube.com/watch?v=C9KCzQqcyGY",
        "source": "Chris Kilham — Five Tibetans authority",
        "title": "The Five Tibetans — Practicing Correctly",
    },
}

EXERCISE_VIDEOS: dict[str, dict[str, str]] = {
    # CC1 Push — Dragon Door CC series clips on YouTube + official series
    "cc1_push_01": {
        "url": "https://www.youtube.com/watch?v=1V1TpzUwokY",
        "source": "Dragon Door CC series (YouTube)",
        "title": "Wall Push-ups — Step 1",
    },
    "cc1_push_02": {
        "url": "https://direct.dragondoor.com/products/ddv083",
        "source": "Official — Paul Wade / Dragon Door (CC Vol 1: Push)",
        "title": "Incline Push-ups — Step 2 (official series)",
    },
    "cc1_push_05": {
        "url": "https://direct.dragondoor.com/products/ddv083",
        "source": "Official — Paul Wade / Dragon Door (CC Vol 1: Push)",
        "title": "Full Push-ups — Step 5 (official series)",
    },
    "cc1_push_10": {
        "url": "https://direct.dragondoor.com/products/ddv083",
        "source": "Official — Paul Wade / Dragon Door (CC Vol 1: Push)",
        "title": "One-Arm Push-ups — Step 10 (official series)",
    },
    # Starting Strength — official channel
    "ss_back_squat": {
        "url": "https://www.youtube.com/watch?v=nhoikoUEI8U",
        "source": "Starting Strength (official)",
        "title": "Learning to Squat",
    },
    "ss_bench_press": {
        "url": "https://www.youtube.com/watch?v=rxD321l2svE",
        "source": "Starting Strength (official)",
        "title": "Learning to Bench Press",
    },
    "ss_deadlift": {
        "url": "https://www.youtube.com/watch?v=p2OPUi4xGrM",
        "source": "Starting Strength (official)",
        "title": "Learning to Deadlift",
    },
    "ss_overhead_press": {
        "url": "https://www.youtube.com/watch?v=8dacy5hjaE8",
        "source": "Starting Strength (official)",
        "title": "Learning to Press",
    },
    "ss_power_clean": {
        "url": "https://www.youtube.com/watch?v=37-wjE_c4NU",
        "source": "Starting Strength (official)",
        "title": "Power Clean Series Part 1",
    },
    # Overcoming Gravity progressions
    "og_planche_lean": {
        "url": "https://www.youtube.com/watch?v=UoPRqPvF4AQ",
        "source": "Tom Merrick (Bodyweight Warrior)",
        "title": "Planche Lean",
    },
    "og_tuck_planche": {
        "url": "https://www.youtube.com/watch?v=CaKyFvr6Oko",
        "source": "FitnessFAQs",
        "title": "Tuck Planche Tutorial",
    },
    "og_front_lever_tuck": {
        "url": "https://www.youtube.com/watch?v=AGhb8V8M758",
        "source": "FitnessFAQs",
        "title": "Front Lever Progression",
    },
    "og_front_lever": {
        "url": "https://www.youtube.com/watch?v=AGhb8V8M758",
        "source": "FitnessFAQs",
        "title": "Front Lever",
    },
    # Explosive calisthenics
    "ec_clap_pushup": {
        "url": "https://www.youtube.com/watch?v=2n4UqRIJyk4",
        "source": "Al Kavadlo",
        "title": "Clap Push-up",
    },
    # Five Tibetan Rites — Chris Kilham full sequence
    "ftr_rite_1": {
        "url": "https://www.youtube.com/watch?v=C9KCzQqcyGY",
        "source": "Chris Kilham",
        "title": "Rite 1 — Spinning",
    },
    "ftr_rite_2": {
        "url": "https://www.youtube.com/watch?v=C9KCzQqcyGY",
        "source": "Chris Kilham",
        "title": "Rite 2 — Leg Raises",
    },
    "ftr_rite_3": {
        "url": "https://www.youtube.com/watch?v=C9KCzQqcyGY",
        "source": "Chris Kilham",
        "title": "Rite 3 — Kneeling Backbend",
    },
    "ftr_rite_4": {
        "url": "https://www.youtube.com/watch?v=C9KCzQqcyGY",
        "source": "Chris Kilham",
        "title": "Rite 4 — Tabletop Bridge",
    },
    "ftr_rite_5": {
        "url": "https://www.youtube.com/watch?v=C9KCzQqcyGY",
        "source": "Chris Kilham",
        "title": "Rite 5 — Pendulum",
    },
    # Convict Conditioning 2 — book ladders + respected calisthenics coaches
    "cc2_trifecta_l_hold_04": {
        "url": "https://www.youtube.com/watch?v=cu0fHp8HCDo",
        "source": "FitnessFAQs (Daniel Vadnal)",
        "title": "L-Sit — progressions & hip flexor strength",
    },
    "cc2_trifecta_l_hold_06": {
        "url": "https://www.youtube.com/watch?v=wzaJ9lhetmk",
        "source": "Calisthenics progression (L-sit → V-sit path)",
        "title": "V-Sit — compression progressions",
    },
    "cc2_clutch_flag_03": {
        "url": "https://www.youtube.com/watch?v=bG0h7bSfxQI",
        "source": "Chris Heria / THENX (human flag progressions)",
        "title": "Human Flag — tuck to full",
    },
    "cc2_press_flag_03": {
        "url": "https://www.youtube.com/watch?v=bG0h7bSfxQI",
        "source": "Chris Heria / THENX (human flag progressions)",
        "title": "Human Flag — tuck to full",
    },
}


@lru_cache(maxsize=1)
def _load_catalog_file() -> dict:
    catalog_path = paths.app_resource("progression", "seed", "v1", "exercise_videos.json")
    if not catalog_path.exists():
        return {"exercises": {}, "series": {}}
    with open(catalog_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def get_exercise_video(
    seed_key: str | None,
    source_book: str | None = None,
    family: str | None = None,
    exercise_name: str | None = None,
) -> dict[str, str] | None:
    if seed_key and seed_key in EXERCISE_VIDEOS:
        return EXERCISE_VIDEOS[seed_key].copy()

    catalog = _load_catalog_file()
    if seed_key and seed_key in catalog.get("exercises", {}):
        return catalog["exercises"][seed_key].copy()

    series_key = f"{source_book}:{family}" if source_book and family else None
    if series_key and series_key in SERIES_VIDEOS:
        video = SERIES_VIDEOS[series_key].copy()
        if exercise_name:
            video["title"] = f"{exercise_name} — see {video['title']}"
        return video

    if series_key and series_key in catalog.get("series", {}):
        video = catalog["series"][series_key].copy()
        if exercise_name:
            video["title"] = f"{exercise_name} — see {video['title']}"
        return video

    return None


def open_exercise_video(video: dict[str, str]) -> None:
    import webbrowser

    webbrowser.open(video["url"])
