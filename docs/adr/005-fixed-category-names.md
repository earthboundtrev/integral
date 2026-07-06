# ADR-005: Fixed Category Names

**Status:** Accepted  
**Date:** 2026-06-27

## Context

Eight life domains are foundational to dashboard layout, summaries, and future radar charts.

## Decision

These exact category names are stable API surface:

1. Money/Freedom
2. Body & Presence
3. Burnout Prevention & Energy Management
4. Creative/Mental Work
5. Family/Logistics
6. Search Practice
7. Spiritual Development
8. Emotional Wellbeing

Renaming requires a migration spec + data migration task.

## Agent Rules

- MUST use exact strings in seed data, UI, and tests
- MUST NOT alias or abbreviate in storage keys
