---
id: SPEC-006
title: Settings placeholder
phase: phase-1
status: done
prd_refs: [PRD Epic A6]
adr_refs: [ADR-007]
---

# SPEC-006: Settings Placeholder

## 1. Target

Settings button shows informative message that full editor is future work; directs user to edit JSON for now.

## 2. Boundary

### In scope
- `show_settings_placeholder()` messagebox
- Text: full editor coming soon; edit `~/.personal_dev_tracker/data.json` directly for now

### Out of scope
- In-app category editor

### Files allowed
- `tracker.py`

### Dependencies
- SPEC-001 `done`

## 4. Acceptance Criteria (EARS)

| ID | Criterion |
|----|-----------|
| AC-1 | **When** user clicks Settings, **the** system **shall** show an info dialog with path to data file. |

## 5. Verification

| AC ID | Method |
|-------|--------|
| AC-1 | Manual click test |

## 6. Tasks

- [ ] T1: Implement `show_settings_placeholder()` with `messagebox.showinfo`
- [ ] T2: Wire Settings footer button

## 8. Revision History

| Date | Change |
|------|--------|
| 2026-06-27 | Initial approved spec |
