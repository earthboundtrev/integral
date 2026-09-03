---
name: review-architect
description: Run Integral pre-merge architect review after Bugbot and tests. Use when the user asks for /review-architect, architect review, pre-merge architecture review, or merge-ready review.
---

# Review Architect (Integral)

Use when the user asks to run `/review-architect` or **architect review** before PR.

This is the counterpart to **Bugbot** — Bugbot catches logic bugs; architect review catches layer violations, export/import gaps, missing README Features, and merge-readiness gaps.

## Pipeline stage: ARCHITECT

Ticket work uses the pointer pipeline in `.cursor/rules/ticket-lifecycle-loop.mdc`:

```
IMPLEMENT → BUGBOT → TESTS → ARCHITECT → DEPLOY
```

- Run **only after** **BUGBOT** is clean and **TESTS** pass on the current diff.
- **Merge-ready** → advance pointer to **DEPLOY**.
- **Blockers** → fix code, rewind pointer to **BUGBOT**, re-run Bugbot → Tests → Architect. Do not re-run architect-only after fixes.
- One merge-ready pass does not exit the ticket — human merge/sign-off on **DEPLOY** does.

## Standalone invocation

No active ticket → report findings only unless the user asks to fix.

## Prerequisites

If pointer is not past **TESTS**, or Bugbot has not run on the **current** diff, run **BUGBOT** first — even if an earlier session already ran it.

Launch Architect with **`model: "cursor-grok-4.6-high-fast"`** (fallback chain in `.cursor/rules/subagent-watchdog.mdc`). Do **not** omit `model`. Do **not** use Opus/Sonnet unless the user explicitly asks. Stay **local** — `.cursor/rules/prefer-local-agents.mdc`.

## Launch review

1. Read `.cursor/agents/integral-architect.md`.
2. Read `.cursor/rules/integral-architect.mdc`.
3. Launch exactly one readonly subagent:
   - `subagent_type: "integral-architect"` (or `generalPurpose` if that type is unavailable)
   - `model: "cursor-grok-4.6-high-fast"` (**required** — do not omit)
   - Prefer readonly / no edits unless the parent is fixing blockers after the review
   - `run_in_background: false` unless explicitly asked to run in background
   - `description: "Integral Architect"`
   - Omit `environment` or set `"local"`

Repository path: active workspace root. Do not compute the full diff yourself before launching.

### Branch checkout (same as Bugbot)

If the user asks to review a specific PR or branch, check out that branch first. Stash only after user confirms if checkout is blocked.

### Prompt shape

```text
You are the Integral Architect subagent. Follow the instructions in .cursor/agents/integral-architect.md in this repository.

Full Repository Path: <absolute repository path>
Diff: <one of: "branch changes", "uncommitted changes">
Base Branch: <only when reviewing against a specific base other than main>
GitHub issue: <#N if known, else "unknown">
Custom Instructions: <only when the user gave specific review instructions>
```

Default `Diff` to `branch changes`.

## After the subagent finishes

Summarize:

- **Verdict** — Merge-ready (→ DEPLOY) or N blockers (→ fix, rewind to BUGBOT)
- Blockers table: Severity | Location | Finding
- README Features and export/import status (one line)

**Ticket pipeline:** fix blockers, set pointer to **BUGBOT**. **Standalone:** fix only if asked.

## Related

- Pipeline: `.cursor/rules/ticket-lifecycle-loop.mdc`
- Rule: `.cursor/rules/integral-architect.mdc`
- Watchdog / models: `.cursor/rules/subagent-watchdog.mdc`
- Local agents: `.cursor/rules/prefer-local-agents.mdc`
- Bugbot: Cursor `review-bugbot` skill (**BUGBOT** stage)
- Security: `.cursor/rules/security-review.mdc`
