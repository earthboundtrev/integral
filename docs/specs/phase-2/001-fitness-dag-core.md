---
id: SPEC-201
title: Fitness DAG core entities
phase: phase-2
status: done
prd_refs: [PRD Epic B1]
adr_refs: [ADR-004, ADR-006]
---

# SPEC-201: Fitness DAG Core Entities

## 1. Target

SQLite schema and pure-Python progression module for Exercise, ProgressionEdge, UserExerciseProgress with DAG cycle validation.

**User story:** As a user, I want exercise relationships stored in a graph, so that cross-book progression can be tracked.

## 2. Boundary

### In scope
- `progression/models.py`, `progression/db.py`, `progression/validate.py`
- SQLite schema at `~/.personal_dev_tracker/fitness.db`
- CRUD for exercises and edges; cycle detection on prerequisite edges

### Out of scope
- UI, seed data, mastery evaluator (SPEC-202), workout logging (SPEC-204)

### Files allowed
- `progression/**`
- `tests/progression/**`

### Dependencies
- Phase 1 complete (all phase-1 specs `done`)

## 4. Acceptance Criteria (EARS)

| ID | Criterion |
|----|-----------|
| AC-1 | **When** a prerequisite edge would create a cycle, **the** system **shall** reject it with a clear error. |
| AC-2 | **The** progression module **shall** have no Tkinter imports. |
| AC-3 | **The** schema **shall** store mastery_criteria and unlock_condition as JSON text. |

## 5. Verification

| AC ID | Method |
|-------|--------|
| AC-1–AC-3 | `pytest tests/progression/` |

## 6. Tasks

- [ ] T1: Define schema + migrations bootstrap
- [ ] T2: Implement models and DB access layer
- [ ] T3: Implement cycle validation
- [ ] T4: Tests

## 7. Loop

- If cycle validation fails, inspect prerequisite-only traversal before changing schema.
- If schema changes are needed, update this spec first and re-run all `tests/progression/`.

## 8. Verification Notes

Verified 2026-06-27 with:

```bash
python -m pytest tests/ -v
```

Result: 16 passed.

## 9. Revision History

| Date | Change |
|------|--------|
| 2026-06-27 | Draft — approve before implement |
| 2026-06-27 | Implemented Phase 2 DAG core; marked done after tests passed |
