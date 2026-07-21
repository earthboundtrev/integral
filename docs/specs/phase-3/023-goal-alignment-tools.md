---
id: SPEC-323
title: Light goal development & life alignment tools
phase: phase-3
status: done
prd_refs: [PRD §5 Epic C]
adr_refs: [ADR-001, ADR-003, ADR-007]
github: https://github.com/earthboundtrev/integral/issues/43
depends_on: [SPEC-321]
---

# SPEC-323: Goal development & alignment tools

## 1. Target (Outcome)

Lightweight goal/alignment tooling: milestones can link to a **Life Domain** and carry a simple
**progress %**; the journal gains a few **alignment/neurodivergence/goal reflection prompts**;
progress shows in the milestones list and summary. No project-management bloat; matplotlib stays
lazy (ADR-003).

## 2. Boundary

**In:**

- `milestones.py` — `domain` + `progress` fields; `normalize_milestone`; summary tweak.
- `integral_dialogs.py` — linked-domain combobox + progress input in the Milestones dialog;
  progress shown in the list.
- `journal.py` — reflection prompts.
- `integral_io.py` — milestones CSV gains `domain`, `progress` columns.
- Tests + docs.

**Out:**

- Radar/alignment chart (deferred to avoid bloat; text progress is enough).
- New top-level storage (milestones already persisted).

## 3. Design / Data

Milestone item gains `domain: str` (linked Life Domain, may be "") and `progress: int` (0–100).
`normalize_milestone` backfills defaults so old data upgrades cleanly. Setting status `done`
snaps progress to 100. Journal↔milestone linkage reuses existing `[[journal:…]]`/`[[domain:…]]`
backlinks (milestone notes can contain them). CSV export adds the two columns so it keeps
roundtripping (`.cursor/rules/backup-export.mdc`).

## 4. Acceptance Criteria

1. A milestone can link to an existing domain and store a progress % (0–100).
2. Simple progress tracking: progress shows in the list + summary; `done` → 100%.
3. A few alignment/autism/goal reflection prompts are available in the journal.
4. No bloat; existing milestones/journal keep working; old data upgrades with defaults.
5. Export/import: JSON backup + milestones CSV still roundtrip with the new fields.

## 5. Verification

- `python -m unittest discover -s tests -v` (normalize/defaults, progress clamp, CSV columns, prompts).
- Manual: Milestones dialog → link a domain + set progress; journal shows new prompts.

## 6. Tasks

1. `milestones.py` fields + normalize + summary.
2. Milestones dialog UI (domain + progress).
3. Journal prompts.
4. CSV columns.
5. Tests + docs.

## 7. Loop

Max 3 retries per AC; fix within boundary files or amend this spec.
