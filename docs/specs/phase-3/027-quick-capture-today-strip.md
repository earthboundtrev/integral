---
id: SPEC-327
title: Quick Capture on Today's Log action strip
phase: phase-3
status: done
prd_refs: [PRD Phase 3]
adr_refs: [ADR-001]
issue: 76
---

# SPEC-327: Quick Capture on Today's Log action strip

## 1. Target (Outcome)

Users can open Quick Capture from the **top Today's Log** action row (next to Journal /
More…), not only from the footer nav band.

**User story:** As a daily user, I want Quick Capture beside Journal / More so I can open
the panel without scrolling to the footer chrome.

## 2. Boundary (Scope)

### In scope
- Button on Today's Log horizontal actions strip calling `toggle_quick_capture`
- Docs/CHANGELOG/README as needed

### Out of scope
- Removing footer Quick Capture
- Changing panel behavior

### Files allowed
- `docs/specs/phase-3/027-quick-capture-today-strip.md`
- `personal_dev_tracker.py`
- `tests/test_quick_capture_ui.py` (or small dashboard label helper test)
- `README.md`, `CHANGELOG.md`

## 3. Design

Pack `Quick Capture` after `Journal` and before `More…` in the log_bar actions row.

## 4. Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-1 | **When** Today's Log is shown, **the** actions strip **shall** include a Quick Capture button. |
| AC-2 | **When** that button is clicked, **the** app **shall** toggle Quick Capture via existing `toggle_quick_capture`. |
| AC-3 | Footer Quick Capture **shall** still work. |
| AC-4 | Narrow windows: action strip remains horizontally scrollable. |

## 5. Verification

| AC | Method |
|----|--------|
| AC-1–3 | Manual smoke + code review of pack order / command= |
| AC-4 | Existing horizontal scroll tests still pass |

## 6. Tasks

- [x] T1: Spec
- [x] T2: Wire button
- [x] T3: Docs
- [x] T4: Pipeline → PR Closes #76

## 7. Loop

Max 3 retries; then blocked + ask human.

## 8. Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-08-03 | agent | Initial for #76 |
