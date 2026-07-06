---
id: SPEC-207
title: Body composition logging
phase: phase-2
status: done
prd_refs: [PRD §5 Phase 2]
adr_refs: [ADR-002, ADR-004]
---

# SPEC-207: Body Composition Logging

## 1. Target (Outcome)

Users can log weight, waist/chest/hips measurements, and optional photo path references locally per profile.

## 2. Boundary (Scope)

### Files allowed
- `progression/db.py`, `progression/models.py`
- `body_composition_ui.py`
- `fitness_ui.py`

## 5. Verification

- AC1: `body_composition_logs` table created — pytest via session tests
- AC2: UI opens from Fitness Progress footer — manual
