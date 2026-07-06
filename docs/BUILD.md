# Build Standalone EXE

Local-first: the EXE bundles Python + app code. **Your data stays in** `~/.personal_dev_tracker/` (profiles, logs, fitness DB) — not next to the EXE.

## Prerequisites

- Windows
- Python 3.11+
- Runtime deps: `pip install -r requirements.txt`
- Build deps: `pip install -r requirements-build.txt`

## Build

```powershell
cd C:\Users\THOMP\personal-dev-tracker
pip install -r requirements.txt -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
```

Output: `dist\PersonalDevelopmentTracker.exe`

## Run

Double-click `dist\PersonalDevelopmentTracker.exe` or:

```powershell
.\dist\PersonalDevelopmentTracker.exe
```

## Develop (without EXE)

```powershell
python tracker.py
```

## What gets bundled

- `tracker.py` and all imported modules
- `progression/seed/v1/*.json` (fitness seed data)
- matplotlib (loaded only when you open Graphs tab)

## What stays outside the EXE

- Daily logs: `~/.personal_dev_tracker/profiles/<profile>/data.json`
- Fitness graph: `~/.personal_dev_tracker/profiles/<profile>/fitness.db`
- App config: `~/.personal_dev_tracker/config.json`

Updating the EXE does not delete your data.
