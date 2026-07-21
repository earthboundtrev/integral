---
id: SPEC-320
title: Practice-specific reminders + holistic guidance
phase: phase-3
status: done
prd_refs: [PRD §5 Epic C]
adr_refs: [ADR-001, ADR-002, ADR-007]
github: https://github.com/earthboundtrev/integral/issues/39
depends_on: [SPEC-318, SPEC-319]
---

# SPEC-320: Practice reminders + guidance

## 1. Target (Outcome)

Users can set reminders tied to specific practices (e.g. "Five Tibetan Rites + 10 min
breathing") that fire once/day at a chosen time, and the guidance engine surfaces
practice-consistency nudges alongside the practice→symptom correlations from #38.

## 2. Boundary

**In:**

- `notifications.py` — `practice_reminders` in settings + `due_practice_reminders` +
  scheduler integration.
- `integral_dialogs.py` — practice-reminder editor in the Reminders settings section.
- `insights/engine.py` — `analyze_practice_consistency`, threaded into `analyze_all`.
- Tests + docs.

**Out:**

- Reminder snooze/response actions; per-practice adaptive scheduling.

## 3. Design / Data

`settings.notifications.practice_reminders`: list of `{label, time (HH:MM), enabled}`.
`due_practice_reminders` fires each enabled reminder once per day (deduped via the existing
`reminder_state.sent_keys`, key = `practice:{time}:{label}`), independent of whether the day
is already logged. `analyze_practice_consistency` looks at the last 7 days: emits a positive
insight for well-kept practices and a watch insight when practices have stalled.

## 4. Acceptance Criteria

1. Users can add/remove practice reminders with a label and time; they persist and roundtrip.
2. A practice reminder fires at its time (once/day), respecting enabled/disabled and sent state.
3. Guidance surfaces practice-consistency findings (positive + stalled) via `analyze_all`.
4. AI insights remain context-aware of practices (via #38 bridged notes + gut_symptoms kind).
5. No regressions to existing daily reminders.

## 5. Verification

- `python -m unittest discover -s tests -v` (normalize, due timing, sent state, consistency).
- Manual: add a reminder in settings; it appears/fires; consistency shows in guidance.

## 6. Tasks

1. Practice reminders in notifications + scheduler.
2. Settings editor UI.
3. Consistency insight.
4. Tests + docs.

## 7. Loop

Max 3 retries per AC; fix within boundary files or amend this spec.
