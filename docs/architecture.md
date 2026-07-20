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
| Dashboard | Category cards, engagement streak (life/journal/fitness), today's status |
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

## Creative Writing (Phase 3)

| Module | Responsibility |
|--------|----------------|
| `creative_projects.py` | Library index normalize/CRUD; inspiration/manuscript file I/O |
| `creative_ui.py` | Writing Projects library window + document editors |
| `paths.creative_projects_dir()` | `%APPDATA%\Integral\creative\` (or platform equivalent) |

Metadata lives in `data.json` under `creative_projects`; novel-length text stays on disk beside user data so daily loads stay lean.

Document windows (SPEC-303): Inspiration and Manuscript open as independent `Toplevel`s with debounced autosave; app quit flushes dirty editors via `flush_open_document_windows()`.

Creative/Mental Work integration (SPEC-304): log dialog links to Writing Projects; explicit “Log writing session” marks checklist item `Made progress on a creative project`.

Deep Work Mode (SPEC-305): `deep_work.py` timer + `deep_work_ui.py` start dialog; tracker hides non-essential nav while a session runs.

Quick Capture (SPEC-314): `quick_capture.py` settings + oEmbed helper + day-entry note merge; `quick_capture_ui.py` always-on-top panel (off by default). Link starters prepend into category `notes`; Journal now opens `show_journal_window(..., seed=)`. Optional YouTube title via public oEmbed only while capturing.

Notification residency (SPEC-306): reminders need a live process — `minimize_on_close` iconifies instead of quitting; `autostart_windows.py` toggles HKCU Run for Start with Windows. Controls live under Data & Security.

