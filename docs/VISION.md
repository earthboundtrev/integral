# Personal Development Tracker — Vision

> **Canonical product doc:** [`PRD.md`](PRD.md)  
> **Implementation:** agents execute approved specs in [`specs/`](specs/README.md) — not this file directly.

## What This Is

A **local-first, lightweight desktop app** for holistic personal development tracking. It starts as a daily log across eight life domains and grows into a unified progression platform — beginning with fitness, where exercise systems from multiple books connect into one skill tree.

## Core Principles

1. **Lightweight first** — Fast cold start, low memory, minimal dependencies. Every feature must justify its cost.
2. **Local-first** — Data lives on the user's machine (`~/.personal_dev_tracker/`). No cloud required for core use.
3. **Graph-based progression** — Exercises (and eventually other domain skills) are nodes in a directed acyclic graph, not isolated linear lists.
4. **Honest tracking** — Ratings, checklists, metrics, notes, streaks, and summaries over gamification theater.
5. **Extensible categories** — Fitness is the first deep domain; the same progression pattern applies to other categories later.

## Life Domains (8 Categories)

| Category | Focus |
|----------|-------|
| Money/Freedom | Finances, long-term goals, freedom mindset |
| Body & Presence | Movement, mindfulness, nourishment, sleep, energy |
| Burnout Prevention & Energy Management | Breaks, boundaries, self-care, stress |
| Creative/Mental Work | Deep work, ideas, creative projects |
| Family/Logistics | Quality time, tasks, communication |
| Search Practice | Inquiry, reflection, concrete search actions |
| Spiritual Development | Practice, teachings, gratitude, connection |
| Emotional Wellbeing | Emotional check-ins, journaling, regulation |

Each category has: checklist items, typed metrics (number/rating), overall daily rating (1–10), and free-form notes.

## Fitness Evolution Platform (Phase 2+)

Combines respected training systems into one experience:

- **Convict Conditioning 1 & 2 + Explosive Calisthenics** (Paul Wade)
- **Overcoming Gravity** (Steven Low) — gymnastics / advanced bodyweight
- **Starting Strength** (Mark Rippetoe) — barbell
- **Five Tibetan Rites** — yoga / vitality

Beyond workout logging: visual progression, body composition (weight, measurements, photos), and eventually an AI coach that reads the progression graph to suggest personalized paths.

## What Success Looks Like

- App opens in under 2 seconds on a typical machine.
- Daily logging takes under 60 seconds per category.
- Graphs and summaries update instantly from local data.
- Fitness progression shows a clear "where am I / what's next" skill tree across books.
- Adding a new exercise or program does not require rewriting core logic.

## Non-Goals (For Now)

- Cloud sync or online accounts (local profiles only)
- Mobile apps
- Social features
- Electron or heavy web stacks
- Rewriting in C++ (see ADR-001)

## Distribution

- Standalone Windows `.exe` — local-first, no installer required (ADR-009, `docs/BUILD.md`)
- User data in `~/.personal_dev_tracker/` — not bundled inside the EXE
