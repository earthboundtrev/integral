# ADR-004: SQLite for Fitness Phase

**Status:** Accepted  
**Date:** 2026-06-27

## Context

Phase 1 JSON is sufficient for daily entries. Fitness graph (exercises, edges, user progress) needs relational queries.

## Decision

Introduce **SQLite** at `~/.personal_dev_tracker/fitness.db` when Phase 2 begins. Keep `data.json` for daily life-domain entries — do not merge into one store.

## Agent Rules

- Phase 1 specs MUST NOT add SQLite
- Phase 2+ fitness data MUST go through `storage` / `progression` modules, not raw SQL in UI
- Use `sqlite3` stdlib only — no SQLAlchemy without new ADR
