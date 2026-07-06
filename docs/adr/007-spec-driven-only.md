# ADR-007: Spec-Driven Implementation Only

**Status:** Accepted  
**Date:** 2026-06-27

## Context

Product owner will not write application code. All implementation must come from agents executing approved specs.

## Decision

1. **No code without an approved spec** in `docs/specs/` with `status: approved`.
2. **Spec is source of truth** — if code conflicts with spec, fix spec first (or amend spec with revision history), then re-implement.
3. **One spec ≈ one PR** — scope bounded by spec file list.
4. **Every feature has EARS acceptance criteria** with verification methods.
5. **Implementation follows the loop** in `docs/WORKFLOW.md`.

## Agent Rules

- MUST read spec + referenced ADRs before writing code
- MUST NOT implement from PRD alone — decompose into spec if missing
- MUST update spec status: `in_progress` → `done` with AC verification notes
- MUST stop and ask human if spec is ambiguous after 3 failed retries
