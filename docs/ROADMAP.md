# Integral — Roadmap

Known gaps vs funded competitors, tracked as intentional future work. Integral stays **local-first by default**; new capabilities should respect privacy and low-friction daily logging.

---

## Priority gaps (from competitive research)

| # | Gap today | Who does it better | Roadmap direction |
|---|-----------|-------------------|-------------------|
| 1 | **No cloud sync** | [Benji](https://www.benji.so/), AuraOne, HALO | Optional multi-device sync — user-controlled export/import first, then encrypted sync you opt into (no mandatory account) |
| 2 | **No AI layer** | [Orakemu](https://orakemu.com/), [Sinqly](https://sinqly.app/), [nopy](https://github.com/JoshuaHarris391/nopy) | Local, privacy-preserving AI — optional; your API key or local model; grounded in your logs and guidance playbooks |
| 3 | **No encryption at rest** | [Mini Diarium](https://github.com/fjrevoredo/mini-diarium), Line by Line | Encrypt `data.json` (or SQLite vault) with passphrase; unlock on app start |
| 4 | **Brand / polish behind funded SaaS** | Benji, Daylio, LifeWheel, HALO | App icon ✓, installer UX, onboarding, typography, empty states, release branding |

---

## Phase A — Foundation (shipped / in progress)

- [x] Multi-area daily logging (rating, checklist, metrics, notes)
- [x] GitHub-style activity grid + day explorer
- [x] Guidance engine (trends, gaps, burnout signals)
- [x] Fitness Hub (CC, Tibetan Rites, Explosive Calisthenics)
- [x] Windows `.exe` build
- [x] MIT license, README, app icon
- [x] Quarterly milestone tracker
- [x] Export to CSV / backup wizard
- [x] First-run onboarding

---

## Phase B — Security & trust

**Goal:** Match Mini Diarium’s security story without giving up structured life tracking.

- [x] Passphrase-protected vault
- [x] Encryption at rest for journal data (Fernet + PBKDF2)
- [ ] Clear security docs (what is encrypted, what never leaves the machine)
- [ ] Optional key file / recovery flow

---

## Phase C — Optional cloud sync

**Goal:** Benji-level multi-device convenience for users who want it — never required.

- [ ] One-click encrypted backup to user-chosen folder (Dropbox/iCloud/Google Drive via OS sync)
- [x] Manual merge / import from backup file
- [ ] Optional end-to-end encrypted sync (design TBD — no vendor lock-in)
- [ ] Conflict resolution for multi-device edits

*Principle:* Local remains the source of truth. Sync is opt-in.

---

## Phase D — AI layer (optional)

**Goal:** Orakemu/Sinqly-style insight without sending life data to Integral’s servers.

- [ ] Optional AI provider (OpenAI, Anthropic, local LM Studio — user’s key)
- [ ] Weekly digest generation from logs + guidance engine output
- [ ] “What’s blocking me?” prompt using recent notes (user-triggered only)
- [ ] Fitness progression commentary tied to official program tables
- [ ] Offline fallback — rule-based guidance remains when AI is off

*Principle:* AI reads only what the user explicitly enables; no telemetry.

---

## Phase E — Brand & product polish

**Goal:** Feel as intentional as funded SaaS on first launch.

- [x] App icon + exe embedding
- [ ] Windows installer (MSI/NSIS) with proper name and icon
- [x] First-run onboarding (pick categories, explain rating + Save)
- [ ] Empty states with clear CTAs
- [ ] Consistent typography and spacing pass
- [ ] Social preview / release banner for GitHub
- [ ] Screenshots for README and Releases page
- [ ] macOS and Linux builds (stretch)

---

## Not on the roadmap (for now)

| Item | Reason |
|------|--------|
| Mandatory cloud account | Conflicts with local-first promise |
| Social feeds / public timelines | Out of scope; privacy focus |
| Wearable auto-import | Large integration surface; revisit after core polish |
| Native mobile apps | Separate product effort; desktop + exe first |

---

## How to propose work

Open a GitHub issue with:

1. Which phase (B–E) it fits
2. Which competitor gap it addresses
3. Whether it must stay optional / local-first
