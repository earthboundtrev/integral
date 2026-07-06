# ADR-002: Local-First Storage

**Status:** Accepted  
**Date:** 2026-06-27

## Context

Personal development data is sensitive. App must work offline.

## Decision

All user data lives under `~/.personal_dev_tracker/`. No cloud sync, accounts, or telemetry in core features.

## Paths

| Phase | Path | Contents |
|-------|------|----------|
| 1 | `data.json` | categories + daily entries |
| 2+ | `fitness.db` | exercises, edges, progress, workouts |
| 2+ | `photos/` | progress photos (filesystem refs in DB) |

## Agent Rules

- MUST NOT add network calls to core logging, storage, or chart flows
- MUST NOT send user notes/metrics to external services without new ADR + opt-in spec
