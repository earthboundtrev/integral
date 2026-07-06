# ADR-008: Local Multi-Profile (Accounts)

**Status:** Accepted  
**Date:** 2026-06-27

## Context

Users need separate progression and daily logs for multiple people on the same machine (e.g. family members). This is not cloud multi-tenant auth — it is local profile switching.

## Decision

Support **multiple local profiles** under `~/.personal_dev_tracker/profiles/<profile_id>/`.

Each profile has isolated:
- `data.json` (daily life-domain entries)
- `fitness.db` (exercise graph + user progress)

App config at `~/.personal_dev_tracker/config.json` stores active profile and profile list.

## Agent Rules

- MUST NOT add cloud accounts, passwords, or sync in this ADR
- All storage paths MUST resolve through active profile directory
- Switching profile MUST reload in-memory data without mixing entries
- Legacy single-file `data.json` at app root MUST migrate to `profiles/default/`
