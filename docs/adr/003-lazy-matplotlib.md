# ADR-003: Lazy-Load Matplotlib

**Status:** Accepted  
**Date:** 2026-06-27

## Context

matplotlib import adds 1–3s to cold start if loaded at module level.

## Decision

matplotlib is the **only** allowed non-stdlib pip dependency for charting. It MUST be imported **only** inside graph-view functions (e.g. `build_graphs_tab`), never at module top level.

## Agent Rules

- MUST NOT `import matplotlib` at top of `tracker.py` or `app.py`
- MUST NOT add pandas, plotly, pyqtgraph, or other chart libs without new ADR
- SHOULD verify with `python -X importtime` that matplotlib absent from startup import chain
