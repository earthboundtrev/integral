import json
import os
import tempfile

import profiles

DATA_FILE_NAME = "data.json"


def get_data_dir():
    profiles.ensure_app_structure()
    return profiles.get_profile_dir()


def get_data_path():
    return os.path.join(get_data_dir(), DATA_FILE_NAME)


def get_default_categories():
    return {
        "Money/Freedom": {
            "checklist": [
                "Tracked daily finances",
                "Took action toward financial freedom",
                "Reviewed long-term money goals",
            ],
            "metrics": [
                {"name": "Savings/Income logged", "type": "number", "unit": "$", "default": 0},
                {"name": "Freedom mindset rating", "type": "rating", "min": 1, "max": 10, "default": 5},
            ],
        },
        "Body & Presence": {
            "checklist": [
                "Completed movement/exercise",
                "Practiced mindfulness or presence",
                "Ate nourishing food",
            ],
            "metrics": [
                {"name": "Sleep hours last night", "type": "number", "unit": "hrs", "default": 0},
                {"name": "Energy level", "type": "rating", "min": 1, "max": 10, "default": 5},
                {"name": "Presence rating", "type": "rating", "min": 1, "max": 10, "default": 5},
            ],
        },
        "Burnout Prevention & Energy Management": {
            "checklist": [
                "Took intentional breaks",
                "Respected personal boundaries",
                "Did a self-care activity",
            ],
            "metrics": [
                {"name": "Morning energy", "type": "rating", "min": 1, "max": 10, "default": 5},
                {"name": "Stress level (lower = better)", "type": "rating", "min": 1, "max": 10, "default": 5},
            ],
        },
        "Creative/Mental Work": {
            "checklist": [
                "Had a focused/deep work session",
                "Captured ideas or insights",
                "Made progress on creative project",
            ],
            "metrics": [
                {"name": "Deep work hours", "type": "number", "unit": "hrs", "default": 0},
                {"name": "Focus / Creativity rating", "type": "rating", "min": 1, "max": 10, "default": 5},
            ],
        },
        "Family/Logistics": {
            "checklist": [
                "Spent quality time with family",
                "Handled key logistics/tasks",
                "Communicated openly",
            ],
            "metrics": [
                {"name": "Family time", "type": "number", "unit": "hrs", "default": 0},
                {"name": "Logistics completion", "type": "rating", "min": 1, "max": 10, "default": 5},
            ],
        },
        "Search Practice": {
            "checklist": [
                "Engaged in search/inquiry practice",
                "Journaled or reflected on search",
                "Took a concrete search-related action",
            ],
            "metrics": [
                {"name": "Search effort rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                {"name": "Insights or actions taken", "type": "number", "unit": "", "default": 0},
            ],
        },
        "Spiritual Development": {
            "checklist": [
                "Daily spiritual practice (meditation, prayer, contemplation, etc.)",
                "Read or reflected on spiritual teachings / wisdom",
                "Practiced gratitude, surrender, or presence",
                "Connected with community, nature, or higher purpose",
            ],
            "metrics": [
                {"name": "Spiritual practice time", "type": "number", "unit": "min", "default": 0},
                {"name": "Spiritual connection / peace rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                {"name": "Insights or realizations", "type": "number", "unit": "", "default": 0},
            ],
        },
        "Emotional Wellbeing": {
            "checklist": [
                "Checked in with my current emotions",
                "Journaled or processed feelings",
                "Practiced self-compassion or emotional regulation",
                "Expressed emotions in a healthy, constructive way",
            ],
            "metrics": [
                {"name": "Emotional awareness rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                {"name": "Overall mood / emotional stability", "type": "rating", "min": 1, "max": 10, "default": 5},
                {"name": "Emotional check-ins or processing sessions", "type": "number", "unit": "", "default": 0},
            ],
        },
    }


def empty_data():
    return {"categories": get_default_categories(), "entries": {}}


def ensure_data_dir():
    os.makedirs(get_data_dir(), exist_ok=True)


def load(data_path=None):
    path = data_path or get_data_path()
    ensure_data_dir()
    if not os.path.exists(path):
        data = empty_data()
        save(data, path)
        return data
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("categories", get_default_categories())
    data.setdefault("entries", {})
    return data


def save(data, data_path=None):
    path = data_path or get_data_path()
    ensure_data_dir()
    directory = os.path.dirname(path)
    fd, temp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
