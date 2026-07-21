---
id: SPEC-319
title: Symptom tracking + practice→symptom correlations
phase: phase-3
status: done
prd_refs: [PRD §5 Epic C]
adr_refs: [ADR-001, ADR-002, ADR-007]
github: https://github.com/earthboundtrev/integral/issues/38
depends_on: [SPEC-317, SPEC-318]
---

# SPEC-319: Symptom tracking + correlations

## 1. Target (Outcome)

Symptoms (gas, bloating, stomach comfort, energy, regularity, well-being) are tracked as
Life Domain metrics (already possible via #36 Gut Healing pack). This spec adds **practice →
symptom correlation** findings: comparing a symptom metric on **days with a logged practice**
vs **days without**, surfaced in the rule-based guidance engine, plus a symptom-focused AI
insight kind.

## 2. Boundary

**In:**

- `insights/engine.py` — `analyze_practice_symptom_correlations(...)`, threaded into
  `analyze_all(..., practices=...)`.
- `personal_dev_tracker.py` — pass `self.practices` to `analyze_all` call sites.
- `ai_insights.py` — add a "Gut & symptom patterns" insight kind (prompt only).
- Tests + docs.

**Out:**

- No new persisted schema (symptoms are existing metrics; practices from #37).
- Charts are optional and deferred.

## 3. Design / Data

Symptom metrics are detected by name hints (`gas`, `bloat`, `stomach comfort`, `regularity`,
`energy`, `well-being`, `comfort`). "Lower is better" for gas/bloating.

For a lookback window (default 21 days):

- `practice_days` = dates with ≥1 logged practice (`practices.items[].date`).
- For each symptom metric, compute mean on practice days vs non-practice days.
- Require ≥ `min_samples` (default 3) on each side and |delta| ≥ 0.5 to emit a finding.
- Positive severity when practice days are *better* (lower for lower-is-better metrics,
  higher otherwise); watch otherwise.

## 4. Acceptance Criteria

1. Users can quickly log symptoms as metrics (via #36 gut pack; no new flow required).
2. `analyze_practice_symptom_correlations` emits a finding like "Lower average gas on days
   with practice (3.2 vs 5.1)", guarded by a minimum sample size.
3. Findings appear in the existing guidance/insights surfaces (via `analyze_all`).
4. A symptom-focused AI insight kind exists and asks for practice-vs-symptom patterns.
5. No regressions; existing insights keep working.

## 5. Verification

- `python -m unittest discover -s tests -v` (correlation math + sample guard + direction).
- Manual: log a symptom metric + practices; guidance shows the correlation.

## 6. Tasks

1. Correlation analyzer + thread through `analyze_all`.
2. Tracker call sites pass practices.
3. AI insight kind.
4. Tests + docs.

## 7. Loop

Max 3 retries per AC; fix within boundary files or amend this spec.
