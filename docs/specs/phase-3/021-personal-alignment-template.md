---
id: SPEC-321
title: Personal Health & Alignment domain template
phase: phase-3
status: done
prd_refs: [PRD §5 Epic C]
adr_refs: [ADR-001, ADR-005, ADR-007]
github: https://github.com/earthboundtrev/integral/issues/40
depends_on: [SPEC-317]
---

# SPEC-321: Personal Health & Alignment template

## 1. Target (Outcome)

A `personal_alignment` template ("Personal Health & Alignment") that applies 5 personal-first
domains — Vitality & Anti-Aging, Sleep & Hypersomnia Management, Neurodivergence &
Self-Understanding, Inflammation & Oxidative Stress, and Life Alignment & Goals — via the
existing #36 template picker (onboarding + category editor). Metrics are phrased with direction
(e.g. "daytime sleepiness (lower = better)") so #38 correlations read correctly.

## 2. Boundary

**In:** `domain_templates.py` (new template entry only); tests; docs.
**Out:** No UI/plumbing changes (picker already lists all templates); no schema change; no book IP.

## 3. Design / Data

Reuses the existing category schema and `apply_template` non-destructive merge from SPEC-317.
Book/protocol specifics are left generic; user edits checklist/notes for exact practices.

## 4. Acceptance Criteria

1. Applying "Personal Health & Alignment" adds 5–7 domains with sensible defaults.
2. Non-destructive (existing domains untouched; re-apply adds nothing) — inherited from SPEC-317.
3. Templates remain clean, editable Python dicts.
4. Symptom-style metrics use lower/higher directionality suitable for #38 correlations.
5. No IP issues (generic references only).

## 5. Verification

- `python -m unittest discover -s tests -v` (template shape + directionality + apply).
- Manual: category editor → Apply Template → "Personal Health & Alignment".

## 6. Tasks

1. Add `personal_alignment` to `DOMAIN_TEMPLATES`.
2. Tests + docs.

## 7. Loop

Max 3 retries per AC; fix within boundary files or amend this spec.
