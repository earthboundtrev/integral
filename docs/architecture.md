# Architecture

## Current State (Phase 1)

Single-file Python desktop app using Tkinter.

```
personal-dev-tracker/
├── tracker.py              # Main app (or split when >800 lines)
├── docs/                   # Project documentation
├── .cursor/rules/          # Cursor agent rules
└── data/                   # Optional bundled defaults (categories seed)

User data (runtime):
~/.personal_dev_tracker/
└── data.json               # categories + daily entries
```

### Phase 1 Data Shape (`data.json`)

```json
{
  "categories": {
    "Body & Presence": {
      "checklist": ["..."],
      "metrics": [{ "name": "...", "type": "number|rating", "unit": "...", "default": 0 }]
    }
  },
  "entries": {
    "2026-06-27": {
      "Body & Presence": {
        "rating": 7,
        "checklist": { "Completed movement/exercise": true },
        "metrics": { "Sleep hours last night": 7.5 },
        "notes": "..."
      }
    }
  }
}
```

### Phase 1 UI Surfaces

| Surface | Purpose |
|---------|---------|
| Dashboard | 8 category cards, streaks, today's status |
| Log dialog | Rating, checklist, metrics, notes per category |
| Graphs & Summaries | Today / week / month stats + embedded charts |
| Full History | Chronological notes dump |
| Settings | Placeholder → future category editor |

## Target State (Phase 2+)

```
~/.personal_dev_tracker/
├── data.json               # Daily life-domain entries (unchanged)
├── fitness.db              # SQLite: exercises, edges, user progress, workout logs
└── photos/                 # Progress photos (filesystem refs in DB)
```

### Module Boundaries (When Splitting)

| Module | Responsibility |
|--------|----------------|
| `app.py` | Tk root, navigation, window lifecycle |
| `dashboard.py` | Category cards, streaks |
| `logging.py` | Log dialog, save entry |
| `summaries.py` | Today/week/month aggregation |
| `charts.py` | Lazy matplotlib; cache figures |
| `storage.py` | JSON load/save; future SQLite adapter |
| `progression/` | Graph model, mastery evaluator, unlock engine |
| `progression/seed/` | CC, OG, SS, FTR exercise + edge data |

### Layering Rules

1. **UI never reads files directly** — goes through `storage` layer.
2. **Summaries/charts are read-only views** — computed from in-memory data.
3. **Progression engine is pure logic** — no Tkinter imports; testable in isolation.
4. **Fitness workout log** links daily `entries` to `exercise_id` performances (Phase 2 bridge).

## Graphs & Summaries Spec

### Summaries Tab

| Period | Metrics |
|--------|---------|
| Today | Avg rating, categories logged, per-category completion |
| This Week | Avg rating, active days, streak, checklist completion % |
| Last 30 Days | Avg rating, active days, total notes count, best/worst category |

Precompute rolling windows on save; cache until next save.

### Graphs Tab

| Chart | Data |
|-------|------|
| Daily avg rating (30d line) | Mean of all category ratings per day |
| Category avg (bar, all-time) | Mean rating per category |
| Future: metric trends | Per-metric time series |
| Future: fitness skill tree | DAG visualization |
| Future: radar / life balance | 8-axis spider from category averages |

## Integration: Daily Tracker ↔ Fitness Graph

Daily category logging remains the **habit layer**. Fitness deep-tracking adds:

- Workout session → exercises performed → reps/holds/weight
- Mastery evaluation updates skill tree
- Dashboard "Body & Presence" card shows summary; fitness view shows skill tree detail

Do not merge into one monolithic form — link via shared date + category reference.
