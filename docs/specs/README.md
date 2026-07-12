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
| [002-creative-projects-library](phase-3/002-creative-projects-library.md) | done | Creative writing projects library + storage ([#1](https://github.com/earthboundtrev/integral/issues/1)) |
| [003-creative-writing-windows](phase-3/003-creative-writing-windows.md) | done | Inspiration + manuscript windows ([#2](https://github.com/earthboundtrev/integral/issues/2)) |
| [004-creativity-writing-integration](phase-3/004-creativity-writing-integration.md) | done | Tie writing to Creative/Mental Work ([#3](https://github.com/earthboundtrev/integral/issues/3)) |
| [005-deep-work-mode](phase-3/005-deep-work-mode.md) | done | Deep Work Mode timer + focus UI ([#4](https://github.com/earthboundtrev/integral/issues/4)) |
| [006-notification-residency](phase-3/006-notification-residency.md) | done | Portable reminder residency ([#15](https://github.com/earthboundtrev/integral/issues/15)) |
| [007-streak-any-engagement](phase-3/007-streak-any-engagement.md) | done | Engagement streak: life + journal + fitness ([#18](https://github.com/earthboundtrev/integral/issues/18)) |
| [008-journal-gap-repair](phase-3/008-journal-gap-repair.md) | done | Human gap repair via backdated journal ([#19](https://github.com/earthboundtrev/integral/issues/19)) |
| [009-journal-cross-links](phase-3/009-journal-cross-links.md) | done | Journal entry cross-links ([#21](https://github.com/earthboundtrev/integral/issues/21)) |
| [013-os-protocol-handler](phase-3/013-os-protocol-handler.md) | done | Windows `integral://` OS deep links ([#22](https://github.com/earthboundtrev/integral/issues/22)) |

Implement writing stack in order **302 → 303 → 304**. **305** may proceed in parallel (soft dependency on 302/303 for optional writing launch).

## How to Add a Feature

1. Tell agent: "Write spec for [feature]" → uses `harness-spec-author`
2. Review spec, set `status: approved`
3. Tell agent: "Implement SPEC-NNN" → uses `harness-implement`
4. Tell agent: "Verify SPEC-NNN" → uses `harness-review`

You never write code.
