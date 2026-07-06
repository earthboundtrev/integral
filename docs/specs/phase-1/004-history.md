---
id: SPEC-004
title: Full history view
phase: phase-1
status: done
prd_refs: [PRD Epic A4]
adr_refs: [ADR-001, ADR-007]
---

# SPEC-004: Full History View

## 1. Target

Toplevel window listing all entries reverse-chronologically with date headers, category, rating, and notes preview.

**User story:** As a user, I want to browse all past logs, so that I can review my journal over time.

## 2. Boundary

### In scope
- Opened from "View Full History" footer button
- Window 800×600, ScrolledText read-only
- Format: `=== YYYY-MM-DD ===` then per category rating + first 200 chars of notes
- Newest dates first

### Out of scope
- Search, filter, edit, delete

### Files allowed
- `tracker.py` or `history.py`

### Dependencies
- SPEC-001 `done`

## 4. Acceptance Criteria (EARS)

| ID | Criterion |
|----|-----------|
| AC-1 | **When** user clicks View Full History, **the** history window **shall** open. |
| AC-2 | **The** history **shall** list dates in descending order. |
| AC-3 | **For** each category entry, **the** view **shall** show category name, rating, and notes truncated to 200 characters. |
| AC-4 | **When** no entries exist, **the** window **shall** display an empty or informative message. |

## 5. Verification

| AC ID | Method |
|-------|--------|
| AC-1–AC-4 | Manual with seeded data; optional `tests/test_history.py` for formatting function |

## 6. Tasks

- [ ] T1: Extract `format_history(entries) -> str` for testing
- [ ] T2: Implement `show_history()` Toplevel + ScrolledText
- [ ] T3: Wire footer button

## 8. Revision History

| Date | Change |
|------|--------|
| 2026-06-27 | Initial approved spec |
