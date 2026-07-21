---
id: SPEC-324
title: Personal AI insight kinds — vitality, sleep/hypersomnia, neurodivergence, alignment
phase: phase-3
status: done
prd_refs: [PRD §5 Epic C]
adr_refs: [ADR-001, ADR-002, ADR-007]
github: https://github.com/earthboundtrev/integral/issues/42
depends_on: [SPEC-319, SPEC-321]
---

# SPEC-324: Personal AI insight kinds

## 1. Target (Outcome)

Four new **optional, fully-local** Ollama insight kinds focused on my concerns — Vitality &
Anti-Aging, Sleep & Hypersomnia, Neurodivergence & Alignment, and Life Alignment & Goals —
reasoning over the domains (#40), practice/effect note lines (#37/#41), symptom metrics, and
journal reflections (#43) already present in the AI context.

## 2. Boundary

**In:** `ai_insights.py` — new `INSIGHT_KINDS` entries (prompts only). Tests + docs.
**Out:** No new context plumbing (context already includes domains/journal/fitness); no network;
no changes to the rule-based engine (covered by #38/#39).

## 3. Design / Data

Each kind is a dict entry: `{label, default_days, system, user_intro}`. `INSIGHT_KIND_ORDER`
derives from `INSIGHT_KINDS` keys, so the picker lists them automatically. Prompts instruct the
model to avoid inventing data and to act as a coach, not a doctor. Slow-moving signals get longer
default windows (21–30 days).

## 4. Acceptance Criteria

1. New kinds for Vitality, Sleep/Hypersomnia, Neurodivergence/Alignment, and Alignment/Goals
   appear in the AI insight picker.
2. Each has `label`, `default_days`, `system`, and `user_intro`; `build_chat_messages` works.
3. Prompts pull from the relevant domains + journal + practice lines (no new plumbing needed).
4. Fully local/private (Ollama only; no network calls added); works when Ollama absent.
5. Prompts instruct no-invented-data + coach-not-doctor.

## 5. Verification

- `python -m unittest discover -s tests -v` (kinds present + required keys + build_chat_messages).
- Manual: AI Insights picker shows the 4 kinds; running one produces focused output.

## 6. Tasks

1. Add 4 `INSIGHT_KINDS` entries.
2. Tests + docs.

## 7. Loop

Max 3 retries per AC; fix within boundary files or amend this spec.
