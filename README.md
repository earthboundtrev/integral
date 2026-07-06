# Integral

**Local-first holistic life tracking** — daily reflection across eighteen domains, a private journal, fitness progression across multiple training systems, and exports/backups so your history survives.

> Previously developed as "Personal Development Tracker"; the app is **Integral**.

## Why Integral

Years ago I was working through the Convict Conditioning series and logging reps, progress, and what my body was learning in a physical notebook. I lost that journal. It was devastating — not because the paper was special, but because **years of context vanished**: where I was in each progression, what had finally clicked, what I had tried and failed. That loss stalled my training and my confidence. I kept starting over in my head instead of building on real history.

Integral is built so that feeling does not have to happen again:

- **Everything lives on your machine** — searchable, reviewable, exportable
- **Optional encryption** — journal-grade privacy for thoughts you would not put on a random cloud app
- **Backups and CSV export** — zip your full life data + fitness progress; keep copies like you wish you had for that notebook
- **Backdated entries with a reason** — catch up honestly without pretending you logged on the day (accountability, not cheating the tool)
- **Fitness Hub** — CC and other programs as structured progressions, not scattered notes

Integral is for the lightweight daily check-in *and* the detailed stream-of-consciousness reflection — the kind of record you would want to read back years later, on screen or on a reMarkable-style tablet, without digging through paper or hoping you did not lose the one notebook that mattered.

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

Tests: `python -m pytest tests/ -q`

## Documentation

| Doc | Contents |
|-----|----------|
| [CHANGELOG.md](CHANGELOG.md) | Release notes |
| [docs/PRD.md](docs/PRD.md) | Product requirements |
| [docs/VISION.md](docs/VISION.md) | Vision and principles |
| [docs/BUILD.md](docs/BUILD.md) | Build instructions |

## License

See [LICENSE](LICENSE).
