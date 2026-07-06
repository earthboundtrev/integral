# Integral — Vision

> **Canonical product doc:** [`PRD.md`](PRD.md)  
> **Release notes:** [`../CHANGELOG.md`](../CHANGELOG.md)

## What This Is

**Integral** is a local-first desktop app for holistic personal development — daily logging across eighteen life domains, a dedicated journal, fitness progression across respected training systems, and exports/backups that protect years of personal history.

## Why It Exists

Integral grew out of a chain of failures — not of effort, but of **tools that could not hold a life record safely**.

### Lost training journal

A lost Convict Conditioning notebook erased months of progression notes and stalled growth. Paper is wonderful until it is gone. I kept reopening a blank page thinking *I know I was further than this — I just cannot remember where.*

### reMarkable

I used a reMarkable tablet and liked it. When it broke and I could not afford a replacement, the story changed again. Their app still lets me **view** old notes, but I cannot **add** to that world without the hardware that syncs to their cloud. Local copies exist, yet updating them is clunky, and edits on disk do not flow back upstream. If the cloud has an outage — or worse — your relationship to your own archive becomes fragile. Convenience and ownership are not the same thing.

### Paper, again

I returned to paper for the cognitive benefits of handwriting. It still fails as infrastructure: easy to lose, impossible to chart over time, too much volume to revisit by hand, illegible in my own script, and fundamentally **unorganizable** without software.

### The hybrid

Integral is the combination I want: **write when writing helps you think**, but **store what must last** in a form I control — structured actions, dates, reasons, fitness progressions, journal entries, exports I can keep. Local-first, optionally encrypted, backup-friendly. Not a replacement for every way you capture thought; a durable layer underneath it.

### Why build it now

I am not a career developer. **AI acts as a force multiplier** — design, implementation, and iteration are far more tractable than they would have been alone. That does not make the product less personal; it makes building something this tailored finally realistic.

If you have ever lost a notebook, hit read-only on your own notes, or stared at unsearchable pages and thought *there has to be a better way* — Integral is for you.

### What Integral delivers

1. **Your data stays yours** — local files, optional encryption, portable backups (no cloud required to use or review)
2. **Review is easy** — search, history, activity grid, exports for long-term reading
3. **Honest logging** — backdated entries require a reason; the tool supports integrity, not vanity metrics
4. **Training memory** — fitness progressions (CC, Starting Strength, Overcoming Gravity, etc.) live beside daily life logs, not in a separate lost notebook
5. **Hybrid capture** — handwriting and quick notes still have a place; Integral is where structured history lives

## Core Principles

1. **Lightweight first** — Fast cold start, low memory, Tkinter not Electron.
2. **Local-first** — `%APPDATA%\Integral\` (or dev `data/data.json`). No cloud required.
3. **Graph-based fitness** — Exercises are nodes in a DAG across books and families.
4. **Honest tracking** — Ratings, checklists, metrics, journal, streaks — not gamification theater.
5. **Recoverable** — Export and backup are first-class; losing a device should not mean losing your story.

## Life Domains (18)

Eight original domains expanded to eighteen, including career, relationships, home, learning, culture, food, art consumed, reading, and content consumed — see `personal_dev_tracker.py` defaults and git history (`6056116`).

## Fitness Evolution Platform

- Convict Conditioning 1 & 2, Explosive Calisthenics, Overcoming Gravity, Starting Strength, Five Tibetan Rites
- Fitness Hub: book → program family → step series
- SQLite `fitness.db` per profile for progression state
- Demo video links and skill tree view

## What Success Looks Like

- Daily logging takes under a minute per domain when you are tired; journal when you have more to say
- You can find any note or training entry from years ago in seconds
- A full backup fits in a zip you control
- Losing a physical notebook never has to mean losing your training arc again

## Non-Goals (For Now)

- Cloud sync or online accounts
- Mobile native apps
- Social features
- Electron / heavy web stacks

## Distribution

- Windows: `dist/Integral/Integral.exe` via `build.ps1`
- Version tracked in `paths.APP_VERSION` and `CHANGELOG.md`
