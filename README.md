# Integral

**Local-first holistic life tracking** — daily reflection across eighteen domains, a private journal, fitness progression across multiple training systems, and exports/backups so your history survives.

> Previously developed as "Personal Development Tracker"; the app is **Integral**.

## Why Integral

### The lost notebook

Years ago I was grinding through Convict Conditioning and keeping a paper journal — reps, what hurt, what finally clicked, which step I was actually on. Then I lost it. Not “misplaced for a week” lost. **Gone.**

That one hurt. It wasn’t about the notebook itself. It was years of context vanishing: where I was in each progression, what I’d tried and failed, what my body had been learning week by week. After that I kept starting over in my head instead of building on something real. My training stalled. So did my confidence.

I don’t want to feel that again.

### reMarkable — great until it wasn't

I also had a **reMarkable tablet**, and I honestly loved it. E-ink felt like paper without hauling notebooks everywhere. I was happy with that setup.

Then I broke it. I didn’t have the money to replace it.

I still have their app on my computer, so I can open my old notes whenever I want. But I **can’t add to them**. Not really. Without the tablet, nothing new syncs into that world. I’m stuck looking at a frozen archive — my history is there, but the living record stopped the day the hardware did.

And it’s all tied to their cloud. I’ve thought about that more than I’d like. If their servers have a bad day — or worse — it messes with your ability to pull your own stuff down. Yeah, the app keeps local copies. That helps. But updating those copies is awkward, and if you fix something locally, **it doesn’t push back to the cloud**. So you’re in this weird middle: read-only history on one side, a sync model you don’t fully own on the other. That’s not how I want to hold onto my life.

### Paper again — and why it still falls short

So I went back to paper. I still believe writing by hand is good for the brain — I’m not giving that up.

But paper stinks as the *system*:

- I can **lose** it. I already did once.
- I can’t **see** trends — no streaks, no charts, no “oh, I’ve been skipping this for three weeks.”
- There’s **too much** to flip through by hand and actually learn from.
- My **handwriting** is rough; future-me does not want to decode it.
- It doesn’t stay **organized**. I can try. Software can do it better. Paper can’t.

### Externalizing what you're processing

Some of us don't really *know* what we think until it's outside our heads. Pen and paper are still the best tools I know for that — slow enough to feel honest, physical enough to stick. But paper alone can't carry everything I need to work through: eighteen life domains, fitness progressions, plans versus what actually happened, threads I need to find again months later.

I built Integral because **externalizing information is how I process it** — not as a productivity trick, but as a cognitive need. Once something is written in a structure I chose, I can compare days, notice drift, and stop rehearsing the same thoughts in a loop. A generic notes app captures fragments. A cloud journal often stops being *mine* the moment the hardware or the sync model changes. I wanted one place that holds the whole picture and stays on my machine.

If you're the kind of person who reaches for a notebook when something won't settle — and you've hit the ceiling of what paper alone can organize — you're probably the same kind of person who ends up building something like this. The need doesn't show up on a feature checklist. It's why the app exists at all.

### The combination approach

Integral is what I actually want: **keep writing things down** when that’s how I think — on paper, on whatever I have — but **put what needs to last** somewhere I control.

In Integral that means structured actions, dates, reasons, fitness progressions, the *why* behind what I did. I get to choose the shape of the record instead of hoping I find the right page in a pile of notebooks or a read-only cloud folder.

### Built with a force multiplier

I’m not a full-time programmer. I wouldn’t have built this the same way — or at this pace — without **AI as a force multiplier**. The design, the back-and-forth, the “make it faster, make it mine” iteration: that’s far easier with help. Integral exists because keeping my own data local matters to me, and because finally, building something this personal is realistic.

I care enough to use it. I just wasn’t going to hand-write all of this code myself.

### What Integral gives you

- **Everything lives on your machine** — searchable, reviewable, exportable
- **Optional encryption** — journal-grade privacy for thoughts you would not put on a random cloud app
- **Backups and CSV export** — zip your full life data + fitness progress; keep copies like you wish you had for that notebook
- **Backdated entries with a reason** — catch up honestly without pretending you logged on the day (accountability, not cheating the tool)
- **Fitness Hub** — CC and other programs as structured progressions, not scattered notes

Integral is for the lightweight daily check-in *and* the detailed stream-of-consciousness reflection — the kind of record you would want to read back years later, without digging through paper, hoping the cloud still works, or wondering where you left off.

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
| **Life domains (18)** | Ratings, checklists, metrics, notes, streaks, guidance |
| **Journal** | Prompts or free write; backdate with reason |
| **Activity** | GitHub-style contribution grid; click any day |
| **Fitness Hub** | CC1/CC2/SS/OG/EC/FTR — nested book → program → steps |
| **Safety net** | Export CSV, full JSON backup, optional vault encryption |
| **AI Insight (optional)** | Local Ollama review of recent logs — see below |

Tests: `python -m pytest tests/ -q`

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
- **Today's Log** bar — **AI Insight** (accent button, top of the main window)
- **Footer nav** — **AI Insight** next to Weekly Summary
- **Graphs & Progress → AI Insight** — first tab; pick insight type and time window, then generate
- **Weekly Summary** / **Guidance** — **Get AI Insight** or **AI Insight** in the footer

**Setup (Windows)**

1. Install [Ollama](https://ollama.com) (or `winget install Ollama.Ollama`) and start it — the tray app or `ollama serve`
2. From the Integral repo: `pip install -r requirements-ai.txt`
3. Pull the default model (about 2 GB): `ollama pull llama3.2:3b`
4. Open Integral and use **AI Insight** as above

The first insight after a cold start can take 30–60 seconds while the model loads; later runs are faster. Integral runs fine without Ollama — this feature is entirely optional and skipped if the client or server is missing.

## Documentation

| Doc | Contents |
|-----|----------|
| [CHANGELOG.md](CHANGELOG.md) | Release notes |
| [docs/PRD.md](docs/PRD.md) | Product requirements |
| [docs/VISION.md](docs/VISION.md) | Vision and principles |
| [docs/BUILD.md](docs/BUILD.md) | Build instructions |

## License

See [LICENSE](LICENSE).
