---
id: SPEC-301
title: Life balance radar + recommendations
phase: phase-3
status: done
prd_refs: [PRD §6 Phase 3]
adr_refs: [ADR-001, ADR-003]
---

# SPEC-301: Life Balance Radar + Local Recommendations

## 1. Target (Outcome)

8-axis life balance radar chart in Graphs window. Dashboard shows local rule-based "What's Next" recommendations (no LLM).

## 2. Boundary (Scope)

### Files allowed
- `charts.py`, `recommendations.py`, `tracker.py`
- `tests/test_recommendations.py`

## 5. Verification

- AC1: Radar figure builds — pytest
- AC2: Recommendations include daily + fitness — pytest
- AC3: Dashboard panel visible — manual
