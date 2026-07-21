---
id: SPEC-322
title: Deeper practice logging — per-movement, Strong Medicine, effect links
phase: phase-3
status: done
prd_refs: [PRD §5 Epic C]
adr_refs: [ADR-001, ADR-002, ADR-007]
github: https://github.com/earthboundtrev/integral/issues/41
depends_on: [SPEC-318]
---

# SPEC-322: Practice logging depth

## 1. Target (Outcome)

Extend the #37 practice log (delta, not rebuild) with: (1) an optional **per-movement**
breakdown for routines that have movements (Five Tibetan Rites' 5 rites; Strong Medicine
lifts), (2) a **Strong Medicine** preset sourced from `programs/strong-medicine.json` (generic
names, no invented standards), (3) a subjective **effect** field ("energy boost? reduced
sleepiness? inflammation feel?") that flows into the linked domain notes (feeding #38
correlations + AI), and (4) **Fitness Hub parity** — reach the practice log from the hub.

## 2. Boundary

**In:**

- `practices.py` — `effect` + `movements` on items; `strong_medicine` preset; per-movement in
  presets; summary/note include movement + effect.
- `practices_ui.py` — per-movement rows + effect field.
- `fitness_ui.py` — "Log daily practice" entry point.
- Tests + docs.

**Out:**

- No new top-level data.json key (reuse #37 `practices` store; movements nest inside items).
- No changes to progression DAG / SQLite.

## 3. Design / Data

Practice item gains optional `effect: str` and `movements: [{name, reps?, hold_seconds?,
quality?}]`. Presets may declare `movements: [names]` (rendered as optional per-row inputs) and
include `effect` in their field list. Backup roundtrips automatically (payload spread). No
invented rep standards — Strong Medicine names are generic; the JSON `source` documents origin.

## 4. Acceptance Criteria

1. A routine with movements can be logged full-session **or** per-movement (reps per movement).
2. Strong Medicine preset exists with sensible generic movement defaults.
3. An `effect` field is captured and appears in the linked domain note (feeds #38 + AI).
4. Practice log reachable from the Fitness Hub (parity with Quick Capture).
5. Data visible in history/streaks/AI; logging stays optional/fast (<60s); backup roundtrips.
6. No invented progression standards (names match program JSON).

## 5. Verification

- `python -m unittest discover -s tests -v` (movements + effect normalize/summary/merge; preset).
- Manual: Fitness Hub → Log daily practice → Rites per-movement; note appears in the domain.

## 6. Tasks

1. `practices.py` effect + movements + strong_medicine preset.
2. `practices_ui.py` per-movement rows + effect field.
3. Fitness Hub entry point.
4. Tests + docs.

## 7. Loop

Max 3 retries per AC; fix within boundary files or amend this spec.
