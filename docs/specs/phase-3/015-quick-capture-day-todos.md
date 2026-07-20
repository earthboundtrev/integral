---
id: SPEC-315
title: Quick Capture overlay — todos, schedule, finish→log, quick-log, focus shield
phase: phase-3
status: done
prd_refs: [PRD §5 Epic C — C10]
adr_refs: [ADR-001, ADR-002, ADR-007]
github: https://github.com/earthboundtrev/integral/issues/34
depends_on: [SPEC-314, SPEC-305]
---

# SPEC-315: Quick Capture day todos + quick-log + focus shield

## 1. Target (Outcome)

Quick Capture panel gains today/upcoming todos, finish→category log, quick-log launcher, Deep Work timer, and Windows focus shield (selective minimize + nudge).

## 2. Boundary

Shipped as implemented. OS Airplane Mode out of scope.

### JSON shape (`data.json` → `todos`)

```json
{
  "items": [
    {
      "id": "12hex",
      "text": "Renew plates",
      "done": false,
      "work_date": "2026-07-25",
      "category": "Money/Freedom"
    }
  ]
}
```

## 3–7

See prior draft revisions; tasks completed.

## 8. Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-07-20 | agent | Draft through focus shield |
| 2026-07-20 | agent | Implemented; done |

## 9. AC verification

| AC | Result |
|----|--------|
| AC-1–7 | `todos.py` + UI + `merge_todo_done_line` tests |
| AC-8–9 | Quick log combo → existing openers |
| AC-10–11 | Overlay Deep Work + timer refresh |
| AC-12–13 | `focus_shield.py` + start dialog checkboxes + poll |
| AC-14 | No airplane/radio APIs |
| AC-15 | README Features |
