# Changelog

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
