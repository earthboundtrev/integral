# ADR-006: Progression DAG Model

**Status:** Accepted  
**Date:** 2026-06-27

## Context

Multiple fitness books (CC, OG, SS, EC, FTR) need unified cross-system progression.

## Decision

Model all exercises as **nodes** and relationships as **directed edges** in a **DAG** (for prerequisite chains). Mastery on a node unlocks downstream nodes per `unlock_condition` JSON.

Core entities: `Exercise`, `ProgressionEdge`, `UserExerciseProgress`, `MasteryCriteria`.

Full spec: `docs/PROGRESSION_MODEL.md`.

## Agent Rules

- Progression engine MUST be pure Python (no Tkinter imports)
- MUST validate no cycles on prerequisite edge insert
- Cross-book edges are encouraged (e.g. CC One-Arm Push-up → OG Planche Lean)
