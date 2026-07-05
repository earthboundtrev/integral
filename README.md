# Integral

> **Tend every area of your life. One honest day at a time.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Integral is a **free, open-source** desktop app for tracking your whole life — not just workouts or mood, but money, family, burnout, creativity, spirituality, emotions, and what you take in (food, art, books, and everyday content).

Log in seconds on hard days. See your year at a glance. Get gentle guidance when something starts slipping.

**No account. No cloud. Your journal stays on your computer.**

<p align="center">
  <img src="assets/integral-icon-source.png" alt="Integral app icon" width="128" height="128" />
</p>

---

## Open source — and why the fitness programs are here

Integral is released under the [MIT License](LICENSE). Anyone can read the code, run it, change it, and share it. That openness is exactly why this app can include **reference progression tables** for well-known bodyweight and mobility programs — built for personal use inside your own journal, not sold as a replacement for the books.

**I am not sponsored by, affiliated with, or endorsed by** the authors or publishers of those programs. Integral does not speak for them. If a table or step name differs from your copy of the book, **trust the book**.

If these programs have helped you and you want to support the people who wrote them, buy their work. That is the best way to say thank you:

| Program in Integral | Book (Amazon) |
|---------------------|---------------|
| Convict Conditioning (Big Six) | [Convict Conditioning](https://www.amazon.com/Convict-Conditioning-Paul-Wade/dp/0938045768) — Paul Wade |
| Convict Conditioning 2 | [Convict Conditioning 2](https://www.amazon.com/Convict-Conditioning-Advanced-Prison-Training/dp/1938898007) — Paul Wade |
| Explosive Calisthenics | [Explosive Calisthenics](https://www.amazon.com/Explosive-Calisthenics-Paul-Wade/dp/1938898074) — Paul Wade |
| Five Tibetan Rites | [The Eye of Revelation](https://www.amazon.com/Ancient-Secret-Fountain-Youth/dp/0919948013) — Peter Kelder |
| Overcoming Gravity | [Overcoming Gravity (2nd ed.)](https://www.amazon.com/Overcoming-Gravity-systematic-gymnastics-strength/dp/1452865756) — Steven Low |
| Strong Medicine | [Strong Medicine](https://www.amazon.com/Strong-Medicine-Conquer-Chronic-Achieve/dp/1938898244) — Chris Hardy & Marty Gallagher |
| Super Joints | [Super Joints](https://www.amazon.com/Super-Joints-Russian-Longevity-Pain-Free/dp/0938045369) — Pavel Tsatsouline |

*(Amazon links are standard referral-free product URLs for convenience; Integral earns nothing from them.)*

---

## What you can track

Integral is built around **life areas** — buckets you check in on each day (or whenever you have energy). On a rough day, a **1–10 rating and Save** is enough. When you have more time, add checklist ticks, quick numbers, and notes.

### Default life areas

Integral ships with **18 editable life areas** across financial, physical, mental, emotional, spiritual, relational, cultural, and environmental development — plus what you take in (food, art, books, content).

See **[docs/HOLISTIC_DEVELOPMENT_MODEL.md](docs/HOLISTIC_DEVELOPMENT_MODEL.md)** for the full domain map and how areas connect.

**Consumption detail & competitors:** [docs/INPUT_AND_CONSUMPTION_COMPARISON.md](docs/INPUT_AND_CONSUMPTION_COMPARISON.md)

You can rename areas, edit checklists, and add your own categories in the app.

### How the pieces fit together

| What you see | What it does for you |
|--------------|----------------------|
| **Overview** | Year-at-a-glance grid, today's snapshot, quarterly priorities, short guidance |
| **Categories** | Daily check-in per life area |
| **Day explorer** | Click any day on the grid to review or fill in the past |
| **Guidance** | Plain-language nudges when an area is neglected, trending down, or stuck |
| **Graphs** | Trends and balance over time |
| **Weekly summary** | A readable recap of your week |
| **Fitness Hub** | Log sessions against book-based programs; see progress and coaching hints |
| **Search** | Find old notes across life logs and workouts |
| **Export & backup** | CSV exports and full journal backups you control |

Guidance connects the dots — for example, low body energy when food hasn't been logged, or mood dipping when no art has been noted. It's pattern-spotting, not medical advice.

---

## Getting started

### Windows (easiest)

1. Download **`Integral-windows.zip`** from [Releases](https://github.com/earthboundtrev/integral/releases).
2. Unzip and double-click **`Integral.exe`**.

Your journal is saved on this PC (typically under `%APPDATA%\Integral\`). Use **Backup** inside the app, or copy that file, so you never lose your history. You can optionally lock the journal with a passphrase under **Data & Security**.

### First time in the app

1. Open **Categories** and pick one area — rating + **Save** counts.
2. Glance at **Overview** to see your activity grid fill in.
3. If you train with a book program, open **Fitness Hub** and log a session.
4. Check **Guidance** after a few days; it works better with a little history.

---

## Privacy

- Data is stored locally as JSON on your machine.
- No Integral account, no telemetry, no required internet connection.
- Optional encryption if you want the file passphrase-protected.
- Open source — you can verify what the app does.

---

## For developers

Integral is Python + Tkinter, local-first, with optional `cryptography` for encrypted journals.

```powershell
python -m pip install -r requirements.txt
.\run.ps1
```

Build Windows `.exe`: `.\build.ps1` → `dist\Integral\Integral.exe`

Run tests: `python -m unittest discover -s tests -v`

Project layout, roadmap, and competitive notes live in [`docs/`](docs/). Contributions welcome — open an issue before large changes.

---

## License

[MIT License](LICENSE) — Copyright (c) 2026 Integral contributors.
