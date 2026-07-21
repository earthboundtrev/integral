---
id: SPEC-318
title: Daily practice logging — duration, reps/completions, quality, notes
phase: phase-3
status: done
prd_refs: [PRD §5 Epic C]
adr_refs: [ADR-001, ADR-002, ADR-007]
github: https://github.com/earthboundtrev/integral/issues/37
depends_on: [SPEC-317, SPEC-315]
---

# SPEC-318: Daily practice logging

## 1. Target (Outcome)

Users can quickly log **daily practices/routines** that are not progressive-DAG exercises —
Five Tibetan Rites, wind-releasing yoga (Pavanamuktasana), diaphragmatic breathing, generic
yoga/movement — capturing **duration (min)**, **reps/completions/sets**, **hold time (per side)**,
a **quality (1–10)**, and **notes**. Logged practices bridge into the linked Life Domain's day
entry so they appear in history, contribute to streaks, and feed AI insights. Existing CC
program logging keeps working and now shows **form quality** in session summaries.

## 2. Boundary

**In:**

- `practices.py` — presets + CRUD + summary + `merge_practice_line` (pure logic).
- `personal_dev_tracker.py` — `self.practices` in payload/load; log-practice dialog.
- `quick_capture_ui.py` — "Log practice" entry in the quick-log launcher.
- `progression/sessions.py` — include `form_quality` in `format_session_summary`.
- Tests + docs.

**Out:**

- Per-rite breakdown for Tibetan Rites (single session log for now).
- Symptom correlations (#38) and reminders (#39).

## 3. Design / Data

`data.json` gains a top-level `practices` store (mirrors `todos`):

```json
{ "items": [ {
  "id": "hex", "date": "2026-07-21", "name": "Five Tibetan Rites", "preset": "tibetan_rites",
  "duration_minutes": 12, "completions": 9, "sets": null, "hold_seconds": null,
  "per_side": false, "quality": 8, "notes": "Felt strong energy after",
  "domain": "Physical Practices & Movement" } ] }
```

Presets (`PRACTICE_PRESETS`) declare which fields + labels a practice shows, and a default
linked domain. Logging appends a readable summary line into the linked domain's day notes
(creating the entry at default rating if absent — same pattern as Quick Capture finish→log),
so it counts for history/streaks/AI. Backup roundtrips automatically (payload spread).

## 4. Acceptance Criteria

1. Users can log duration, reps/sets/completions, quality (1–10), and notes for a daily practice.
2. Five Tibetan Rites, Pavanamuktasana, diaphragmatic breathing, and generic movement have
   sensible default fields.
3. Existing CC session logging still works; `form_quality` now appears in session summaries.
4. Logged practices are saved and visible in history + AI context, and count toward streaks.
5. Practice presets/data live in a clean, extensible structure.
6. Export → restore/import still roundtrips with the new `practices` store.

## 5. Verification

- `python -m unittest discover -s tests -v` (practices CRUD, merge, summary, backup roundtrip).
- Manual: Quick Capture → Log practice → Tibetan Rites; entry appears in the day log.

## 6. Tasks

1. `practices.py` (presets + CRUD + merge + summary).
2. Tracker payload/load + log-practice dialog + Quick Capture entry.
3. `format_session_summary` form_quality.
4. Tests + docs.

## 7. Loop

Max 3 retries per AC; fix within boundary files or amend this spec.
