---
id: SPEC-209
title: Skill tree v2 (filters + click-to-log)
phase: phase-2
status: done
prd_refs: [PRD §5 Phase 2]
adr_refs: [ADR-001]
---

# SPEC-209: Skill Tree v2

## 1. Target (Outcome)

Skill tree supports book/family filters, multi-column DAG layout, recommended-edge styling, and click-to-log.

## 2. Boundary (Scope)

### Files allowed
- `skill_tree.py`
- `fitness_ui.py`
- `tests/test_skill_tree.py`

## 5. Verification

- AC1: Full model has 91 nodes — pytest
- AC2: Filter by book works — pytest
- AC3: Click-to-log wired — manual
