---
id: SPEC-314
title: Quick Capture mode (link → day entry + journal quick-start)
phase: phase-3
status: done
prd_refs: [PRD §5 Epic C — proposed C9]
adr_refs: [ADR-001, ADR-002, ADR-007]
github: https://github.com/earthboundtrev/integral/issues/32
depends_on: []
---

# SPEC-314: Quick Capture mode

## 1. Target (Outcome)

While living in the browser / other apps, the user can turn on a small always-on-top **Quick Capture** panel that reduces friction to two capture paths:

1. **Link → life domain** — paste a URL, pick a category, Save → starter day entry for today (editable later).
2. **Journal quick-start** — one control that opens (or creates) a journal draft for today with focus ready to type — for a thought, an X post, or whatever sparked reflection — without digging through full app chrome.

When Capture mode is **off**, Integral behaves as today (no overlay, no URL polling, no title network calls).

**User stories:**
- As someone who lives on YouTube, I want near-zero friction to park a link into the right life domain.
- As someone who gets a sudden thought while elsewhere, I want one click to start journaling without re-navigating the whole app.

## 2. Boundary (Scope)

### In scope
- Toggle in Data & Security + nav **Quick Capture**; default **off**
- Always-on-top mini window: link capture + Journal now (+ optional seed)
- Save merges starter into today’s category `notes` (no new schema fields)
- YouTube oEmbed title resolve (best-effort)
- README Features

### Out of scope
- Browser extension; continuous clipboard watch; global hotkeys; non-YouTube title fetch

### Files allowed
- `quick_capture.py`, `quick_capture_ui.py`
- `personal_dev_tracker.py`, `integral_dialogs.py`, `journal_ui.py`
- `full-spectrum-development.spec`
- `tests/test_quick_capture.py`
- `docs/specs/README.md`, `docs/PRD.md`, README, CHANGELOG, this spec

## 3. Design

Starter notes format: `[Quick Capture HH:MM] Title\nURL` prepended to existing notes.

Optional HTTPS: public YouTube oEmbed only while Capture is on / user pastes YouTube URL (no API key; soft-fail).

## 4. Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-1 | Off → no overlay, no oEmbed |
| AC-2 | On → topmost panel with link + Journal |
| AC-3 | Save URL+category → today’s starter in notes |
| AC-4 | YouTube + empty title + success → title filled |
| AC-5 | oEmbed fail / non-YouTube → Save still works |
| AC-6 | Journal now opens today’s journal ready to type |
| AC-7 | Seed line prepended into journal body |
| AC-8 | Default off |
| AC-9 | README Features |

## 5. Verification

| AC | Method |
|----|--------|
| AC-1, AC-4, AC-5, AC-8 | `tests/test_quick_capture.py` |
| AC-2, AC-3, AC-6, AC-7 | Manual + code paths |
| AC-9 | README |

## 6. Tasks

- [x] T1–T5

## 7. Loop

Max 3 retries; then `blocked`.

## 8. Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-07-20 | agent | Draft |
| 2026-07-20 | agent | Journal quick-start on same overlay |
| 2026-07-20 | agent | Implemented; done |

## 9. AC verification

| AC | Result |
|----|--------|
| AC-1/8 | settings default + panel destroy when off |
| AC-2 | `quick_capture_ui.open_quick_capture_panel` |
| AC-3 | `merge_day_entry_starter` |
| AC-4/5 | mocked oEmbed tests |
| AC-6/7 | `show_journal_window(..., seed=)` |
| AC-9 | README Features |
