"""SPEC-323 goal development & alignment tools."""

import csv
import os
import tempfile

import journal
import milestones
from integral_io import export_milestones_csv


def test_normalize_backfills_domain_and_progress():
    m = milestones.normalize_milestone({"title": "Old milestone", "status": "open"})
    assert m["domain"] == ""
    assert m["progress"] == 0
    assert m["title"] == "Old milestone"


def test_progress_clamped_and_done_snaps_to_100():
    assert milestones.normalize_milestone({"title": "x", "progress": 250})["progress"] == 100
    assert milestones.normalize_milestone({"title": "x", "progress": -5})["progress"] == 0
    done = milestones.normalize_milestone({"title": "x", "status": "done", "progress": 10})
    assert done["progress"] == 100


def test_merge_upgrades_legacy_items():
    merged = milestones.merge_milestones(
        [{"title": "Improve hypersomnia management", "status": "in_progress", "progress": 40}]
    )
    assert merged[0]["progress"] == 40
    assert "domain" in merged[0]


def test_summary_includes_avg_progress():
    summary = milestones.milestone_summary(
        [
            {"status": "done", "progress": 100},
            {"status": "open", "progress": 20},
        ]
    )
    assert "1/2 complete" in summary
    assert "avg progress 60%" in summary


def test_milestones_csv_includes_new_columns():
    rows = [
        milestones.normalize_milestone(
            {"title": "Deepen autism understanding", "domain": "Neurodivergence & Self-Understanding", "progress": 30}
        )
    ]
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        export_milestones_csv(rows, path)
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            assert "domain" in reader.fieldnames
            assert "progress" in reader.fieldnames
            row = next(reader)
            assert row["domain"] == "Neurodivergence & Self-Understanding"
            assert row["progress"] == "30"
    finally:
        os.remove(path)


def test_alignment_prompts_available():
    prompts = journal.empty_journal()["prompts"]
    assert any("aligned" in p.lower() for p in prompts)
    assert any("masking" in p.lower() for p in prompts)
    assert any("autism" in p.lower() for p in prompts)


def test_normalize_journal_appends_new_prompts_for_existing_users():
    existing = {"prompts": ["Free write — no prompt"], "entries": []}
    normalized = journal.normalize_journal(existing)
    assert any("masking" in p.lower() for p in normalized["prompts"])
