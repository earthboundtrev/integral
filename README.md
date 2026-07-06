# Personal Development Tracker

**Spec-driven, agent-built, zero human code.**

Local-first desktop app for holistic personal development — daily logging across 8 life domains, graphs & summaries, evolving into a graph-based fitness progression platform.

## How You Build (Without Writing Code)

1. **PRD** — `docs/PRD.md` defines the whole product
2. **ADRs** — `docs/CONSTITUTION.md` + `docs/adr/` = decisions agents must not break
3. **Specs** — `docs/specs/` = one spec per PR, with EARS acceptance criteria
4. **Agents** — Cursor rules in `.cursor/rules/` = harness (implement, author, review)
5. **Loop** — `docs/WORKFLOW.md` = intent → spec → implement → verify → done

Methodology from [Gauntlet Night School: Specs, ADRs, and Building Loops](https://youtu.be/ayHy7YHddak).

### Your commands to the agent

| You say | Agent uses |
|---------|------------|
| "Implement SPEC-005" | `harness-implement` + spec file |
| "Write spec for workout logging" | `harness-spec-author` |
| "Verify SPEC-001" | `harness-review` |
| "Add feature X" | Spec author first, approve, then implement |

### Phase 1 (MVP) — implemented

**From source:**
```bash
pip install --user -r requirements.txt
python tracker.py
```

**Classic EXE (no Python needed):**
```powershell
pip install -r requirements.txt -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
# Double-click: dist\PersonalDevelopmentTracker.exe
```

See [docs/BUILD.md](docs/BUILD.md). User data always lives in `~/.personal_dev_tracker/` — survives EXE updates.

Tests: `python -m pytest tests/ -v` (42 passed)

### Phase 2 — started

`SPEC-201` is **done**: the fitness DAG core now has SQLite-backed exercises, progression edges, user progress, JSON criteria storage, and prerequisite-cycle validation.

`SPEC-202` is **done**: logged performance can now mark exercises mastered and unlock downstream nodes from mastery conditions.

`SPEC-203` is **done**: CC1 push-up progression seed (10 steps) with tests.

`SPEC-208` is **done**: standalone Windows EXE build (PyInstaller). Output: `dist/PersonalDevelopmentTracker.exe`. Data stays in `~/.personal_dev_tracker/`.

`SPEC-204` is **done**: **Fitness Progress** window — log sets/reps, mastery unlocks next step.

`SPEC-205` is **done**: lightweight Skill Tree view, colored by progress status.

**Multi-account:** local profiles via header dropdown (ADR-008). Not cloud login.

## Documentation Map

| Doc | Contents |
|-----|----------|
| [docs/PRD.md](docs/PRD.md) | Product requirements, epics, architecture mermaid |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | Spec-driven loop, status values, agent factory |
| [docs/SPEC_TEMPLATE.md](docs/SPEC_TEMPLATE.md) | Template for new feature specs |
| [docs/CONSTITUTION.md](docs/CONSTITUTION.md) | ADR index |
| [docs/VISION.md](docs/VISION.md) | Vision narrative |
| [docs/PERFORMANCE.md](docs/PERFORMANCE.md) | Why Python not C++; performance budget |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Module boundaries, data flow |
| [docs/DATA_MODEL.md](docs/DATA_MODEL.md) | JSON shapes, fitness entities |
| [docs/PROGRESSION_MODEL.md](docs/PROGRESSION_MODEL.md) | Exercise DAG deep spec |

## Cursor Rules (Harness)

| Rule | When |
|------|------|
| `constitution.mdc` | Always — ADRs, no code without spec |
| `spec-driven-workflow.mdc` | Always — read spec before code |
| `harness-implement.mdc` | Python files — implementation agent |
| `harness-spec-author.mdc` | New features — write specs only |
| `harness-review.mdc` | After implement — verify AC |
| `performance-lightweight.mdc` | Python — lazy matplotlib, etc. |
| `progression-graph.mdc` | Fitness/progression code |
| `data-storage.mdc` | Data conventions |
| `ui-tkinter.mdc` | UI patterns |

## Setup (for running agent-built app)

```bash
pip install matplotlib
python tracker.py
```

Data: `~/.personal_dev_tracker/data.json`
