---
id: SPEC-204
title: Workout logging UI
phase: phase-2
status: done
prd_refs: [PRD Epic B4]
adr_refs: [ADR-001, ADR-006, ADR-008, ADR-009]
---

# SPEC-204: Workout Logging UI

## 1. Target

Tkinter window to log exercise performance against the fitness graph, evaluate mastery, and unlock next steps. Auto-loads CC1 push seed on first open if graph is empty.

**User story:** As a user, I want to log sets/reps for progression exercises, so that the skill tree advances when I meet mastery standards.

## 2. Boundary

### In scope
- Footer button **Fitness Progress**
- Toplevel with exercise list (available + in_progress + mastered summary)
- Log dialog: sets, reps, optional hold seconds, optional weight
- Calls `record_performance()` from progression engine
- Uses active profile's `fitness.db`
- Seeds CC1 push on first open if no exercises

### Out of scope
- Skill tree graph visualization (SPEC-205)
- Workout session history table (future)
- Body composition (SPEC-206)

### Files allowed
- `fitness_ui.py` (create)
- `tracker.py` (wire button)
- `tests/test_fitness_ui.py` (logic tests only, no full tk if flaky)

### Dependencies
- SPEC-201, SPEC-202, SPEC-203 `done`

## 4. Acceptance Criteria (EARS)

| ID | Criterion |
|----|-----------|
| AC-1 | **When** user opens Fitness Progress with empty DB, **the** system **shall** load CC1 push seed. |
| AC-2 | **When** user logs performance meeting mastery, **the** exercise **shall** show as mastered in the list. |
| AC-3 | **When** mastery unlocks a downstream exercise, **the** list **shall** show the next exercise as available. |
| AC-4 | **The** fitness UI **shall** use the active profile's fitness database. |
| AC-5 | **The** fitness window **shall** open without importing matplotlib. |

## 5. Verification

| AC ID | Method |
|-------|--------|
| AC-1–AC-4 | `python -m pytest tests/test_fitness_ui.py -v` |
| AC-5 | `python -X importtime -c "import fitness_ui"` — no matplotlib |

## 6. Tasks

- [ ] T1: Create `fitness_ui.py` with list + log dialog
- [ ] T2: Wire `tracker.py` footer button
- [ ] T3: Auto-seed + profile-scoped repo
- [ ] T4: Tests for seed-on-empty and mastery unlock display logic

## 8. Revision History

| Date | Change |
|------|--------|
| 2026-06-27 | Implemented workout logging UI |
