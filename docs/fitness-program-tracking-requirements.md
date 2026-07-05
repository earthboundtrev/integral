# Fitness Program Progress Tracking — Product Requirements

**Product:** Full Spectrum Development Tracker  
**Document:** Fitness program intelligence layer  
**Status:** Draft for implementation planning  
**Date:** 2026-07-05

---

## 1. Problem statement

The current app is strong at **daily reflection**: ratings, checklists, free-form notes, and generic charts per life category. That is not enough for physical development.

What you need is a system that understands **structured fitness programs** — Tibetan Rites, Convict Conditioning (CC), Explosive Calisthenics (EC), and others you add over time — and can answer questions like:

- Am I actually progressing in CC Big Six, or just repeating the same step?
- When did I last advance in Tibetan Rites repetitions?
- Is my EC power work improving (height, reps, hold time, tempo)?
- Which program am I neglecting this month?
- What should I do in today's session based on where I am in each program?

**The app must not be a notebook of exercise names.** It must be a **progress engine** with program semantics, comparable metrics, and graphs that show *development over time*.

---

## 2. Vision

> One local app that tracks **multi-program physical development** with enough structure to graph real progress, while still supporting notes and holistic life areas (spiritual, emotional, etc.).

### Success looks like

| User question | App answer |
|---------------|------------|
| "Where am I in Convict Conditioning?" | Current step per movement, days at step, readiness to advance |
| "Is Tibetan Rites improving?" | Rep progression chart per rite, cycle time trend, consistency streak |
| "How is explosive work going?" | Jump height / rep / rest trends for EC drills |
| "What did I do last Tuesday?" | Structured session log, not vague notes |
| "Am I balanced across programs?" | Weekly volume + progression heatmap across all active programs |

---

## 3. Goals and non-goals

### Goals

1. **Program-aware data model** — exercises belong to programs with rules, levels, and advancement criteria.
2. **Session logging optimized for speed** — log a workout in under 2 minutes.
3. **Automatic progress inference** — detect level-ups, plateaus, regressions, and deloads from data.
4. **Cross-program analytics** — compare development across CC, Tibetan Rites, EC, and custom programs.
5. **Preserve existing holistic tracker** — life categories (spiritual, emotional, etc.) remain; fitness becomes a first-class domain, not a checklist under "Body & Presence."

### Non-goals (v1)

- Social features, cloud sync, or multi-user accounts
- Video form analysis or wearables integration
- Replacing a full gym programming app (Wave, Strong, etc.) for arbitrary weightlifting
- Medical injury diagnosis or prescriptive training plans without user-defined rules

---

## 4. Core concepts

### 4.1 Program

A **program** is a named training system with its own progression logic.

Examples (seed library):

| Program | Type | Progression unit |
|---------|------|----------------|
| **Tibetan Rites** | Daily ritual sequence | Reps per rite (1–21+), optional cycle timing |
| **Convict Conditioning** | Step-based calisthenics | Step 1–10 per movement (Big Six + variants) |
| **Explosive Calisthenics** | Skill + power drills | Level, reps, height/distance, hold seconds, tempo |
| **Custom / Future** | User-defined | User-defined levels and metrics |

Each program defines:

- `program_id`, `name`, `description`
- `movements[]` — named exercises within the program
- `progression_model` — how advancement works (see §4.2)
- `default_metrics[]` — what to capture per movement/session
- `advancement_rules[]` — when the app suggests or records a level-up

### 4.2 Progression models

The app must support **multiple progression paradigms**, not one generic "reps" field.

| Model | Used by | Key fields | Advance signal |
|-------|---------|------------|----------------|
| **Step ladder** | Convict Conditioning | `step` (1–10), `reps_per_set`, `sets`, `rest` | Hit target reps at perfect form for N sessions |
| **Repetition ramp** | Tibetan Rites | `reps` per rite, `rounds`, `duration` | Sustained target reps for N days; optional increase cadence |
| **Performance metric** | Explosive Calisthenics | `reps`, `height_cm`, `distance_cm`, `hold_sec`, `RPE` | Trend improvement or passing benchmark threshold |
| **Time under tension** | Isometrics, hangs | `hold_sec`, `sets` | Hold time trend |
| **Binary mastery** | Skills (e.g. first muscle-up) | `achieved` (bool), `date` | One-time milestone + maintenance logging |
| **Custom formula** | User programs | User-defined metrics | User-defined rule expressions |

### 4.3 Movement

