---
id: SPEC-313
title: Windows integral:// OS protocol handler
phase: phase-3
status: done
prd_refs: [PRD §5 Epic C]
adr_refs: [ADR-001, ADR-002, ADR-007, ADR-009]
github: https://github.com/earthboundtrev/integral/issues/22
depends_on: [SPEC-309]
---

# SPEC-313: OS protocol handler for integral://

## 1. Target (Outcome)

Windows users can enable `integral://` so a link pasted outside Integral (browser, chat, notes) launches or focuses Integral and opens the target journal entry.

**User story:** As a user, I want integral://journal/{id} to work across my OS, so my notes are a navigable personal layer.

## 2. Boundary

### In scope
- HKCU registration of `integral` URL protocol (user-level, no admin)
- Toggle in Data & Security
- Argv parsing; second-instance handoff via pending file + instance lock
- Only `integral://journal/{12-hex-id}` accepted
- README note

### Out of scope
- HKLM / machine-wide install
- Browser extension
- Non-Windows platforms (toggle disabled)

### Files
- `protocol_windows.py`, `deep_links.py`, `personal_dev_tracker.py` (main), `integral_dialogs.py`
- `tests/test_protocol_windows.py`, README, specs README

## 4. Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-1 | Toggle registers/unregisters HKCU protocol |
| AC-2 | Launch with integral://journal/{id} opens that entry |
| AC-3 | If Integral already running, protocol launch hands off via pending file |
| AC-4 | Unknown URLs are rejected without crash |
| AC-5 | README documents the feature |

## 6. Tasks

- [x] Implemented with SPEC-309

## 8. Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-07-12 | agent | Spec + implement per human “must do” after approving 309 |
