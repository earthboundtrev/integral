# Changelog

## Unreleased

### Added

- **Quick Capture expansion (SPEC-315)** — today/upcoming todos, finish→category log, quick-log launcher, Deep Work timer on the overlay, Windows focus shield (choose apps to minimize; nudge back until timer ends)

## 0.3.9 — 2026-07-20

### Added

- **Quick Capture mode** — optional always-on-top panel (off by default): link → life-domain day starter; Journal now with optional seed; best-effort YouTube oEmbed titles

### Build

- Windows app: `dist/Integral/Integral.exe`
- Release zip: `Integral-v0.3.9-windows.zip`
- User data: `%APPDATA%\Integral\data.json`

## 0.3.8 — 2026-07-19

### Added

- **Full CC2 skill-tree seeds** — hangs, calves, fingertip push-ups, clutch/press flags, neck bridges, and Trifecta ladders from official Hub tables (66 steps)
- **Strong Medicine skill-tree seeds** — King Squat→barbell, sumo DL, DB bench/press, statue row, plank core from official Hub tables (25 steps; **177** total seeded exercises)
- Faster fitness seeding (single-connection batch load)

### Build

- Windows app: `dist/Integral/Integral.exe`
- Release zip: `Integral-v0.3.8-windows.zip`
- User data: `%APPDATA%\Integral\data.json`

## 0.3.7 — 2026-07-12

### Added

- **Honest-presence streak** — life log, journal, or fitness counts; pill updates on save; mid-day grace; human gap repair via backdated journal (no freeze tokens)
- **Journal cross-links** — `[[journal:id]]` / `integral://journal/id`; Copy / Insert link; open on click
- **Rich journal formatting** — markdown-lite toolbar (bold, italic, code, headings, quotes, lists)
- **Cross-entity links** — domain days, fitness days, writing projects (`[[domain:…]]`, `[[fitness:…]]`, `[[project:…]]`)
- **Backlinks** — “Linked from” panel in Journal
- **OS deep links** — optional Windows `integral://` protocol registration (Data & Security)
- **Export/import gate** — Cursor rules require backup/restore verification on data/storage changes; stronger JSON backup tests

### Build

- Windows app: `dist/Integral/Integral.exe`
- Release zip: `Integral-v0.3.7-windows.zip`
- User data: `%APPDATA%\Integral\data.json`

## 0.3.6.2 — 2026-07-12

### Added

- **Reminder residency** — minimize-to-taskbar on close and Start with Windows so portable toasts can keep firing; Data & Security controls + test notification

### Fixed

- **Streak on startup** — shows consecutive days ending yesterday when today is not logged yet (grace until midnight)
- **Subtitle** — “Holistic life tracking” (no hard-coded domain count)

### Build

- Windows app: `dist/Integral/Integral.exe`
- Release zip: `Integral-v0.3.6.2-windows.zip`

## 0.3.6.1 — 2026-07-12

### Fixed

- **Today's Log default layout** — status text no longer collides with Continue; taller category grid with mousewheel scroll
- **Duplicate Activity heading** — Overview keeps a single “Activity — click a day to explore” label above the grid
- **Deep Work dialog** — Start / Cancel buttons fully visible
- **Writing Projects** — **Continue Writing** (and Open Both) visible on their own row; double-click opens the manuscript

### Build

- Windows app: `dist/Integral/Integral.exe`
- Release zip: `Integral-v0.3.6.1-windows.zip`

## 0.3.6 — 2026-07-12

### Added

- **Writing Projects** — local library for novels/scripts with inspiration + manuscript documents (separate windows, debounced autosave)
- **Creative/Mental Work integration** — open Writing Projects from the category log; explicit “Log writing session” checklist credit
- **Deep Work Mode** — focus timer (25/50/90/custom) that quiets nav chrome; optional open a writing project; +10 min / End early

### Build

- Windows app: `dist/Integral/Integral.exe`
- Release zip: `Integral-v0.3.6-windows.zip`

## 0.3.5.1 — 2026-07-10

### Fixed

- **Launch crash on v0.3.5** — restored `horizontal=` support in `bind_mousewheel()` so the Overview activity grid initializes correctly

### Build

- Windows app: `dist/Integral/Integral.exe`
- Release zip: `Integral-v0.3.5.1-windows.zip`

## 0.3.5 — 2026-07-10

### Added

- **`build-fast.ps1`** — incremental PyInstaller builds (~5 min) without `--clean` or pip reinstall
- **`mpl_tk.py`** — lazy Matplotlib/TkAgg loading so charts defer NumPy until opened

### Changed

- **Faster app startup** — `graphs` and Matplotlib no longer import at launch
- **Leaner frozen build** — TkAgg-only matplotlib; optional Ollama Python client excluded from the exe bundle

### Build

- Windows app: `dist/Integral/Integral.exe` (release: `.\build.ps1`, dev: `.\build-fast.ps1`)
- Release zip: `Integral-v0.3.5-windows.zip`

## 0.3.4 — 2026-07-10

### Added

- **Graphs Dashboard** — default multi-panel view with 8 auto-picked rating charts; customize 4–12 domains; quick-view for hidden areas
- **Log Exercise search** — type-to-filter exercise picker (no Enter needed); double-click to add a set
- **AI Insight: Day Scanner** — same-day wrap-up with **Today (1 day)** period option
- **Five new AI insight types** — Energy & Burnout, Body & Movement, Gaps & Life Balance, Journal Themes (plus richer checklist/metrics context for the model)

### Fixed

- **Scroll glitches** — removed competing global mousewheel handlers that caused text overlap and crashes; Overview/Categories use shared scroll helper

### Build

- Windows app: `dist/Integral/Integral.exe` (run `.\build.ps1`)
- Release zip: `Integral-v0.3.4-windows.zip`

## 0.3.3 — 2026-07-08

### Added

- **AI Insight discoverability** — accent buttons on the dashboard, Today's Log bar, footer nav, Guidance, and Weekly Summary; dedicated Overview card for local Ollama insights
- **Graphs & Progress** — AI Insight is now the first tab; optional deep-link via "Open in Graphs & Progress"

### Fixed

- **Windows toast reminders** — no longer flash a System32 PowerShell console window from the windowed exe

### Build

- Windows app: `dist/Integral/Integral.exe` (run `.\build.ps1`)
- Release zip: `Integral-v0.3.3-windows.zip`

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
