# ADR-009: Standalone EXE Distribution (Local-First)

**Status:** Accepted  
**Date:** 2026-06-27

## Context

Users want a classic desktop app: double-click an `.exe`, no Python install, no terminal. The product must remain **local-first** — no cloud, no installer that phones home.

## Decision

Ship a **standalone Windows executable** built with **PyInstaller** (stdlib-friendly, works with Tkinter + lazy matplotlib).

| Concern | Rule |
|---------|------|
| User data | Stays in `~/.personal_dev_tracker/` (NOT inside the EXE folder) — survives app updates |
| Bundled assets | Seed JSON, icons — packed inside EXE via PyInstaller `datas` |
| Runtime | Python interpreter bundled; user does not install Python |
| Distribution | `dist/PersonalDevelopmentTracker.exe` (one-file) or `dist/PersonalDevelopmentTracker/` (one-folder, faster cold start) |
| Build tool | PyInstaller only (dev dependency; not required at runtime) |

## Consequences

- Add `paths.py` for frozen vs dev path resolution
- `progression/seed_loader.py` reads seeds from bundle when frozen
- Build spec checked into repo; CI/manual `python -m PyInstaller` produces artifact
- macOS `.app` / Linux binary are future specs — Windows EXE first

## Agent Rules

- MUST NOT require cloud or network for EXE to run
- MUST NOT store user journals/progress inside the EXE directory by default
- MUST use `paths.bundle_root()` for read-only bundled files
- MUST use existing `profiles` / `storage` paths for user data
- PyInstaller is a **build-time** dependency only — not in runtime `requirements.txt`

## Non-Goals

- Microsoft Store / auto-update server
- Code signing (optional future spec)
- Installer wizard (Inno Setup) — optional later; portable EXE is enough for v1
