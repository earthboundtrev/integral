# Spec Backlog

Implement **in order** unless a spec declares otherwise. Human sets `approved` → agent implements → review harness verifies AC → `done`.

## Phase 1 (MVP) — implement in this order

| Order | Spec | Status | Title |
|-------|------|--------|-------|
| 1 | [005-storage-and-seed](phase-1/005-storage-and-seed.md) | done | Storage + default categories |
| 2 | [001-dashboard](phase-1/001-dashboard.md) | done | Main dashboard |
| 3 | [002-daily-logging](phase-1/002-daily-logging.md) | done | Daily log dialog |
| 4 | [003-graphs-summaries](phase-1/003-graphs-summaries.md) | done | Graphs & Summaries |
| 5 | [004-history](phase-1/004-history.md) | done | Full history |
| 6 | [006-settings-placeholder](phase-1/006-settings-placeholder.md) | done | Settings placeholder |

## Infra

| Spec | Status | Title |
|------|--------|-------|
| [001-standalone-exe](infra/001-standalone-exe.md) | done | Windows EXE (local-first) |

## Phase 2 (Fitness DAG)

| Spec | Status | Title |
|------|--------|-------|
| [001-fitness-dag-core](phase-2/001-fitness-dag-core.md) | done | DAG entities + SQLite |
| [002-mastery-unlock](phase-2/002-mastery-unlock.md) | done | Mastery evaluator + unlock engine |
| [003-seed-cc1-push](phase-2/003-seed-cc1-push.md) | done | CC1 push seed (pilot) |
| [004-workout-logging](phase-2/004-workout-logging.md) | done | Workout logging UI |
| [005-skill-tree-ui](phase-2/005-skill-tree-ui.md) | done | Fitness skill tree visualization |
| [006-expand-seeds](phase-2/006-expand-seeds.md) | done | All book seeds (91 exercises) |
| [007-body-composition](phase-2/007-body-composition.md) | done | Body composition logging |
| [008-workout-sessions](phase-2/008-workout-sessions.md) | done | Workout session history |
| [009-skill-tree-v2](phase-2/009-skill-tree-v2.md) | done | Skill tree filters + click-to-log |

## Phase 3 (Cross-domain)

| Spec | Status | Title |
|------|--------|-------|
| [001-radar-recommendations](phase-3/001-radar-recommendations.md) | done | Life balance radar + recommendations |

More Phase 3 specs listed in `docs/PRD.md` §6 — create from template when ready.

## How to Add a Feature

1. Tell agent: "Write spec for [feature]" → uses `harness-spec-author`
2. Review spec, set `status: approved`
3. Tell agent: "Implement SPEC-NNN" → uses `harness-implement`
4. Tell agent: "Verify SPEC-NNN" → uses `harness-review`

You never write code.
