from ui_scroll import _scroll_amount, make_horizontal_scroll_row


class _WheelEvent:
    def __init__(self, *, delta=0, num=None):
        self.delta = delta
        self.num = num


def test_scroll_amount_windows_delta():
    assert _scroll_amount(_WheelEvent(delta=120)) == -1
    assert _scroll_amount(_WheelEvent(delta=-120)) == 1


def test_scroll_amount_linux_buttons():
    assert _scroll_amount(_WheelEvent(delta=0, num=4)) == -1
    assert _scroll_amount(_WheelEvent(delta=0, num=5)) == 1


def test_horizontal_scroll_row_preserves_overflow_for_trailing_actions():
    """Footer strip must keep natural content width so Export stays reachable (#44)."""
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.withdraw()
    try:
        # Narrow host so many buttons must overflow.
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

        bbox = canvas.bbox("all")
        assert bbox is not None
        content_width = bbox[2] - bbox[0]
        visible_width = max(canvas.winfo_width(), 1)
        assert content_width > visible_width + 2, (
            f"expected horizontal overflow (content={content_width}, visible={visible_width})"
        )

        # Trailing actions must be past the first viewport.
        left_before, right_before = canvas.xview()
        assert float(right_before) < 0.99

        canvas.xview_moveto(1.0)
        root.update_idletasks()
        left_after, right_after = canvas.xview()
        assert float(right_after) >= 0.99
        assert float(left_after) > float(left_before)
    finally:
        root.destroy()
