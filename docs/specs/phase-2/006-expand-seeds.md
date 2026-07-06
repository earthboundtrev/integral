---
id: SPEC-206
title: Expand fitness seeds (all books)
phase: phase-2
status: done
prd_refs: [PRD §5 Phase 2]
adr_refs: [ADR-004, ADR-006]
---

# SPEC-206: Expand Fitness Seeds (CC, OG, SS, EC, FTR, CC2)

## 1. Target (Outcome)

Load 91 exercises from CC1 (6 chains), Starting Strength, Overcoming Gravity, Explosive Calisthenics, Five Tibetan Rites, and CC2 sample, plus cross-book recommended edges.

## 2. Boundary (Scope)

### In scope
- Seed JSON files in `progression/seed/v1/`
- Generic `seed_from_file()` and `seed_all_fitness()` in `seed_loader.py`
- Incremental seeding for existing profiles

### Files allowed
- `progression/seed/v1/*.json`
- `progression/seed_loader.py`
- `fitness_ui.py` (ensure_fitness_seeded)
- `tests/progression/test_cc1_seed.py`
- `tests/test_fitness_ui.py`

## 5. Verification

- AC1: `seed_all_fitness` loads 91 exercises — pytest
- AC2: Cross-book recommended edges present — pytest
- AC3: Idempotent re-seed — pytest
