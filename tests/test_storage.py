import json
import os
import tempfile
from datetime import datetime, timedelta

import pytest

import profiles
import storage
import streak
import summaries
import history


@pytest.fixture
def temp_data_path(monkeypatch):
  with tempfile.TemporaryDirectory() as tmp:
    app_dir = os.path.join(tmp, "app")
    profile_dir = os.path.join(app_dir, "profiles", "default")
    os.makedirs(profile_dir, exist_ok=True)
    config_path = os.path.join(app_dir, "config.json")
    with open(config_path, "w", encoding="utf-8") as f:
      json.dump({"active_profile_id": "default", "profiles": [{"id": "default", "name": "Default"}]}, f)

    path = os.path.join(profile_dir, "data.json")

    import profiles
    monkeypatch.setattr(profiles, "get_app_dir", lambda: app_dir)
    monkeypatch.setattr(profiles, "get_profiles_root", lambda: os.path.join(app_dir, "profiles"))
    monkeypatch.setattr(profiles, "get_config_path", lambda: config_path)
    monkeypatch.setattr(
      profiles,
      "get_profile_dir",
      lambda profile_id=None: os.path.join(app_dir, "profiles", profile_id or "default"),
    )
    monkeypatch.setattr(profiles, "get_active_profile_id", lambda: "default")
    yield path


def test_creates_dir_and_defaults(temp_data_path):
  assert not os.path.exists(temp_data_path)
  data = storage.load(temp_data_path)
  assert os.path.exists(temp_data_path)
  assert data["entries"] == {}
  assert len(data["categories"]) == 8


def test_roundtrip_load_save(temp_data_path):
  data = storage.load(temp_data_path)
  data["entries"]["2026-06-27"] = {
    "Body & Presence": {"rating": 8, "checklist": {}, "metrics": {}, "notes": "Good day"}
  }
  storage.save(data, temp_data_path)
  loaded = storage.load(temp_data_path)
  assert loaded["entries"]["2026-06-27"]["Body & Presence"]["rating"] == 8


def test_atomic_save(temp_data_path):
  data = storage.load(temp_data_path)
  storage.save(data, temp_data_path)
  with open(temp_data_path, "r", encoding="utf-8") as f:
    parsed = json.load(f)
  assert "categories" in parsed


def test_eight_categories(temp_data_path):
  data = storage.load(temp_data_path)
  expected = [
    "Money/Freedom",
    "Body & Presence",
    "Burnout Prevention & Energy Management",
    "Creative/Mental Work",
    "Family/Logistics",
    "Search Practice",
    "Spiritual Development",
    "Emotional Wellbeing",
  ]
  assert list(data["categories"].keys()) == expected
  for cat in expected:
    assert len(data["categories"][cat]["checklist"]) >= 1
    assert len(data["categories"][cat]["metrics"]) >= 1


def test_streak_overall():
  today = datetime.now().date()
  entries = {
    today.strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 5}},
    (today - timedelta(days=1)).strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 5}},
  }
  assert streak.get_streak(entries) == 2


def test_streak_category():
  today = datetime.now().date()
  entries = {
    today.strftime("%Y-%m-%d"): {
      "Body & Presence": {"rating": 5},
      "Money/Freedom": {"rating": 5},
    },
    (today - timedelta(days=1)).strftime("%Y-%m-%d"): {"Body & Presence": {"rating": 5}},
  }
  assert streak.get_streak(entries, "Body & Presence") == 2
  assert streak.get_streak(entries, "Money/Freedom") == 1


def test_summary_includes_sections():
  today = datetime.now().strftime("%Y-%m-%d")
  text = summaries.build_summary_text({today: {"Body & Presence": {"rating": 7, "notes": "x"}}})
  assert "=== TODAY ===" in text
  assert "=== THIS WEEK ===" in text
  assert "=== LAST 30 DAYS ===" in text


def test_format_history_empty():
  assert "No entries" in history.format_history({})


def test_format_history_order():
  text = history.format_history(
    {
      "2026-06-25": {"Body & Presence": {"rating": 5, "notes": "older"}},
      "2026-06-27": {"Body & Presence": {"rating": 7, "notes": "newer"}},
    }
  )
  assert text.index("2026-06-27") < text.index("2026-06-25")
