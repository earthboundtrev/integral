# Data Model Reference

## Life Domain Entry (Phase 1)

### Category Definition

```python
{
  "checklist": list[str],           # Daily yes/no items
  "metrics": list[MetricDef]        # Typed measurements
}
```

### MetricDef

| Field | Required | Values |
|-------|----------|--------|
| `name` | yes | string |
| `type` | yes | `"number"` \| `"rating"` |
| `unit` | no | `"$"`, `"hrs"`, `"min"`, `""` |
| `default` | no | number |
| `min`, `max` | ratings only | 1–10 |

### Daily Entry (per category per date)

| Field | Type | Notes |
|-------|------|-------|
| `rating` | int 1–10 | Overall progress for the day |
| `checklist` | dict[str, bool] | Item → checked |
| `metrics` | dict[str, number] | Metric name → value |
| `notes` | string | Free journal text |

### Streak Logic

- **Overall streak**: consecutive calendar days with honest presence — ≥1 life-domain category logged, **or** ≥1 non-empty journal entry, **or** ≥1 fitness session — ending today (with mid-day grace if today is still empty).
- **Category streak**: consecutive days with that specific life-domain category logged (journal/fitness do not count).
- Missing today breaks the streak only after the day ends (grace until midnight local).
- **Gap repair (human, not gamified):** a silent miss breaks continuity; writing a **backdated journal** for the missed day (with the existing honesty reason) makes that day engaged again so consecutive days can reconnect. No freeze tokens.
- **Cross-links:** journal bodies may contain `[[journal:{id}|label]]`, `[[domain:YYYY-MM-DD|Category]]`, `[[fitness:YYYY-MM-DD]]`, `[[project:{id}]]`, or matching `integral://…` URIs; clicking opens the target. Optional Windows protocol registration (Data & Security) lets those URLs open Integral from other apps.
- **Formatting:** journal bodies support markdown-lite (`**bold**`, `*italic*`, `` `code` ``, `#` headings, `>` quotes, `-` lists) rendered in the editor.
- **Backlinks:** journal window lists other entries that link to the current one.

---

## Fitness Entities (Phase 2)

See [PROGRESSION_MODEL.md](./PROGRESSION_MODEL.md) for full graph spec.

### WorkoutSession

| Field | Type |
|-------|------|
| `id` | UUID |
| `date` | YYYY-MM-DD |
| `duration_minutes` | int? |
| `notes` | string |
| `body_weight_kg` | float? |

### WorkoutSet

| Field | Type |
|-------|------|
| `session_id` | UUID |
| `exercise_id` | UUID |
| `sets` | int |
| `reps` | int? |
| `hold_seconds` | float? |
| `weight_kg` | float? |
| `rpe` | int 1–10? |

### BodyCompositionLog

| Field | Type |
|-------|------|
| `date` | YYYY-MM-DD |
| `weight_kg` | float? |
| `measurements` | JSON (chest, waist, etc.) |
| `photo_path` | string? |

---

## Source Books (Fitness Seed)

| Code | Full Name |
|------|-----------|
| `CC1` | Convict Conditioning |
| `CC2` | Convict Conditioning 2 |
| `EC` | Explosive Calisthenics |
| `OG` | Overcoming Gravity |
| `SS` | Starting Strength |
| `FTR` | Five Tibetan Rites |

Seed files versioned as `progression/seed/v1/`. Bump version when adding exercises; migrate user progress forward.

---

## Creative Writing Projects (Phase 3)

Index key in `data.json`: `creative_projects`

```json
{
  "schema_version": 1,
  "projects": [
    {
      "id": "a1b2c3d4e5f6",
      "title": "Working title",
      "status": "idea|drafting|revising|done",
      "tags": ["novel"],
      "notes": "Optional short blurb",
      "created_at": "ISO-8601",
      "updated_at": "ISO-8601",
      "archived": false
    }
  ]
}
```

Document bodies are **not** stored in `data.json`. Files live under:

```
{user_data_dir}/creative/{project_id}/inspiration.txt
{user_data_dir}/creative/{project_id}/manuscript.txt
```

On Windows (frozen or typical): `%APPDATA%\Integral\creative\...`

---

## Daily Practices (Phase 3)

Index key in `data.json`: `practices`. Lightweight daily routines that are **not** part of the
progressive fitness DAG (Tibetan Rites, breathing, yoga holds). Logging a practice also appends
a summary line into the linked Life Domain's day entry (so it counts for history/streaks/AI).

```json
{
  "items": [
    {
      "id": "12hex",
      "date": "2026-07-21",
      "name": "Five Tibetan Rites",
      "preset": "tibetan_rites",
      "duration_minutes": 12,
      "completions": 9,
      "sets": null,
      "hold_seconds": null,
      "per_side": false,
      "quality": 8,
      "effect": "Big energy boost, less daytime sleepiness",
      "movements": [
        {"name": "Rite 1 — Spin", "reps": 9, "hold_seconds": null, "quality": null},
        {"name": "Rite 2 — Leg Raise", "reps": 9, "hold_seconds": null, "quality": null}
      ],
      "notes": "Felt strong energy after",
      "domain": "Physical Practices & Movement"
    }
  ]
}
```

Presets live in `practices.py` (`PRACTICE_PRESETS`) and declare which fields + labels a routine
surfaces plus its default linked domain. A preset may also declare `movements` (a list of names),
which enables an optional **per-movement** log (reps per movement) in the dialog. The optional
`effect` field captures the subjective result ("energy boost?", "reduced sleepiness?") and, with
the per-movement breakdown, is written into the linked domain note (feeding correlations + AI).
Extend `PRACTICE_PRESETS` to add a routine — no schema change needed.

