# Constitution (Decision Log)

Immutable decisions for AI agents. Full ADRs in `docs/adr/`. Cursor rule: `.cursor/rules/constitution.mdc`.

**Principle:** Decision logs + specs = agent contract. Code is derivative.

| ADR | Decision | Status |
|-----|----------|--------|
| [001](adr/001-python-tkinter-stack.md) | Python + Tkinter; not C++/Electron | Accepted |
| [002](adr/002-local-first-storage.md) | `~/.personal_dev_tracker/` local only | Accepted |
| [003](adr/003-lazy-matplotlib.md) | matplotlib lazy-import only | Accepted |
| [004](adr/004-sqlite-fitness-phase.md) | SQLite for Phase 2 fitness graph | Accepted |
| [005](adr/005-fixed-category-names.md) | 8 fixed category names | Accepted |
| [006](adr/006-progression-dag.md) | Exercise progression as DAG | Accepted |
| [007](adr/007-spec-driven-only.md) | No code without approved spec | Accepted |
| [008](adr/008-local-multi-profile.md) | Local multi-profile accounts on one machine | Accepted |
| [009](adr/009-standalone-exe-distribution.md) | Standalone EXE, local-first user data | Accepted |

## Adding a Decision

1. Copy `docs/adr/000-template.md` (or any ADR as format)
2. Number next sequentially
3. Status: `Proposed` → human sets `Accepted`
4. Agents must comply immediately once Accepted

## Superseding

Never delete ADRs. New ADR states "Supersedes ADR-NNN" and old ADR status → `Superseded`.
