# Integral

**Local-first holistic life tracking** — daily reflection across life domains you define, a private journal, fitness progression across multiple training systems, and exports/backups so your history survives. Python + Tkinter desktop app for Windows. AI writes the application code; a human sets the requirements, reviews the changes, and decides what ships.

> Previously developed as "Personal Development Tracker"; the app is **Integral**.

Full background: [Trevor Thompson](#about-the-builder).

---

## Table of Contents

- [Why Integral](#why-integral)
- [Quick start](#quick-start)
- [What you get](#what-you-get)
- [How This Codebase Is Built](#how-this-codebase-is-built)
  - [Workflow evolution](#workflow-evolution)
  - [Integral AI team workflow (10/14/2026)](#integral-ai-team-workflow-10142026)
  - [Round handoff](#round-handoff)
  - [GitHub ticket flow](#github-ticket-flow)
  - [What this is not](#what-this-is-not)
  - [Standing ops](#standing-ops)
- [Testing](#testing)
- [Documentation](#documentation)
- [License](#license)
- [About the Builder](#about-the-builder)

---

## Why Integral

### The lost notebook

Years ago I was grinding through Convict Conditioning and keeping a paper journal — reps, what hurt, what finally clicked, which step I was actually on. Then I lost it. Not "misplaced for a week" lost. **Gone.**

That one hurt. It wasn't about the notebook itself. It was years of context vanishing: where I was in each progression, what I'd tried and failed, what my body had been learning week by week. After that I kept starting over in my head instead of building on something real. My training stalled. So did my confidence.

I don't want to feel that again.

### reMarkable — great until it wasn't

I also had a **reMarkable tablet**, and I honestly loved it. E-ink felt like paper without hauling notebooks everywhere. I was happy with that setup.

Then I broke it. I didn't have the money to replace it.

I still have their app on my computer, so I can open my old notes whenever I want. But I **can't add to them**. Not really. Without the tablet, nothing new syncs into that world. I'm stuck looking at a frozen archive — my history is there, but the living record stopped the day the hardware did.

And it's all tied to their cloud. I've thought about that more than I'd like. If their servers have a bad day — or worse — it messes with your ability to pull your own stuff down. Yeah, the app keeps local copies. That helps. But updating those copies is awkward, and if you fix something locally, **it doesn't push back to the cloud**. So you're in this weird middle: read-only history on one side, a sync model you don't fully own on the other. That's not how I want to hold onto my life.

### Paper again — and why it still falls short

So I went back to paper. I still believe writing by hand is good for the brain — I'm not giving that up.

But paper stinks as the *system*:

- I can **lose** it. I already did once.
- I can't **see** trends — no streaks, no charts, no "oh, I've been skipping this for three weeks."
- There's **too much** to flip through by hand and actually learn from.
- My **handwriting** is rough; future-me does not want to decode it.
- It doesn't stay **organized**. I can try. Software can do it better. Paper can't.

### Externalizing what you're processing

Some of us don't really *know* what we think until it's outside our heads. Pen and paper are still the best tools I know for that — slow enough to feel honest, physical enough to stick. But paper alone can't carry everything I need to work through: eighteen life domains, fitness progressions, plans versus what actually happened, threads I need to find again months later.

I built Integral because **externalizing information is how I process it** — not as a productivity trick, but as a cognitive need. Once something is written in a structure I chose, I can compare days, notice drift, and stop rehearsing the same thoughts in a loop. A generic notes app captures fragments. A cloud journal often stops being *mine* the moment the hardware or the sync model changes. I wanted one place that holds the whole picture and stays on my machine.

If you're the kind of person who reaches for a notebook when something won't settle — and you've hit the ceiling of what paper alone can organize — you're probably the same kind of person who ends up building something like this. The need doesn't show up on a feature checklist. It's why the app exists at all.

### The combination approach

Integral is what I actually want: **keep writing things down** when that's how I think — on paper, on whatever I have — but **put what needs to last** somewhere I control.

In Integral that means structured actions, dates, reasons, fitness progressions, the *why* behind what I did. I get to choose the shape of the record instead of hoping I find the right page in a pile of notebooks or a read-only cloud folder.

### Built with a force multiplier

I'm not a full-time programmer. I wouldn't have built this the same way — or at this pace — without **AI as a force multiplier**. The design, the back-and-forth, the "make it faster, make it mine" iteration: that's far easier with help. Integral exists because keeping my own data local matters to me, and because finally, building something this personal is realistic.

I care enough to use it. I just wasn't going to hand-write all of this code myself.

### What Integral gives you

- **Everything lives on your machine** — searchable, reviewable, exportable
- **Optional encryption** — journal-grade privacy for thoughts you would not put on a random cloud app
- **Backups and CSV export** — full zip backup includes life data, Writing Project manuscripts (`creative/`), and fitness progress; CSV Export also ships a creative documents zip for offline copies
- **Backdated entries with a reason** — catch up honestly without pretending you logged on the day (accountability, not cheating the tool)
- **Fitness Hub** — CC and other programs as structured progressions, not scattered notes
- **Writing Projects** — novels and scripts with an inspiration document beside the manuscript (autosave, local files)
- **Deep Work Mode** — a focus timer that quiets the rest of the app so you can write or log without chrome noise

Integral is for the lightweight daily check-in *and* the detailed stream-of-consciousness reflection — the kind of record you would want to read back years later, without digging through paper, hoping the cloud still works, or wondering where you left off. **Depth is optional:** one rating is a complete honest day; unused domains stay quiet. The tool works for you — you don't work for the tool.

## Quick start

**From source:**
```bash
pip install -r requirements.txt
python personal_dev_tracker.py
```

**Windows build:**
```powershell
pip install -r requirements.txt -r requirements-build.txt
.\build.ps1
# Run: dist\Integral\Integral.exe
```

User data: `%APPDATA%\Integral\data.json` (encrypted optional via Data & Security).

## What you get

| Area | Features |
|------|----------|
| **Left sidebar navigation** | 240px persistent sidebar with brand, tagline, and quick access to Today, Fitness Hub, Reflect, Journal, Graphs, Weekly Summary; **Go to…** (Ctrl+K, text-safe); global shortcuts **Ctrl+Shift+T** (Today todo / Quick Capture), **W** (log workout), **R** (Reflect), **J** (Journal), **I** (Weekly Summary), **G** (Graphs), **Ctrl+Shift+/** or **F1** (shortcut list); **Reflect** opens a one-screen daily reflection page (all domains, single Save); open windows raise-if-open instead of duplicate; footer and sidebar **More…** opens a grouped popup (15 actions in VIEW / WORK MODES / DATA & SETTINGS) with ↑↓ Enter Esc, type-ahead, and shortcut hints where available |
| **Life domains (18)** | Ratings, checklists, metrics, notes, streaks, guidance — **optional depth**; one check-in is enough; never scored as N/18 completeness; **Today's Log** inline todo (type + Enter for today, last-used category), one-tap **+ Todo / Log workout / Reflect**, Find filter + All/Unlogged/Logged, pin up to 5 favorites (right-click), and a **More…** menu |
| **Go to…** | Command palette (footer or Ctrl+K) to jump to any screen or Log a domain by typing |
| **Domain templates** | One-click starter packs (**Gut Healing**, **Personal Health & Alignment**) add a coherent set of pre-configured domains; applied from onboarding or the category editor, never overwriting existing domains |
| **Daily practices** | Log non-program routines (Five Tibetan Rites, Strong Medicine, breathing, wind-releasing yoga) with duration, reps/completions, hold time, quality (1–10), an optional per-movement breakdown, a subjective "effect" note, and free notes; reachable from Quick Capture **and** the Fitness Hub; flows into the linked life domain for history, streaks, and insights |
| **Workout history** | One-click access from Today's Log and Fitness Hub to complete session history — two-pane view with list (month headers, keyset paging, exercise filter) and detail pane showing exercises, sets, volume, **PR / =PR badges**, trend hints, and notes per session; click an exercise (or focus it and press Enter) for per-exercise history with a **sparkline** trend and all-time PR summary |
| **Symptom correlations** | Guidance compares symptom metrics (gas, bloating, comfort, energy) on days *with* a logged practice vs *without*, surfacing patterns like "lower gas on practice days"; a "Gut & Symptom Patterns" AI insight goes deeper |
| **Practice reminders** | Set nudges for specific routines (e.g. "Five Tibetan Rites + 10 min breathing") at a chosen time; guidance also flags practice consistency (kept-up vs stalled) |
| **Goals & alignment** | Quarterly milestones can link to a life domain and carry a simple progress %; journal reflection prompts for alignment, masking, autism self-understanding, and goals |
| **AI insight focuses** | Optional local (Ollama) insight kinds for Vitality & Anti-Aging, Sleep & Hypersomnia, Neurodivergence & Alignment, and Life Alignment & Goals — reasoning over your domains, practices, symptoms, and journal, fully offline |
| **Journal** | Prompts or free write; markdown-lite toolbar (bold/italic/headings/lists); backlinks; cross-links to journal/domain/fitness/writing; gap-day continuity; OS `integral://` paste; **Edit in system editor** for Grammarly outside Tk |
| **Writing Projects** | Novels/scripts library — inspiration + manuscript in separate windows; debounced autosave; stored under `%APPDATA%\Integral\creative\`; **Open externally** / **Reload from disk** |
| **Creative/Mental Work** | Open Writing Projects from the category log; **Log writing session** marks creative progress for the day |
| **Deep Work** | Focus timer (25 / 50 / 90 / custom); quieter nav; optional open a writing project; +10 min or end early |
| **Activity** | GitHub-style contribution grid; click any day; smooth horizontal scroll |
| **Save feedback** | Top-of-window success/error banners (truthful after disk write; errors stay until ✕); inline validation on Save and focus-out; post-reflection guidance as a dismissable banner with **Don't show again** (re-enable in Settings); workout save uses **Undo** instead of a delete-confirm modal |
| **Snappy UI** | Soft Overview refresh (no full rebuild on Refresh/save paths); cached fitness day counts; footer / Today's Log scroll coalesced so fast flicks do not ghost buttons |
| **Streak** | Overall streak counts life log, journal, or fitness for the day; updates as soon as you save; mid-day grace if today is still empty; **click the header streak pill (· details)** to open Overview & Categories in a full window (activity grid, guidance, domain cards) so the main dashboard stays Today's Log-focused |
| **Quick Capture** | Optional always-on-top panel (off by default): open from **Today's Log** (next to Journal / More…) or the footer nav; today's todos + scheduled backlog with collapsible sections, inline edit, and drag-free ↑/↓ reordering; **finish always logs to a life domain** (prompts for category if missing — same idea as Link → day entry / YouTube); link starters; Journal now; quick-log opener; **domain typeahead** on category pickers; Deep Work timer + Windows focus shield (minimize chosen apps) |
| **Fitness Hub** | CC1/CC2/SS/SM/OG/EC/FTR — nested book → program → steps; **Log Exercise** with **Add** (picker + metrics), **+ Set** (copy last queued row), **Repeat last session**, re-pick/remove queued sets without Canceling the draft, **Save Session** with banner **Undo**; **volume vs last log** while logging (↑/→/↓ on sets×reps or weighted volume; click for history carousel) |
| **Fitness skill tree** | Progressive logging DAG for full CC1 Big Six, full CC2 ladders, and Strong Medicine resistance progressions (squat→barbell, sumo DL, DB bench/press, statue row, plank core) from official Hub tables |
| **Safety net** | Export CSV (+ creative docs zip + YouTube history CSV when imported), full zip backup (data + `creative/` + fitness), optional vault encryption |
| **YouTube Takeout** | Import watch history from a free Google Takeout JSON/zip (Data & Security); merge/dedupe locally; optional day notes for Content / Art — no API keys, no account connect |
| **Reminders** | Windows toasts while Integral is running; optional Start with Windows + minimize-on-close so reminders keep working |
| **AI Insight (optional)** | Local Ollama review of recent logs — see below |

Tests: `python -m pytest tests/ -q`

### Writing Projects & Deep Work

**Writing Projects** keep long-form creative work inside Integral without bloating daily logs:

- Select a project, then **Continue Writing** to open the manuscript (double-click works too)
- Open Inspiration for premise/notes, or **Open Both** so the premise stays visible while you write
- Text autosaves after a short pause; Save and app quit also flush
- From **Creative/Mental Work** logging, jump to Writing Projects or explicitly **Log writing session** for the day

**Deep Work Mode** is app-wide focus:

- Start from Overview or the footer (**Deep Work**)
- Pick a duration; optionally open a writing project's inspiration + manuscript
- Non-essential nav (graphs, fitness, export, settings, …) hides for the session; Journal and Writing Projects stay available
- Countdown banner with **+10 min** and **End Deep Work**

### Reminders (Windows)

Daily reminder toasts only fire **while Integral is running** — the portable zip is not a background Windows service. Under **Data & Security**:

- **Enable daily reminder toasts**
- **Minimize to taskbar on close** — closing the window keeps Integral (and reminders) alive; restore from the taskbar
- **Start Integral with Windows** — launches at sign-in so reminders can run through the day
- **Send test notification** / **Quit Integral completely** when you want a real exit

### OS deep links (Windows)

Under **Data & Security**, enable **Register integral:// protocol with Windows**. Then:

1. Open a journal entry → **Copy link** (clipboard gets `integral://journal/{id}` plus a wiki form)
2. Paste that `integral://` URL in a browser address bar, chat, or notes app and open it
3. Windows launches Integral (or hands off to a running instance) and focuses that journal entry

Links accept `integral://journal/{id}`, `integral://domain/{date}/{category}`, `integral://fitness/{date}`, and `integral://project/{id}`.

### YouTube watch history (Google Takeout)

YouTube does **not** let third-party apps pull full watch history via API. Integral imports a free **Google Takeout** file instead (no API keys, no Google login inside the app):

1. Open [takeout.google.com](https://takeout.google.com) → **Deselect all** → enable **YouTube and YouTube Music**
2. Under that product, include **History**, prefer **JSON**
3. Create the export, download the zip when Google emails you
4. In Integral → **Data & Security** → **Import YouTube Takeout…** and pick `watch-history.json` or the zip
5. Optionally append daily summaries to **Content You Have Consumed** / **Art You Have Consumed** notes (never auto-sets ratings)

Re-import merges and skips duplicates. Browse imported watches from the same screen. CSV Export includes a YouTube history file when data is present. Button-triggered refresh of a newer Takeout file is tracked in [#83](https://github.com/earthboundtrev/integral/issues/83).

### Optional: Local AI insights (Ollama)

Integral can summarize your last **7–30 days** with a **small local model** — no cloud API, no embeddings, no extra databases. Your logs stay on your machine; only a compact text summary of recent domains, journal excerpts, and fitness sessions is sent to Ollama on `localhost`.

**Insight types**

| Type | Best for | Default period |
|------|----------|----------------|
| **Day Scanner** | Same-day wrap-up — wins, gaps, one next step | Today (1 day) |
| **Weekly Review** | Patterns, wins, and 1–2 concrete next steps | 7 days |
| **Emotional Patterns** | Mood, stress, relational notes, burnout signals | 7 days |
| **Energy & Burnout** | Sleep, boundaries, recovery, energy management | 7 days |
| **Body & Movement** | Exercise, fitness sessions, physical self-care | 7 days |
| **Gaps & Life Balance** | Neglected domains and rebalancing across 18 areas | 30 days |
| **Journal Themes** | Recurring themes in journal and domain notes | 7 days |

Period options: **1** (today), **7**, or **30** days. Choosing an insight type auto-suggests its default period; you can override.

**Where to find it**

- **Overview tab** — "Local AI Insight" card and **AI Insight** button on the stats row
- **Today's Log** bar — one filled primary action (**Log one → …** when a domain still needs a check-in)
- **Footer nav** — **AI Insight** next to Weekly Summary
- **Graphs & Progress → AI Insight** — first tab; pick insight type and time window, then generate
- **Weekly Summary** / **Guidance** — **Get AI Insight** or **AI Insight** in the footer

**Setup (Windows)**

1. Install [Ollama](https://ollama.com) (or `winget install Ollama.Ollama`) and start it — the tray app or `ollama serve`
2. From the Integral repo: `pip install -r requirements-ai.txt`
3. Pull the default model (about 2 GB): `ollama pull llama3.2:3b`
4. Open Integral and use **AI Insight** as above

The first insight after a cold start can take 30–60 seconds while the model loads; later runs are faster. Integral runs fine without Ollama — this feature is entirely optional and skipped if the client or server is missing.

### Grammarly / desktop writing assistants

Grammarly Desktop (and similar tools) typically **cannot** underline or suggest inside Integral's built-in text boxes. Integral uses **Tkinter** `Text` widgets, which Windows does not expose via the UI Automation Text Pattern Grammarly hooks (unlike Word, browsers, and many Electron apps). This is a toolkit limitation (ADR-001: Python + Tkinter), not a broken setting.

**Workarounds in-app:**

- **Journal** → **Edit in system editor…** — opens a draft in your default text app; reload when done
- **Writing Projects** (Inspiration / Manuscript) → **Open externally…** then **Reload from disk** after saving in Word/Notepad/VS Code/etc.

---

## How This Codebase Is Built

**The application source code is written by AI** (as described in [Built with a force multiplier](#built-with-a-force-multiplier)). Trevor owns everything around the code: requirements, prompts and workflow, product decisions, review, and deciding when a change is safe to use on his own data.

Integral was built with Cursor as the coding agent.

### Workflow evolution

| Era | Effective | Handoff chain | What changed |
|-----|-----------|---------------|--------------|
| Pre-team (solo + AI) | Project start → 10/13/2026 | Trevor → Cursor (vibe-coded) | Solo, conversational prompting in Cursor; no dedicated test, triage, or review roles |
| **Integral AI team** | **10/14/2026** | Tester → Requirements Analyst → Product Manager → Cursor → Lead Developer tests; Daily Update + Workflow Historian alongside | Dedicated roles for finding, writing up, ranking, and verifying work; nightly status email; dated workflow log |

New rows are added by the Workflow Historian when new workflow specs land.

### Integral AI team workflow (10/14/2026)

On 10/14/2026 Trevor set up a team of Grok Bot agents around Integral. They don't replace the test suite; they feed the same AI build loop with findings, issues, and priorities.

| Role | What it does |
|------|--------------|
| **Tester** | Uses Integral (Python/Tk desktop app) and finds bugs. |
| **Requirements Analyst** | Turns findings into GitHub issues. |
| **Product Manager** | Ranks issues and writes Cursor briefs for the work to be done. |
| **Lead Developer** | Runs the tests each day. |
| **Daily Update** | Emails Trevor a nightly Integral update. |
| **Workflow Historian** | Keeps a dated workflow log, records how the workflow evolves (with a 9 PM ET daily backstop), and updates this document when new specs land. |

### Round handoff

Issues are written by the Requirements Analyst and filed to GitHub. The Product Manager ranks them and writes a Cursor brief. Trevor runs the brief through Cursor and reviews the change. The Lead Developer's daily test run confirms the suite. The Daily Update reports the day to Trevor. The Workflow Historian logs any process change.

### GitHub ticket flow

Integral's tickets live in [GitHub Issues](https://github.com/earthboundtrev/integral/issues) on `earthboundtrev/integral`. Every fix ships through a PR tied to one issue, following the Cursor rule `.cursor/rules/ticket-lifecycle-loop.mdc` (adapted from the SmartAstro / Ducking Gravity pipeline).

**Labels**

| Group | Labels |
|-------|--------|
| Type | `type: bug`, `type: feature`, `type: test`, `type: chore` |
| Priority | `priority: critical`, `priority: high`, `priority: medium`, `priority: low` |
| Area | `area: ai-insights`, `area: data-migration`, `area: fitness`, `area: graphs`, `area: packaging`, `area: platform`, `area: skill-tree`, `area: storage`, `area: tests`, `area: ui`, `area: vault/encryption`, `area: youtube` |
| GitHub defaults | `bug`, `enhancement`, `documentation`, `duplicate`, `invalid`, `wontfix`, `question`, `help wanted`, `good first issue` |

Older tickets (through #86) use the default `bug` / `enhancement` labels. Issues #88–#99, filed 10/14/2026, use the type / priority / area scheme.

**Issue shape.** The repo has no `.github/` issue templates. Bodies follow a convention instead. Feature tickets use *Summary / User story / Acceptance criteria / Notes* (e.g. #86). Bug reports from testing passes use *Who hit it / environment / Steps to reproduce / Expected / Actual / In everyday words / Acceptance criteria / Related* (e.g. #95).

**States.** Open → closed as *completed* when the linked PR merges, or closed as *not planned* for duplicates (e.g. #62, #63 duplicating #64).

**From finding to fix to verification**

1. **Finding.** The Tester (or Trevor) hits a bug.
2. **Issue.** Issues are written by the Requirements Analyst and filed to GitHub with type / priority / area labels.
3. **Rank + brief.** The Product Manager orders the open issues by priority and writes a Cursor brief.
4. **Ship pointer in Cursor** (`ticket-lifecycle-loop.mdc`): `IMPLEMENT → BUGBOT → TESTS → ARCHITECT → DEPLOY`. Bugbot and Architect are separate review Tasks, never the implementer self-certifying. Any code fix rewinds the pointer to BUGBOT. TESTS means `py_compile` plus `pytest`. New user-facing features need an approved `docs/specs/` spec first (ADR-007).
5. **PR + merge.** The PR body carries `Closes #N`, and Trevor merges.
6. **Hard close gate.** A ticket is not done until the PR is merged, issue `#N` is **CLOSED**, and the feature branch is deleted. The repo has `delete_branch_on_merge` on, and `scripts/post_merge_hygiene.ps1 -Issue N -PR P` verifies and cleans up (added in PR #70).
7. **Verification.** The Lead Developer's daily test run confirms the suite stays green.

### What this is not

- Not a replacement for the pytest suite (`python -m pytest tests/ -q`)
- Not an automatic issue firehose — issues are written thoughtfully and filed with context

### Standing ops

- **Daily tests:** Lead Developer runs the test suite each day.
- **Nightly update:** Daily Update emails Trevor a nightly Integral summary.
- **Workflow memory:** Workflow Historian keeps a dated workflow log; daily backstop at 9 PM ET.
- **Doc freshness:** Workflow Historian updates this document when new workflow specs land.

---

## Testing

```bash
python -m pytest tests/ -q
```

## Documentation

| Doc | Contents |
|-----|----------|
| [CHANGELOG.md](CHANGELOG.md) | Release notes |
| [docs/PRD.md](docs/PRD.md) | Product requirements |
| [docs/VISION.md](docs/VISION.md) | Vision and principles |
| [docs/BUILD.md](docs/BUILD.md) | Build instructions |

## License

See [LICENSE](LICENSE).


---

## About the Builder

**[Trevor Thompson](https://www.linkedin.com/in/trevor-thompson-dev)** · [LinkedIn](https://www.linkedin.com/in/trevor-thompson-dev) · [GitHub](https://github.com/earthboundtrev)

System engineer (Booz Allen Hamilton). On his own time he ships apps the AI-native way: **AI writes the application code**; Trevor does the requirements, prompts, workflow management, review, and the call on what's safe to ship. His production showcase is [SmartAstro](https://gitlab.com/earthboundtrev/astro), a studio-management system in daily use; Integral is his personal, local-first counterpart built with the same approach.
