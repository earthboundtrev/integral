"""Lazy Matplotlib TkAgg imports — defer numpy/mpl until charts are opened."""

from __future__ import annotations

Figure = None
FigureCanvasTkAgg = None
mdates = None


def ensure_matplotlib() -> None:
    """Load Matplotlib once, with TkAgg only."""
    global Figure, FigureCanvasTkAgg, mdates
    if Figure is not None:
        return
    import matplotlib

    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg as _canvas_cls
    from matplotlib.figure import Figure as _figure_cls
    import matplotlib.dates as _mdates

    Figure = _figure_cls
    FigureCanvasTkAgg = _canvas_cls
    mdates = _mdates
