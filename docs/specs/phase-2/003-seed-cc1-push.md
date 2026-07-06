---
id: SPEC-203
title: CC1 push progression seed (pilot)
phase: phase-2
status: done
prd_refs: [PRD Epic B3]
adr_refs: [ADR-006, ADR-008]
---

# SPEC-203: CC1 Push Progression Seed (Pilot)

## 1. Target

Ship testable seed data for Convict Conditioning 1 push-up chain (10 steps) and loader that populates the fitness DAG for the active profile.

## 2. Boundary

### In scope
- `progression/seed/v1/cc1_push.json`
- `progression/seed_loader.py`
- Tests proving load + mastery unlock chain

### Out of scope
- UI skill tree
- Other books (OG, SS, EC, FTR)

## 4. Acceptance Criteria (EARS)

| ID | Criterion |
|----|-----------|
| AC-1 | **The** seed **shall** include 10 CC1 push exercises and 9 prerequisite edges. |
| AC-2 | **When** seed is loaded twice, **the** system **shall** not duplicate exercises. |
| AC-3 | **When** Wall Push-ups are mastered per criteria, **the** next step **shall** become `available`. |

## 5. Verification

`python -m pytest tests/progression/test_cc1_seed.py -v` — 4 passed (2026-06-27).

## 8. Revision History

| Date | Change |
|------|--------|
| 2026-06-27 | Implemented CC1 push seed + tests |
