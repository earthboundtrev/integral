from mpl_tk import ensure_matplotlib


def test_ensure_matplotlib_loads_tkagg():
    ensure_matplotlib()
    import mpl_tk

    assert mpl_tk.Figure is not None
    assert mpl_tk.FigureCanvasTkAgg is not None
    assert mpl_tk.mdates is not None

    ensure_matplotlib()
    first_figure = mpl_tk.Figure
    ensure_matplotlib()
    assert mpl_tk.Figure is first_figure
