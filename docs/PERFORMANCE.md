# Performance & Lightweight Architecture

## The Question: Python vs C++?

**Short answer: Stay in Python for now. Do not rewrite to C++ for performance.**

### Why Python Is Fine Here

| Concern | Reality |
|---------|---------|
| Startup time | Dominated by **matplotlib import** (~1–3s), not Python itself |
| Runtime speed | JSON read/write and Tkinter UI for personal-scale data (<10k entries) is instant |
| Dev velocity | Graph progression, AI coach hooks, and rapid iteration matter more than microseconds |
| Binary size | Irrelevant for a personal desktop tool |

C++ would shave milliseconds off data operations but costs weeks of rewrite for UI, charts, and graph logic — with no meaningful UX gain at personal data scale.

### When to Reconsider the Stack

Only if **all** of these become true:

- Cold start must be <500ms and lazy-loading cannot achieve it
- Dataset exceeds ~100k entries with complex graph queries on every frame
- You need native mobile or embedded deployment

Even then, prefer **Rust + Tauri** or a **compiled Python bundle (PyInstaller + lazy imports)** before a raw C++ GUI rewrite.

## Performance Budget

| Metric | Target |
|--------|--------|
| Cold start (dashboard visible) | < 2 seconds |
| Open log dialog | < 200ms |
| Save entry | < 100ms |
| Open Graphs tab (first time) | < 3 seconds (matplotlib load) |
| Graphs tab (subsequent) | < 500ms |
| Memory (idle) | < 150 MB |

## Mandatory Lightweight Practices

### Dependencies

- **Stdlib + Tkinter** for core UI and data — always.
- **matplotlib** — only dependency beyond stdlib; **lazy-import** when user opens Graphs tab.
- No pandas, numpy (unless matplotlib already pulls numpy — accept that, don't add more).
- No ORM, no web server, no Electron.

### Startup

```python
# ✅ Lazy-load heavy charting
def build_graphs_tab(self, parent):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    ...

# ❌ Never import matplotlib at module top level
import matplotlib.pyplot as plt  # adds seconds to every launch
```

### Data Access

- Load full JSON once at startup; keep in memory; write on save.
- For fitness graph (Phase 2): migrate to **SQLite** only when JSON parsing becomes measurable (>5MB file or slow loads).
- Precompute summary stats on save, not on every dashboard refresh.

### UI

- Destroy/recreate views sparingly; prefer updating widgets in place for hot paths.
- Limit graph redraws — cache Figure objects when data unchanged.
- Use `ttk` over raw `tk` where possible (native theming, less custom drawing).

### Future Chart Alternatives (If matplotlib Too Heavy)

1. **Tkinter Canvas** — line/bar charts for simple trends, zero extra deps
2. **pyqtgraph** — faster than matplotlib for live data (adds Qt dependency — avoid unless needed)
3. **Export-only** — generate PNG on demand instead of embedding (worse UX, fastest startup)

## Profiling Rule

Before any optimization or language rewrite:

1. Measure cold start with `python -X importtime tracker.py`
2. Measure save/load with realistic data file size
3. Fix the biggest bottleneck first (almost always: eager matplotlib import)
