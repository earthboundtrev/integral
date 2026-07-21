---
id: SPEC-317
title: Pre-configured Life Domain templates (Gut Healing starter pack)
phase: phase-3
status: done
prd_refs: [PRD §5 Epic C]
adr_refs: [ADR-001, ADR-002, ADR-005, ADR-007]
github: https://github.com/earthboundtrev/integral/issues/36
depends_on: [SPEC-305]
---

# SPEC-317: Domain templates

## 1. Target (Outcome)

A user can apply a **template** (starting with a **Gut Healing Starter Pack**) that adds a
coherent set of pre-configured Life Domains (checklists + metrics) in one click, from the
category editor and during onboarding. Non-destructive: existing domains and entries are
untouched.

## 2. Boundary

**In:**

- `domain_templates.py` — new module: `DOMAIN_TEMPLATES`, `list_templates`, `get_template`,
  `apply_template` (pure, non-destructive merge returning added/skipped).
- `integral_dialogs.py` — `show_template_picker` dialog; onboarding "start with a template".
- `personal_dev_tracker.py` — "Apply Template…" button in the category editor.
- Tests + docs.

**Out:**

- No change to the per-domain schema (`checklist` + `metrics` only).
- No symptom correlations / practice logging (see #37/#38).

## 3. Design / Data

Templates reuse the existing category schema from `storage.get_default_categories()`:

```python
DOMAIN_TEMPLATES["gut_healing"]["domains"]["Gut Health / Digestion"] = {
    "checklist": ["No gluten today", ...],
    "metrics": [{"name": "Gas / bloating (lower = better)", "type": "rating", "min": 1, "max": 10, "default": 5}],
}
```

`apply_template(categories, template_id) -> (new_categories, added, skipped)`:
existing domain names are **skipped** (never overwritten); new ones deep-copied in.

## 4. Acceptance Criteria

1. Applying "Gut Healing Starter Pack" adds 6–8 relevant domains with sensible defaults.
2. Apply is non-destructive — existing domains/entries unchanged; re-applying adds nothing.
3. All existing domain functionality (rating, checklist, metrics, notes, streaks, edit,
   export/backup) keeps working.
4. Templates live in a clean, extensible structure so new packs are easy to add.
5. Export → restore/import still roundtrips after applying a template.

## 5. Verification

- `python -m unittest discover -s tests -v` (template structure + non-destructive merge).
- Manual: category editor → Apply Template → domains appear; onboarding path.

## 6. Tasks

1. `domain_templates.py` (data + pure apply).
2. `show_template_picker` + wire editor button + onboarding.
3. Tests + docs (README, CHANGELOG, spec done).

## 7. Loop

Max 3 retries per AC; fix within boundary files or amend this spec.
