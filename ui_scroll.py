"""Shared scrolling helpers for Tkinter windows."""

import tkinter as tk


def _scroll_amount(event) -> int:
    if event.num == 5 or event.delta < 0:
        return 1
    if event.num == 4 or event.delta > 0:
        return -1
    return 0


def bind_mousewheel(widget, scroll_command, *, horizontal: bool = False) -> None:
    """Bind mouse wheel / trackpad scroll to a yview or xview command."""

    def on_mousewheel(event):
        amount = _scroll_amount(event)
        if amount:
            scroll_command("scroll", amount, "units")

    def on_enter(_event):
        widget.bind_all("<MouseWheel>", on_mousewheel)
        widget.bind_all("<Button-4>", on_mousewheel)
        widget.bind_all("<Button-5>", on_mousewheel)

    def on_leave(_event):
        widget.unbind_all("<MouseWheel>")
        widget.unbind_all("<Button-4>")
        widget.unbind_all("<Button-5>")

    widget.bind("<Enter>", on_enter, add="+")
    widget.bind("<Leave>", on_leave, add="+")
    if horizontal:
        widget.bind("<Shift-MouseWheel>", on_mousewheel, add="+")


def configure_treeview_scroll(tree) -> None:
    """Ensure a Treeview scrolls with its scrollbar and mouse wheel."""
    bind_mousewheel(tree, tree.yview)


def make_scrollable_frame(parent, *, width=None, height=None):
    """
    Return (outer_frame, inner_frame, canvas).
    Pack/grid widgets into inner_frame; outer_frame fills the parent.
    """
    outer = tk.Frame(parent)
    canvas = tk.Canvas(outer, highlightthickness=0, width=width, height=height)
    scrollbar = tk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
    inner = tk.Frame(canvas)

    inner.bind(
        "<Configure>",
        lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
    )
    window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    def _resize_inner(event):
        canvas.itemconfigure(window_id, width=event.width)

    canvas.bind("<Configure>", _resize_inner)
    bind_mousewheel(canvas, canvas.yview)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    return outer, inner, canvas
