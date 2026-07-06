---
id: SPEC-208
title: Workout session history
phase: phase-2
status: done
prd_refs: [PRD §5 Phase 2]
adr_refs: [ADR-004]
---

# SPEC-208: Workout Session History

## 1. Target (Outcome)

Users log multi-exercise workout sessions with notes, duration, and body weight. Sessions link to Body & Presence daily checklist.

## 2. Boundary (Scope)

### Files allowed
- `progression/db.py`, `progression/models.py`, `progression/sessions.py`
- `fitness_ui.py`
- `tests/test_fitness_ui.py`

## 5. Verification

- AC1: Session + sets persist — pytest
- AC2: Body & Presence checklist updated — pytest
- AC3: Session history view — manual
