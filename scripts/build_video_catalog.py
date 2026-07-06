"""Build exercise_videos.json with per-exercise fallbacks to official series."""

import json
from pathlib import Path

SERIES = {
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
        "source": "Official — Paul Wade / Dragon Door",
        "title": "Handstand Push-up progressions",
    },
    "CC2:sample": {
        "url": "https://direct.dragondoor.com/collections/convict-conditioning",
        "source": "Official — Paul Wade / Dragon Door (CC2)",
        "title": "Convict Conditioning 2",
    },
    "OG:push": {
        "url": "https://www.youtube.com/watch?v=UoPRqPvF4AQ",
        "source": "Tom Merrick (Bodyweight Warrior)",
        "title": "Planche progression",
    },
    "OG:pull": {
        "url": "https://www.youtube.com/watch?v=AGhb8V8M758",
        "source": "FitnessFAQs",
        "title": "Front lever progression",
    },
    "SS:main": {
        "url": "https://www.youtube.com/@startingstrength",
        "source": "Official — Starting Strength",
        "title": "Starting Strength channel",
    },
    "EC:explosive": {
        "url": "https://www.youtube.com/watch?v=2n4UqRIJyk4",
        "source": "Al Kavadlo",
        "title": "Explosive push-up progressions",
    },
    "FTR:rites": {
        "url": "https://www.youtube.com/watch?v=C9KCzQqcyGY",
        "source": "Chris Kilham",
        "title": "Five Tibetans — full sequence",
    },
}


def main() -> None:
    seed_dir = Path("progression/seed/v1")
    exercises: dict[str, dict[str, str]] = {}

    for seed_file in sorted(seed_dir.glob("*.json")):
        if seed_file.name in {"cross_links.json", "exercise_videos.json"}:
            continue
        payload = json.loads(seed_file.read_text(encoding="utf-8"))
        series_key = f"{payload['source_book']}:{payload['family']}"
        series = SERIES.get(series_key, {})
        for item in payload.get("exercises", []):
            step = item.get("step")
            exercises[item["key"]] = {
                "url": series.get("url", ""),
                "source": series.get("source", "Curated reference"),
                "title": f"Step {step}: {item['name']}",
            }

    output = {
        "version": "v1",
        "series": SERIES,
        "exercises": exercises,
    }
    out_path = seed_dir / "exercise_videos.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {len(exercises)} exercise entries to {out_path}")


if __name__ == "__main__":
    main()
