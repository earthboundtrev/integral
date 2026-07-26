---
id: SPEC-326
title: Full export/backup/restore including creative sidecars
phase: phase-3
status: done
prd_refs: [PRD §5]
adr_refs: [ADR-001, ADR-002, ADR-007]
github: https://github.com/earthboundtrev/integral/issues/45
depends_on: []
---

# SPEC-326: Full-fidelity backup with creative documents

## 1. Target

Export / Backup / Restore round-trips **everything** needed to continue using Integral,
including Writing Projects inspiration + manuscript files under `creative/`.

## 2. Boundary

**In:** `backup.py`, `integral_io.py`, `integral_dialogs.py` (Export + Backup UI),
`creative_projects.py` helpers if needed, tests, docs.

**Out:** Changing where creative files live on disk; multi-profile creative isolation.

## 3. Design

- Profile zip (`backup.export_backup`) includes app-level `creative/**` sidecars.
- UI Backup defaults to a **full zip** (`data.json` + `creative/` + active `fitness.db`)
  via `integral_io.write_full_backup` / `restore_full_backup`; still accepts legacy JSON.
- CSV Export also writes a creative projects zip (or folder) of documents, and copy
  clarifies Backup for full restore fidelity.

## 4. Acceptance Criteria

1. Creative docs survive zip backup → restore. **Verified** via `test_full_backup_roundtrips_creative_documents` and `test_export_import_includes_creative_sidecars`.
2. CSV Export includes creative documents. **Verified** via `export_creative_documents_zip` + Export dialog.
3. Legacy JSON restore still works (index only; warn if creative missing). **Verified** via `test_legacy_json_restore_warns_about_creative`.
4. Tests cover creative sidecar roundtrip. **Verified** in `tests/test_backup.py` / `tests/test_integral_io.py`.

## 5. Verification

`python -m pytest tests/test_backup.py tests/test_integral_io.py -q`
