from ui_scroll import (
    _descendant_ids,
    _scroll_amount,
    coalesce_scroll_command,
    make_horizontal_scroll_row,
)


class _WheelEvent:
    def __init__(self, *, delta=0, num=None):
        self.delta = delta
        self.num = num


def test_scroll_amount_windows_delta():
    assert _scroll_amount(_WheelEvent(delta=120)) == -1
    assert _scroll_amount(_WheelEvent(delta=-120)) == 1


def test_scroll_amount_windows_large_delta():
    assert _scroll_amount(_WheelEvent(delta=240)) == -2
    assert _scroll_amount(_WheelEvent(delta=-360)) == 3


def test_scroll_amount_linux_buttons():
    assert _scroll_amount(_WheelEvent(delta=0, num=4)) == -1
    assert _scroll_amount(_WheelEvent(delta=0, num=5)) == 1


class _FakeScheduler:
    """Minimal stand-in for Tk after/winfo_exists used by coalesce_scroll_command."""

    def __init__(self):
        self.pending: list = []
        self.alive = True

    def winfo_exists(self):
        return self.alive

    def after(self, _ms, callback):
        self.pending.append(callback)
        return id(callback)

    def after_cancel(self, _after_id):
        self.pending.clear()

    def run_pending(self):
        while self.pending:
            cb = self.pending.pop(0)
            cb()


def test_coalesce_scroll_batches_units():
    """Rapid scroll units flush once with the summed amount (#66)."""
    calls: list[tuple] = []

    def scroll_command(*args):
        calls.append(args)

    sched = _FakeScheduler()
    wrapped = coalesce_scroll_command(scroll_command, sched, interval_ms=50)
    wrapped("scroll", 1, "units")
    wrapped("scroll", 1, "units")
    wrapped("scroll", 2, "units")
    assert calls == []
    assert len(sched.pending) == 1
    sched.run_pending()
    assert calls == [("scroll", 4, "units")]


def test_coalesce_scroll_moveto_flushes_pending():
    calls: list[tuple] = []

    def scroll_command(*args):
        calls.append(args)

    sched = _FakeScheduler()
    wrapped = coalesce_scroll_command(scroll_command, sched, interval_ms=50)
    wrapped("scroll", 3, "units")
    wrapped("moveto", 0.5)
    assert ("scroll", 3, "units") in calls
    assert ("moveto", 0.5) in calls


def test_coalesce_scroll_cancel_drops_pending():
    calls: list[tuple] = []

    def scroll_command(*args):
        calls.append(args)

    sched = _FakeScheduler()
    wrapped = coalesce_scroll_command(scroll_command, sched, interval_ms=50)
    wrapped("scroll", 5, "units")
    wrapped.cancel()
    sched.run_pending()
    assert calls == []


def test_descendant_ids_stable_without_child_changes():
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.withdraw()
    try:
        frame = ttk.Frame(root)
        ttk.Button(frame, text="A").pack()
        ttk.Button(frame, text="B").pack()
        root.update_idletasks()
        first = _descendant_ids(frame)
        second = _descendant_ids(frame)
        assert first == second
        assert len(first) == 3
    finally:
        root.destroy()


def test_horizontal_scroll_xview_does_not_toggle_scrollbar_pack():
    """Scrolling must not pack/unpack the scrollbar each notch (#48)."""
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.withdraw()
    try:
        host_parent = ttk.Frame(root, width=280)
        host_parent.pack(fill=tk.X)
        host_parent.pack_propagate(False)

        host, inner, canvas = make_horizontal_scroll_row(host_parent)
        host.pack(fill=tk.X)
        for label in [f"Btn{i}" for i in range(16)]:
            ttk.Button(inner, text=label).pack(side=tk.LEFT, padx=6)

        root.update_idletasks()
        root.update()
        for _ in range(5):
            root.update_idletasks()

        viewport = canvas.master
        bars_before = [w for w in viewport.winfo_children() if isinstance(w, ttk.Scrollbar)]
        assert bars_before, "expected overflow scrollbar to be managed"

        for frac in (0.2, 0.4, 0.6, 0.8, 1.0):
            canvas.xview_moveto(frac)
            root.update_idletasks()
            bars = [w for w in viewport.winfo_children() if isinstance(w, ttk.Scrollbar)]
            assert len(bars) == len(bars_before)
    finally:
        root.destroy()


def test_horizontal_scroll_row_preserves_overflow_for_trailing_actions():
    """Footer strip must keep natural content width so Export stays reachable (#44)."""
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.withdraw()
    try:
        host_parent = ttk.Frame(root, width=280)
        host_parent.pack(fill=tk.X)
        host_parent.pack_propagate(False)

        host, inner, canvas = make_horizontal_scroll_row(host_parent, overflow_hint="Scroll for more →")
        host.pack(fill=tk.X)

        labels = [
            "Refresh",
            "Guidance",
            "Weekly Summary",
            "AI Insight",
            "Full History",
            "Search Notes",
            "Graphs & Progress",
            "Journal",
            "Writing Projects",
            "Deep Work",
            "Quick Capture",
            "Plan Tomorrow",
            "Log Exercise",
            "Fitness Hub",
            "Milestones",
            "Export",
            "Backup",
            "Edit Categories",
            "Data & Security",
        ]
        for label in labels:
            ttk.Button(inner, text=label).pack(side=tk.LEFT, padx=6)

        root.update_idletasks()
        root.update()
        for _ in range(5):
            root.update_idletasks()

        bbox = canvas.bbox("all")
        assert bbox is not None
        content_width = bbox[2] - bbox[0]
        visible_width = max(canvas.winfo_width(), 1)
        assert content_width > visible_width + 2, (
            f"expected horizontal overflow (content={content_width}, visible={visible_width})"
        )

        left_before, right_before = canvas.xview()
        assert float(right_before) < 0.99

        canvas.xview_moveto(1.0)
        root.update_idletasks()
        left_after, right_after = canvas.xview()
        assert float(right_after) >= 0.99
        assert float(left_after) > float(left_before)
    finally:
        root.destroy()
