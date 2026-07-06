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

- **Overall streak**: consecutive calendar days with ≥1 category logged, ending today.
- **Category streak**: consecutive days with that specific category logged.
- Missing today breaks streak only after the day ends (grace until midnight local).

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
