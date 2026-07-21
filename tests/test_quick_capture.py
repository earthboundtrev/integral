"""SPEC-314 Quick Capture — settings, oEmbed, day-entry merge."""

from __future__ import annotations

import json
from datetime import datetime
from unittest import mock

import quick_capture


def test_quick_capture_defaults_off():
    assert quick_capture.normalize_quick_capture_settings({}) == {
        "enabled": False,
        "collapsed": {"today": False, "upcoming": False},
    }
    assert quick_capture.is_quick_capture_enabled({}) is False
    assert quick_capture.is_quick_capture_enabled({"quick_capture": {"enabled": True}}) is True


def test_collapsed_state_persists_and_survives_enable_toggle():
    settings = quick_capture.set_section_collapsed({}, "upcoming", True)
    assert quick_capture.is_section_collapsed(settings, "upcoming") is True
    assert quick_capture.is_section_collapsed(settings, "today") is False
    # Toggling enabled must not wipe collapsed flags (partial merge).
    settings = quick_capture.apply_quick_capture_settings(settings, {"enabled": True})
    assert quick_capture.is_quick_capture_enabled(settings) is True
    assert quick_capture.is_section_collapsed(settings, "upcoming") is True


def test_set_section_collapsed_ignores_unknown_section():
    settings = quick_capture.set_section_collapsed({}, "bogus", True)
    assert quick_capture.is_section_collapsed(settings, "today") is False
    assert quick_capture.is_section_collapsed(settings, "upcoming") is False


def test_is_youtube_url():
    assert quick_capture.is_youtube_url("https://www.youtube.com/watch?v=abc")
    assert quick_capture.is_youtube_url("https://youtu.be/abc")
    assert not quick_capture.is_youtube_url("https://example.com/watch?v=abc")
    assert not quick_capture.is_youtube_url("not a url")


def test_fetch_youtube_title_success():
    payload = json.dumps({"title": "Demo Video"}).encode("utf-8")
    fake = mock.MagicMock()
    fake.read.return_value = payload
    fake.__enter__.return_value = fake
    fake.__exit__.return_value = False
    with mock.patch("quick_capture.urlopen", return_value=fake) as urlopen:
        title = quick_capture.fetch_youtube_title("https://www.youtube.com/watch?v=abc")
    assert title == "Demo Video"
    assert urlopen.called


def test_fetch_youtube_title_skips_non_youtube():
    with mock.patch("quick_capture.urlopen") as urlopen:
        assert quick_capture.fetch_youtube_title("https://example.com/x") is None
    urlopen.assert_not_called()


def test_fetch_youtube_title_soft_fails():
    with mock.patch("quick_capture.urlopen", side_effect=TimeoutError("nope")):
        assert quick_capture.fetch_youtube_title("https://youtu.be/abc") is None


def test_merge_day_entry_starter_appends_notes():
    entries = {
        "2026-07-20": {
            "Body & Presence": {
                "rating": 7,
                "checklist": {"Walked": True},
                "metrics": {},
                "notes": "Already logged",
            }
        }
    }
    quick_capture.merge_day_entry_starter(
        entries,
        date_str="2026-07-20",
        category="Body & Presence",
        url="https://youtu.be/abc",
        title="Demo Video",
        when=datetime(2026, 7, 20, 14, 32),
    )
    entry = entries["2026-07-20"]["Body & Presence"]
    assert entry["rating"] == 7
    assert entry["checklist"] == {"Walked": True}
    assert "Demo Video" in entry["notes"]
    assert "https://youtu.be/abc" in entry["notes"]
    assert "Already logged" in entry["notes"]
    assert entry["notes"].index("Demo Video") < entry["notes"].index("Already logged")


def test_merge_day_entry_starter_creates_new():
    entries: dict = {}
    quick_capture.merge_day_entry_starter(
        entries,
        date_str="2026-07-20",
        category="Creative/Mental Work",
        url="https://example.com/post",
        title="",
        when=datetime(2026, 7, 20, 9, 0),
    )
    entry = entries["2026-07-20"]["Creative/Mental Work"]
    assert entry["rating"] == 5
    assert "https://example.com/post" in entry["notes"]
    assert "[Quick Capture 09:00]" in entry["notes"]
