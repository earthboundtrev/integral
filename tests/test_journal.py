from datetime import date

import pytest

import journal


def test_create_entry_requires_body():
    with pytest.raises(ValueError):
        journal.create_entry("2026-07-05", "   ")


def test_backdate_requires_reason():
    error = journal.validate_backdate("2026-01-01", today=date(2026, 7, 5), reason="too short")
    assert error is not None
    assert "reason" in error.lower()


def test_backdate_accepts_reason():
    error = journal.validate_backdate(
        "2026-01-01",
        today=date(2026, 7, 5),
        reason="Found my old CC training notebook from January.",
    )
    assert error is None


def test_create_backdated_entry_stores_reason():
    item = journal.create_entry(
        "2026-01-01",
        "Recovered notes from lost paper journal.",
        prompt="Fitness / CC training notes",
        backdate_reason="Found my old CC training notebook from January.",
    )
    assert item["backdate_reason"] is not None
    assert "Recovered notes" in item["body"]


def test_future_date_rejected():
    error = journal.validate_backdate("2099-01-01", today=date(2026, 7, 5))
    assert error is not None


def test_search_entries_matches_body():
    data = journal.empty_journal()
    journal.upsert_entry(
        data,
        journal.create_entry("2026-07-05", "Human flag progress felt shaky today."),
    )
    hits = journal.search_entries(data, "human flag")
    assert len(hits) == 1


def test_normalize_journal_keeps_default_prompts():
    data = journal.normalize_journal({"entries": []})
    assert journal.DEFAULT_PROMPTS[0] in data["prompts"]
