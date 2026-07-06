# Integral — Vision

> **Canonical product doc:** [`PRD.md`](PRD.md)  
> **Release notes:** [`../CHANGELOG.md`](../CHANGELOG.md)

## What This Is

**Integral** is a local-first desktop app for holistic personal development — daily logging across eighteen life domains, a dedicated journal, fitness progression across respected training systems, and exports/backups that protect years of personal history.

## Why It Exists

The origin story is simple and personal: a lost training journal during a Convict Conditioning phase erased months of progression notes and stalled growth. Paper is wonderful until it is gone. Cloud apps are convenient until you do not trust them with your inner life.

Integral is the answer to both:

1. **Your data stays yours** — local files, optional encryption, portable backups
2. **Review is easy** — search, history, activity grid, exports for long-term reading
3. **Honest logging** — backdated entries require a reason; the tool supports integrity, not vanity metrics
4. **Training memory** — fitness progressions (CC, Starting Strength, Overcoming Gravity, etc.) live beside daily life logs, not in a separate lost notebook

If you have ever reopened a blank page and thought *I know I was further than this, I just cannot remember where* — Integral is for you.

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
