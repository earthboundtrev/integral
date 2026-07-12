---
id: SPEC-309
title: Journal entry cross-links
phase: phase-3
status: done
prd_refs: [PRD §5 Epic C]
adr_refs: [ADR-001, ADR-002, ADR-007]
github: https://github.com/earthboundtrev/integral/issues/21
epic: Writing & linking (forum-style)
---

# SPEC-309: Journal entry cross-links (slice 1)

## 1. Target (Outcome)

Users can insert and follow **in-app hyperlinks** to other journal entries. Clicking a link opens the Journal window focused on that entry.

**User story:** As a user, I want to link journal entries to each other and open the target on click, so related entries that stack stay navigable.

## 2. Boundary (Scope)

### In scope
- Wiki refs `[[journal:{id}]]` / `[[journal:{id}|label]]` and `integral://journal/{id}`
- Copy link / Insert link in Journal UI
- Clickable tags in journal body; day-view Open; search Open + linkify
- `show_journal_window(..., entry_id=...)`
- Missing id → warning

### Deferred
- Formatting (310), cross-entity (311), backlinks (312) — see epic in revision history of earlier draft
- OS registration of protocol — SPEC-313

### Files
- `journal.py`, `journal_ui.py`, `personal_dev_tracker.py`, tests, README, DATA_MODEL, specs README

## 4. Acceptance Criteria

| ID | Criterion | Verified |
|----|-----------|----------|
| AC-1 | Copy link puts wiki + integral:// on clipboard | Manual + code |
| AC-2 | Insert link inserts wiki ref | Manual + code |
| AC-3 | Click opens entry | Manual |
| AC-4 | Missing id warns | Code + tests get_entry |
| AC-5 | entry_id opens focused | Code |
| AC-6 | README mentions cross-links | Docs |

## 6. Tasks

- [x] T1–T5

## 8. Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-07-12 | agent | Draft; approved by human; implemented |
| 2026-07-12 | agent | Marked done with in-app links; OS protocol in SPEC-313 |
