# Project Status — Personal Development Tracker

**Last updated:** 2026-06-27  
**Tests:** 51 passing (`python -m pytest tests/ -q`)  
**Resume here:** read this file, then `docs/specs/README.md` for spec details.

---

## At a glance

| Stage | Status | Notes |
|-------|--------|-------|
| Phase 1 — Daily tracker | **Done** | All 6 specs |
| Infra — Standalone EXE | **Done** | Rebuild after big changes |
| Multi-profile (ADR-008) | **Done** | No dedicated spec; implemented |
| Phase 2 — Fitness DAG | **Done** | All 9 specs |
| Phase 3 — Cross-domain | **Partial** | Radar + recommendations done; pilot + AI coach not started |
| Docs cleanup | **Not done** | Architecture/data-model docs are stale |

---

## Phase 1 — Daily Life Tracker (MVP) — DONE

| Spec | Feature | Key files |
|------|---------|-----------|
| 005 | Storage + 8 default categories | `storage.py`, `profiles.py` |
| 001 | Dashboard (cards, streaks) | `tracker.py`, `streak.py` |
| 002 | Daily log dialog | `tracker.py` |
| 003 | Graphs & summaries | `charts.py`, `summaries.py` |
| 004 | Full history | `history.py` |
| 006 | Settings placeholder | `tracker.py` |

**What works:** 8 category dashboard, daily logging (rating/checklist/metrics/notes), streaks, graphs, history, profile switcher.

---

## Infra — DONE

| Spec | Feature | Key files |
|------|---------|-----------|
| 001 | Windows EXE (local-first) | `paths.py`, `build/personal_dev_tracker.spec`, `scripts/build_exe.ps1` |

**Data location:** `~/.personal_dev_tracker/profiles/<id>/` (not beside the EXE).

**Rebuild EXE:**
```powershell
.\scripts\build_exe.ps1
```
Output: `dist/PersonalDevelopmentTracker.exe`

---

## Multi-profile — DONE (ADR-008)

- Profiles under `~/.personal_dev_tracker/profiles/<id>/`
- Each profile: own `data.json` + `fitness.db`
- UI: profile dropdown + New Profile in dashboard header
- Legacy `data.json` migrates to `profiles/default/`

---

## Phase 2 — Fitness Progression Graph — DONE

| Spec | Feature | Key files |
|------|---------|-----------|
| 001 | DAG core (SQLite) | `progression/db.py`, `models.py`, `validate.py` |
| 002 | Mastery + unlock engine | `progression/mastery.py`, `engine.py` |
| 003 | CC1 push seed (pilot) | `progression/seed/v1/cc1_push.json` |
| 004 | Exercise logging UI | `fitness_ui.py` |
| 005 | Skill tree v1 | `skill_tree.py` |
| 006 | All book seeds (91 exercises) | `progression/seed/v1/*.json`, `seed_loader.py` |
| 007 | Body composition | `body_composition_ui.py` |
| 008 | Workout sessions | `progression/sessions.py`, `fitness_ui.py` |
| 009 | Skill tree v2 (filters, click-to-log) | `skill_tree.py` |

### Seed data (91 exercises)

| Book | Content |
|------|---------|
| CC1 | Push, squat, pull, leg raise, bridge, HSPU (10 steps each) |
| SS | Back squat, bench, deadlift, OHP, power clean |
| OG | Planche + front lever; skin the cat → back lever |
| EC | Knee push-up → explosive one-arm push-up |
| FTR | Five Tibetan Rites |
| CC2 | Wall HSPU, stand-to-stand bridge, L-sit, V-sit, human flag tuck |
| Cross-links | 4 recommended edges between books |

**Fitness UI entry points** (dashboard → Fitness Progress):
- Log single exercise
- New Session / Session History (multi-exercise workouts)
- Body Composition
- Skill Tree (filter by book/family, click node to log)

Opening Fitness Progress auto-seeds missing exercises for existing profiles (incremental, safe).

---

## Phase 3 — Cross-Domain & Coach — PARTIAL

| PRD ID | Feature | Status | Spec |
|--------|---------|--------|------|
| C2 | Life-balance radar (8 axes) | **Done** | `specs/phase-3/001-radar-recommendations.md` |
| C3 | Local "what's next" recommendations | **Done** | same spec |
| C1 | Progression graph for 1 non-fitness category | **Not started** | TBD |
| C4 | Optional LLM coach | **Deferred** | Needs new ADR |

**Where to find done work:**
- Radar chart: Graphs & Summaries → **Life Balance** tab (`charts.py`)
- Recommendations: dashboard **What's Next** panel (`recommendations.py`)

---

## Not done yet (backlog)

1. **Cross-domain progression pilot** — apply DAG pattern to one non-fitness category (e.g. Money/Freedom milestones)
2. **Optional AI coach** — explicitly deferred; requires ADR before any implementation
3. **Settings screen** — still a placeholder dialog (export/import, profile management, etc.)
4. **Doc cleanup** — `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, `docs/PROGRESSION_MODEL.md` are stale (missing profiles, fitness tables, current modules)
5. **PRD sync** — `docs/PRD.md` §5 still lists old B6/B7 spec names; actual work lives in specs 006–009
6. **EXE rebuild** — last build may predate Phase 2 expansion; rebuild if distributing

---

## How to resume work

### Run the app (dev)
```powershell
python tracker.py
```

### Run tests
```powershell
python -m pytest tests/ -q
```

### Add a new feature (spec-driven)
1. Ask agent: *"Write spec for [feature]"* (uses `harness-spec-author`)
2. Review spec in `docs/specs/`, set `status: approved`
3. Ask agent: *"Implement SPEC-NNN per docs/specs/..."*
4. Ask agent: *"Verify SPEC-NNN"* (uses `harness-review`)
5. Update this file when the stage changes

### Suggested next implementation order
1. Write + approve spec for **cross-domain progression pilot** (Phase 3 C1)
2. Doc cleanup spec (architecture + data model refresh)
3. Real **settings** screen spec (export, profile delete, etc.)
4. Rebuild EXE and smoke-test on a clean machine

---

## Key module map

```
tracker.py              Main app, dashboard, graphs, recommendations panel
storage.py              JSON per profile (8 categories, entries)
profiles.py             Multi-profile config
charts.py               matplotlib (lazy): daily avg, category bar, life balance radar
summaries.py / history.py / streak.py
fitness_ui.py           Fitness list, sessions, logging
skill_tree.py           DAG canvas visualization
body_composition_ui.py  Weight + measurements
recommendations.py      Local rule-based "what's next"
progression/
  db.py                 SQLite: exercises, edges, progress, sessions, body comp
  engine.py / mastery.py
  seed_loader.py        seed_all_fitness()
  sessions.py           Workout session helpers
  seed/v1/*.json        13 seed files, 91 exercises
```

---

## ADRs in effect

| ADR | Rule |
|-----|------|
| 001 | Python + Tkinter only |
| 002 | Local-first `~/.personal_dev_tracker/` |
| 003 | matplotlib lazy-loaded only |
| 004 | SQLite for fitness |
| 005 | 8 fixed category names |
| 006 | Progression is DAG (no cycles) |
| 007 | No code without approved spec |
| 008 | Local multi-profile accounts |
| 009 | Standalone EXE; user data outside EXE |

---

## Revision log

| Date | Change |
|------|--------|
| 2026-06-27 | Phase 2 completed (seeds, body comp, sessions, skill tree v2); Phase 3 partial (radar + recommendations); 51 tests |
