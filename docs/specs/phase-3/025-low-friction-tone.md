---
id: SPEC-325
title: Low-friction tone — optional depth without mandatory completeness
phase: phase-3
status: done
prd_refs: [PRD §5]
adr_refs: [ADR-001, ADR-007]
github: https://github.com/earthboundtrev/integral/issues/46
depends_on: []
---

# SPEC-325: Low-friction / non-punitive logging tone

## 1. Target

Partial and light days feel like wins. Unused domains stay quiet. Copy, guidance severity,
dashboard stats, reminders, and AI prompts stop framing completeness as obligation.

## 2. Boundary

**In:** `insights/engine.py`, `notifications.py`, `ai_insights.py`, `personal_dev_tracker.py`
(dashboard/log bar copy), onboarding copy in `integral_dialogs.py`, tests, README/CHANGELOG.

**Out:** New settings UI for “coverage coaching” (deferred); schema changes; removing domains.

## 3. Acceptance Criteria

1. No default “N/total domains” completeness score on the dashboard log bar.
2. Never-logged domains do not spam guidance; long gaps are invitational info, not action.
3. Reminder/AI copy does not imply full multi-domain daily logging.
4. Docs restate optional depth / low friction.

## 4. Verification

`python -m pytest tests/test_insights_engine.py tests/test_notifications.py tests/test_ai_insights.py -q`
