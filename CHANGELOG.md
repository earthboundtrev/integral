# Changelog

## 0.3.2 — 2026-07-08

### Added

- **AI Insight (optional)** — local Ollama summaries of your last 7–30 days (domains, journal, fitness); no cloud, no embeddings
- **Weekly Review** and **Emotional Patterns** insight types in **Graphs & Progress → AI Insight**
- **Get AI Insight** on the Weekly Summary footer
- `requirements-ai.txt` for the optional `ollama` Python client

### Build

- Windows app: `dist/Integral/Integral.exe` (run `.\build.ps1`)
- Release zip: `Integral-v0.3.2-windows.zip`

## 0.3.1 — 2026-07-07

### Fixed

- **Dialog scrolling** — popups scroll reliably with mouse wheel anywhere in the window; action buttons stay pinned at the bottom
- **Overflow hints** — narrow or short windows show “scroll for more” on toolbars and the today’s-log category grid
- **Fitness ↔ daily log bridge** — workouts from Fitness Hub now mark **Body & Presence** on the correct date and appear in the activity grid and day explorer
- **Backfill on startup** — existing workouts in `fitness.db` sync to daily entries automatically
- **Skill Tree logging** — exercise logs from the skill tree update the main tracker (same as Fitness Hub)

### Added

- **Log Exercise** — quick session logger from Today’s Log and the footer (pick date, add sets, save)
- **Day explorer** — “Log exercise for this day” for past dates; fitness sessions listed from the progression database
- **Session date** on single-step exercise log dialogs (no longer forced to today only)

### Build

- Windows app: `dist/Integral/Integral.exe` (run `.\scripts\build_exe.ps1`)
- Release zip: `Integral-v0.3.1-windows.zip`

## 0.3.0 — 2026-07-06

### Added

- **Plan tomorrow** — set day intentions, fitness goals, and per-area targets for an upcoming day
- **Plan vs Actual** — compare what you planned with what you actually logged (dashboard, day explorer, dedicated review)
- **Fitness progression unlock** — CC-style ladders unlock the next step after meeting progression standards across qualifying sessions
- **Set starting step** — experienced athletes can place themselves on a ladder with clear anti-rushing warnings
- **Fitness settings** — optional bypass of progression locks; configurable sessions required before unlock

### Build

- Windows app: `dist/Integral/Integral.exe` (run `.\scripts\build_exe.ps1`)

## 0.2.9 — 2026-07-06

### Added

- **Windows toast reminders** — Duolingo-style nudges through the day; after your first log, only one evening wrap-up reminder
- **Automatic day rollover** — date, streak, and today's log refresh at midnight while Integral stays open

### Release hygiene

- Repo keeps only the latest `Integral-v*-windows.zip`; older release zips and git tags are removed on each release

### Build

- Windows app: `dist/Integral/Integral.exe` (run `.\scripts\build_exe.ps1`)

## 0.2.8 — 2026-07-05

### Fixed

- **Activity grid** — today turns green immediately when you log (GitHub-style); graph auto-scrolls to the current week
- **Activity counts** — fitness hub workout sessions included in the heatmap, not just life-area JSON entries
- **Clearer greens** — single contributions use a more visible green in light and dark mode

### Improved

- **Life-area log dialogs** — scrollable form with pinned **Save Log** footer so save is never off-screen
- **Fitness step logging** — notes field plus pinned **Save Log**; session dialog **Save Session** pinned at bottom

### Build

- Windows app: `dist/Integral/Integral.exe` (run `.\build.ps1`)

## 0.2.7 — 2026-07-05

### Fixed

- **Fitness Hub progression rules** — each program seed declares `step_progression` (`sequential` vs `parallel`) so unlock behavior matches the real training methodology
- **Starting Strength** — all main lifts available from day one (no artificial squat→bench→deadlift chain)
- **Five Tibetan Rites** — all five rites available together (daily routine, not one-at-a-time unlock)
- **CC2 samples** — independent movement families no longer chained as one fake ladder
- **Anti-cheese** — logging a locked sequential step is rejected; parallel families strip internal prerequisite edges

### Build

- Windows app: `dist/Integral/Integral.exe` (run `.\build.ps1`)

## 0.2.6 — 2026-07-05

### Improved

- **Snappier UI** — logging and journal saves refresh the dashboard in place instead of rebuilding the whole window
- **Deferred disk writes** — the interface updates immediately; saves flush in the background (synced on exit)
- **Cached insights and streaks** — recomputed only when your data actually changes
- **Faster encrypted saves** — reuse vault salt and derived key instead of re-running full key derivation every save
- **Lazy Categories tab** — eighteen domain cards build only when you open that tab
- **Faster activity grid** — indexed day counts instead of scanning all entries per cell
- **Fitness Hub** — skip re-seeding the exercise database on every open
- **Faster streak calculation** — walk backward from today instead of sorting every logged date

### Docs

- Expanded personal origin story (lost notebook, reMarkable, paper, hybrid approach, AI as force multiplier)

### Build

- Windows app: `dist/Integral/Integral.exe` (run `.\build.ps1`)

## 0.2.5 — 2026-07-05

### Why this release matters

Integral exists so your life logs, training notes, and reflections are never one lost notebook away from gone. See [README — Why Integral](README.md#why-integral).

### Added

- **Journal** — prompts, free write, browse/edit past entries, backdated logging with required reason
- **Fitness Hub hierarchy** — book (CC1, SS, …) → program (Pull, Push, …) → steps, collapsed by default
- **Backdated life-area logs** — editable date with accountability reason for past entries
- Journal in activity grid, day explorer, search, full history, CSV export, and encrypted backup JSON

### Improved

- Modern Integral UI theme (cards, typography, streak badge, progress bar)
- Merged progression fitness hub (91 exercises, search, videos, skill tree) with 18-domain Integral app
- Export includes `integral-journal-{timestamp}.csv`

### Build

- Windows app: `dist/Integral/Integral.exe` (run `.\build.ps1`)

## Earlier work

See git history from initial Integral commit through 18-domain model, vault encryption, milestones, and fitness intelligence (0.2.x line).