A **movement** is one exercise within a program (e.g. CC "Pushups", Tibetan Rite #3, EC "Squat jump").

Fields:

- `movement_id`, `program_id`, `name`, `aliases[]`
- `progression_model` (inherits or overrides program default)
- `target_standards[]` — e.g. CC Step 5 standard: "3×50 pushups"
- `optional_notes_prompt` — e.g. "Form focus today?"

### 4.4 Session

A **session** is one training occurrence (usually one day, possibly AM/PM).

```json
{
  "session_id": "uuid",
  "date": "2026-07-05",
  "program_id": "convict-conditioning",
  "movement_logs": [
    {
      "movement_id": "cc-pushups",
      "step": 3,
      "sets": 2,
      "reps": [35, 32],
      "form_quality": 8,
      "notes": "Clean tempo, stopped before grind"
    }
  ],
  "session_rpe": 7,
  "duration_min": 25,
  "notes": "..."
}
```

Sessions are **structured first**, notes second.

### 4.5 Benchmark

A **benchmark** is a repeatable test used to measure development (program-specific).

Examples:

- CC: "Assessment sets" at current step (max clean reps × 3 sets)
- Tibetan Rites: full 5-rite cycle at current rep count, timed
- EC: max vertical jump, broad jump, or explosive push-up height

Benchmarks enable **apples-to-apples graphs** even when day-to-day training varies.

### 4.6 Program state (intelligence layer)

For each `(user, program, movement)` the app maintains **derived state**:

- `current_level` — step, rep tier, or skill tier
- `level_since` — date entered current level
- `sessions_at_level` — count
- `last_session_date`
- `trend` — `improving` | `stable` | `plateau` | `regressing` | `insufficient_data`
- `next_suggested_action` — e.g. "Attempt Step 4 assessment" or "Hold 18 reps for 7 days before adding"

This state is **computed from logs**, not manually maintained (though user can override).

---

## 5. Functional requirements

### FR-1 Program library

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1.1 | Ship seed definitions for Tibetan Rites, Convict Conditioning (Big Six), and Explosive Calisthenics starter movements | P0 |
| FR-1.2 | User can add custom programs and movements | P1 |
| FR-1.3 | User can archive/deactivate programs without deleting history | P1 |
| FR-1.4 | Each program documents its progression rules in-app (readable, not code) | P2 |

### FR-2 Session logging

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-2.1 | "Log workout" flow: pick program → pick movements → enter structured fields | P0 |
| FR-2.2 | Smart defaults: pre-fill last session's step/reps/sets | P0 |
| FR-2.3 | Quick log: one-tap "repeat last session" with editable deltas | P1 |
| FR-2.4 | Support multiple programs in one day (e.g. Tibetan Rites AM + CC PM) | P0 |
| FR-2.5 | Optional link session to life-category "Body & Presence" daily entry | P2 |

### FR-3 Progression intelligence

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-3.1 | Auto-detect CC step advancement when user meets program rules (configurable strictness) | P0 |
| FR-3.2 | Tibetan Rites: track rep level per rite; suggest +1 rep only after consistency window | P0 |
| FR-3.3 | EC: trend detection on primary metric per drill (reps, height, hold time) | P0 |
| FR-3.4 | Plateau detection: N sessions with no meaningful improvement | P1 |
| FR-3.5 | Regression flag: significant drop vs 4-week rolling average | P1 |
| FR-3.6 | "Ready to advance?" prompt with evidence (last N sessions) | P0 |

### FR-4 Graphing and analytics

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-4.1 | **Per-movement progression chart** — level/step over time (step ladder) | P0 |
| FR-4.2 | **Volume chart** — sets × reps or total reps per week | P0 |
| FR-4.3 | **Benchmark trend** — assessment results over time | P0 |
| FR-4.4 | **Cross-program dashboard** — active programs, last trained, current level summary | P0 |
| FR-4.5 | **Consistency heatmap** — sessions per program (not just "categories logged") | P1 |
| FR-4.6 | **Comparative growth index** — normalized 0–100 development score per program for radar chart | P1 |
| FR-4.7 | Export chart data to CSV | P2 |

### FR-5 Tibetan Rites — specific

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-5.1 | Log all 5 rites in one flow with reps each | P0 |
| FR-5.2 | Track optional total cycle duration | P1 |
| FR-5.3 | Graph: reps per rite over time (5 lines or small multiples) | P0 |
| FR-5.4 | Rule: default advancement = hold target reps 7 consecutive days before +1 (configurable) | P0 |
| FR-5.5 | Alert if skipping rites or inconsistent practice | P2 |

### FR-6 Convict Conditioning — specific

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-6.1 | Big Six movements seeded with step standards (from CC progression tables) | P0 |
| FR-6.2 | Per movement: log step, sets, reps per set, form quality (1–10) | P0 |
| FR-6.3 | Graph: current step per movement over time (timeline or ladder viz) | P0 |
| FR-6.4 | Advancement rule: hit `beginner_standard` for movement → suggest step up; never auto-advance without user confirm (v1) | P0 |
| FR-6.5 | "Stuck at step" indicator after X sessions without meeting advance criteria | P1 |

### FR-7 Explosive Calisthenics — specific

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-7.1 | Seed starter drills: squat jump, broad jump, clap push-up, explosive pull, etc. | P0 |
| FR-7.2 | Each drill declares primary metric (`height`, `reps`, `hold`, `distance`) | P0 |
| FR-7.3 | Graph primary metric trend + session RPE overlay | P0 |
| FR-7.4 | Support drill tiers/levels (user-defined or template) | P1 |
| FR-7.5 | Rest-period tracking between explosive sets (optional) | P2 |

### FR-8 Holistic integration

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-8.1 | Keep existing life-area categories (spiritual, emotional, etc.) | P0 |
| FR-8.2 | Fitness programs live under expanded **Body & Physical Development** hub | P0 |
| FR-8.3 | Weekly summary includes fitness: sessions/week, programs touched, notable PRs | P1 |
| FR-8.4 | Notes from sessions searchable alongside journal notes | P1 |

---

## 6. Data model evolution

### Current (v0)

```json
{
  "categories": { "...life areas...": { "checklist": [], "metrics": [] } },
  "entries": { "2026-07-05": { "Body & Presence": { "rating": 7, "notes": "..." } } },
  "settings": { "dark_mode": false }
}
```

### Target (v1)

```json
{
  "schema_version": 2,
  "settings": { "dark_mode": false },
  "life_categories": { },
  "life_entries": { },
  "programs": [
    {
      "id": "tibetan-rites",
      "name": "Tibetan Rites",
      "progression_model": "repetition_ramp",
      "movements": [ { "id": "rite-1", "name": "Rite 1", ... } ],
      "rules": { "advance_after_consecutive_days": 7, "rep_increment": 1 }
    }
  ],
  "sessions": [ ],
  "program_state": {
    "convict-conditioning": {
      "cc-pushups": { "current_step": 3, "since": "2026-05-12", "trend": "stable" }
    }
  }
}
```

### Migration rules

- Existing `categories` / `entries` → `life_categories` / `life_entries` (no data loss)
- `Body & Presence` remains; fitness sessions are **additive**, not a replacement
- `schema_version` gate in loader; merge defaults for new programs like current category merge

---

## 7. Intelligence rules (v1 heuristics)

### 7.1 Trend classification

For numeric metric series (last 6 sessions minimum):

| Condition | Label |
|-----------|-------|
| Slope > +threshold | `improving` |
| Slope near 0 | `stable` |
| 4+ sessions, slope ≈ 0, below advance criteria | `plateau` |
| Last value < 85% of 4-week mean | `regressing` |
| < 3 sessions | `insufficient_data` |

Thresholds are **per metric type** (reps vs cm vs seconds).

### 7.2 Advancement suggestions

| Program | Suggest advance when |
|---------|-------------------|
| Tibetan Rites | Target reps met on all 5 rites for N consecutive days |
| Convict Conditioning | All sets meet step rep standard with form ≥ 7 for 2 sessions |
| Explosive Calisthenics | Primary metric improves 3 sessions in a row OR beats personal benchmark |

User always **confirms** level-up in v1 (prevents bad auto-promotion).

### 7.3 Cross-program "development score" (normalized)

For radar / summary only:

```
score = weighted combination of:
  - consistency (sessions in last 28 days vs target)
  - progression (level increases in last 90 days)
  - performance (metric vs personal baseline)
```

Weights configurable per program; default equal weight.

---

## 8. UI requirements

### 8.1 New surfaces

| Surface | Purpose |
|---------|---------|
| **Fitness hub** | Cards per active program: last session, current level, trend badge |
| **Log session** | Program-specific form (dynamic fields from progression model) |
| **Program detail** | Movement list, current state, history, charts |
| **Progress overview** | Cross-program dashboard + growth radar |
| **Benchmarks** | Log / view assessment results |

### 8.2 Graph requirements (fitness-specific)

Must exceed generic rating line charts:

1. **Step ladder timeline** (CC) — horizontal bands Step 1–10, dots for sessions
2. **Multi-series rep ramp** (Tibetan Rites) — 5 rites on one chart
3. **Metric trend + moving average** (EC)
4. **PR markers** — annotate personal records on charts
5. **Program comparison radar** — normalized development scores

### 8.3 UX principles

- Logging must be faster than opening Notes on a reMarkable
- Graphs must show **change**, not just activity
- Terminology matches each program (Step vs Reps vs Tier — never generic "level" in UI without context)

---

## 9. Seed program content (initial library)

### 9.1 Tibetan Rites

| Movement | Default metric | Notes |
|----------|----------------|-------|
| Rite 1 | reps | Spin |
| Rite 2 | reps | Leg raise |
| Rite 3 | reps | Camel |
| Rite 4 | reps | Table |
| Rite 5 | reps | Up/down dog flow |

Default start: 3 reps each; advance +1 after 7 consistent days.

### 9.2 Convict Conditioning — Big Six

| Movement | Steps | Example Step 3 standard |
|----------|-------|-------------------------|
| Pushups | 1–10 | 3×35 |
| Squats | 1–10 | 3×50 |
| Pullups | 1–10 | 3×10 |
| Leg raises | 1–10 | 3×25 |
| Bridges | 1–10 | 3×25 |
| Handstand pushups | 1–10 | 3×10 |

Standards table stored in program definition (editable in settings P2).

### 9.3 Explosive Calisthenics — starters

| Drill | Primary metric | Secondary |
|-------|----------------|-----------|
| Squat jump | height_cm or reps | RPE |
| Broad jump | distance_cm | RPE |
| Clap push-up | reps | RPE |
| Explosive pull-up | reps | height_cm |
| Sprint start / bound | reps or distance | — |

User adds drills freely; template suggests metric types.

---

## 10. Technical requirements

| ID | Requirement |
|----|-------------|
| TR-1 | Local-first JSON storage; optional export/import |
| TR-2 | `schema_version` with migrations |
| TR-3 | Derived `program_state` recalculated on load and after each session save |
| TR-4 | Chart module accepts program-aware series builders (extend `graphs.py`) |
| TR-5 | Program definitions in `programs/` as JSON (versioned with app) |
| TR-6 | Unit tests for progression rules and trend detection |
| TR-7 | No network required |

---

## 11. Phased delivery

### Phase A — Foundation (P0)

- Data model v2 + migration
- Program library (3 seed programs)
- Session logging with smart defaults
- Per-movement step/rep charts
- Fitness hub on dashboard

**Exit:** You can log CC pushups at Step 3 and see step history on a graph.

### Phase B — Intelligence (P0–P1)

- Trend detection (improving / plateau / regressing)
- Advancement suggestions with evidence
- Tibetan Rites 5-rite flow + rep ramp charts
- Cross-program summary dashboard

**Exit:** App tells you "pushups: stable at Step 3 for 5 sessions — 2 more at standard to advance."

### Phase C — Explosive & benchmarks (P1)

- EC drill templates + metric trends
- Benchmark logging and PR annotations
- Normalized development radar

### Phase D — Polish (P2)

- Custom programs
- CSV export
- Weekly fitness digest in summary view
- Configurable advancement strictness

---

## 12. Acceptance criteria (Phase A + B)

1. **Structured, not vague:** A session log for Convict Conditioning stores step, sets, and reps — not only free text.
2. **Multi-program:** Same week can log Tibetan Rites, CC, and EC; each appears on fitness hub.
3. **Progress visible:** CC pushups graph shows step changes over at least 30 days of test data.
4. **Tibetan Rites:** Rep count per rite graphed; advancement suggestion appears after meeting rule.
5. **Intelligence:** After 5 identical-step CC sessions, app shows `plateau` or `stable` — not silent.
6. **Holistic preserved:** Spiritual / Emotional categories still work unchanged.
7. **Offline:** All features work without internet.

---

## 13. Open questions (for you)

1. **Convict Conditioning standards** — Use Paul Wade's official rep tables exactly, or your personal modified standards?
2. **Tibetan Rites cadence** — Daily only, or allow every-other-day with adjusted advance rules?
3. **Explosive Calisthenics** — Do you follow a specific book/chart (e.g. progression tables), or mostly freestyle with benchmarks?
4. **Advancement authority** — Always confirm level-up manually (recommended v1), or allow auto-advance with undo?
5. **Other programs to seed next** — Yoga, mobility, grip, running, kettlebells?
6. **Units** — Metric (cm) vs imperial (inches) for jumps?

---

## 14. Relationship to current app

| Current feature | Future role |
|-----------------|-------------|
| Life categories | Unchanged holistic journaling |
| Generic metrics | Life areas only; fitness uses program metrics |
| Graphs tab | Split: Life graphs + Fitness graphs |
| Edit Categories | Life categories; separate Program Editor |
| Weekly summary | Adds fitness section: sessions, PRs, trends |
| Dark mode | Applies to all new surfaces |

---

*Next step after approval: implement **Phase A** — schema v2, seed programs, session logger, CC step chart.*
