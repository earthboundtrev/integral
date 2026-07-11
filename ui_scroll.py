"""Shared scrolling helpers for Tkinter windows and dialogs."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

_dialog_scroll_refs: dict[int, int] = {}
_wheel_bound_widgets: set[int] = set()


def _scroll_amount(event) -> int:
    if event.num == 5 or event.delta < 0:
        return 1
    if event.num == 4 or event.delta > 0:
        return -1
    return 0


def bind_mousewheel(
    container: tk.Misc,
    scroll_command: Callable[..., object],
    *,
    horizontal: bool = False,
    watch_configure: tk.Misc | None = None,
) -> None:
    """
    Bind wheel scrolling to a container and its descendants only.

    Avoids bind_all/unbind_all, which causes competing handlers, text overlap
    glitches, and crashes when multiple scroll areas exist in one window.

    Pass horizontal=True when scroll_command is an xview handler; Shift+wheel
    is bound as well for trackpads that emit that sequence.
    """

    def on_mousewheel(event):
        amount = _scroll_amount(event)
        if amount:
            scroll_command("scroll", amount, "units")
        return "break"

    def bind_widget(widget: tk.Misc) -> None:
        widget_id = id(widget)
        if widget_id in _wheel_bound_widgets:
            return
        _wheel_bound_widgets.add(widget_id)
        widget.bind("<MouseWheel>", on_mousewheel, add="+")
        widget.bind("<Button-4>", on_mousewheel, add="+")
        widget.bind("<Button-5>", on_mousewheel, add="+")
        if horizontal:
            widget.bind("<Shift-MouseWheel>", on_mousewheel, add="+")
        widget.bind("<Destroy>", lambda event, wid=widget_id: _wheel_bound_widgets.discard(wid), add="+")

    def bind_tree(widget: tk.Misc) -> None:
        bind_widget(widget)
        for child in widget.winfo_children():
            bind_tree(child)

    def refresh_bindings(_event=None) -> None:
        if container.winfo_exists():
            bind_tree(container)

    refresh_bindings()
    container.bind("<Map>", refresh_bindings, add="+")
    if watch_configure is not None:
        watch_configure.bind(
            "<Configure>",
            lambda _event: container.after_idle(refresh_bindings),
            add="+",
        )


def activate_dialog_scrolling(toplevel: tk.Misc, canvas: tk.Canvas) -> None:
    """Bind wheel scrolling to one dialog canvas without global bind_all."""
    key = id(toplevel)
    _dialog_scroll_refs[key] = _dialog_scroll_refs.get(key, 0) + 1
    outer = canvas.master

    def on_destroy(event):
        if event.widget is not toplevel:
            return
        remaining = _dialog_scroll_refs.get(key, 1) - 1
        if remaining <= 0:
            _dialog_scroll_refs.pop(key, None)
        else:
            _dialog_scroll_refs[key] = remaining

    if _dialog_scroll_refs[key] == 1:
        bind_mousewheel(outer, canvas.yview, watch_configure=canvas)
    toplevel.bind("<Destroy>", on_destroy, add="+")


def refresh_scroll_region(canvas: tk.Canvas, inner: tk.Misc) -> None:
    inner.update_idletasks()
    canvas.update_idletasks()
    bbox = canvas.bbox("all")
    if bbox:
        canvas.configure(scrollregion=bbox)


def configure_treeview_scroll(tree) -> None:
    """Ensure a Treeview scrolls with its scrollbar and mouse wheel."""
    bind_mousewheel(tree, tree.yview)


def make_horizontal_scroll_row(parent, *, height: int = 44, overflow_hint: str = "Scroll for more →"):
    """
    Horizontal strip for toolbars that overflow on narrow windows.

    Returns (host, inner, canvas). Pack buttons into inner with side=tk.LEFT.
    """
    host = ttk.Frame(parent)
    hint = ttk.Label(host, text="", style="Muted.TLabel")
    hint.pack(side=tk.RIGHT, padx=(6, 0))

    viewport = ttk.Frame(host)
    viewport.pack(side=tk.LEFT, fill=tk.X, expand=True)

    canvas = tk.Canvas(viewport, height=height, highlightthickness=0, bd=0)
    scrollbar = ttk.Scrollbar(viewport, orient=tk.HORIZONTAL, command=canvas.xview)
    inner = ttk.Frame(canvas)
    window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def update_hint() -> None:
        canvas.update_idletasks()
        bbox = canvas.bbox("all")
        if not bbox:
            hint.config(text="")
            scrollbar.pack_forget()
            return
        content_width = bbox[2] - bbox[0]
        visible_width = max(canvas.winfo_width(), 1)
        overflow = content_width > visible_width + 2
        if overflow:
            scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            _left, right = canvas.xview()
            hint.config(text=overflow_hint if right < 0.99 else "")
        else:
            scrollbar.pack_forget()
            hint.config(text="")

    def on_inner_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfigure(window_id, height=max(event.height, height))
        update_hint()

    def on_canvas_configure(event):
        canvas.itemconfigure(window_id, width=max(event.width, 1), height=event.height)
        update_hint()

    def on_xscroll(first, last):
        scrollbar.set(first, last)
        update_hint()

    inner.bind("<Configure>", on_inner_configure)
    canvas.bind("<Configure>", on_canvas_configure)
    canvas.configure(xscrollcommand=on_xscroll)

    def on_wheel(event):
        bbox = canvas.bbox("all")
        if not bbox or bbox[2] - bbox[0] <= canvas.winfo_width() + 2:
            return
        amount = _scroll_amount(event)
        if amount:
            canvas.xview_scroll(amount, "units")
        return "break"

    bind_mousewheel(viewport, canvas.xview, watch_configure=inner)
    for seq in ("<Shift-MouseWheel>",):
        canvas.bind(seq, on_wheel, add="+")
        inner.bind(seq, on_wheel, add="+")

    canvas.pack(side=tk.TOP, fill=tk.X, expand=True)
    update_hint()
    return host, inner, canvas


def make_bounded_vertical_scroll(
    parent,
    *,
    max_height: int,
    overflow_hint: str = "↓ Scroll for more",
):
    """
    Vertical scroll area with a fixed max height and an overflow hint label.

    Returns (wrapper, inner, canvas).
    """
    wrapper = ttk.Frame(parent)
    hint = ttk.Label(wrapper, text="", style="Muted.TLabel")
    hint.pack(side=tk.BOTTOM, anchor="e", pady=(2, 0))

    outer, inner, canvas = make_scrollable_frame(wrapper, height=max_height)
    outer.pack(fill=tk.X, expand=False)

    scrollbar = next((w for w in outer.winfo_children() if isinstance(w, ttk.Scrollbar)), None)

    def update_hint() -> None:
        canvas.update_idletasks()
        bbox = canvas.bbox("all")
        if not bbox:
            hint.config(text="")
            return
        content_height = bbox[3] - bbox[1]
        visible_height = max(canvas.winfo_height(), 1)
        if content_height > visible_height + 2:
            _top, bottom = canvas.yview()
            hint.config(text=overflow_hint if bottom < 0.99 else "")
        else:
            hint.config(text="")

    def on_yscroll(first, last):
        if scrollbar is not None:
            scrollbar.set(first, last)
        update_hint()

    canvas.configure(yscrollcommand=on_yscroll)
    inner.bind("<Configure>", lambda _event: update_hint(), add="+")
    canvas.bind("<Configure>", lambda _event: update_hint(), add="+")
    update_hint()
    return wrapper, inner, canvas


def make_scrollable_frame(parent, *, width=None, height=None):
    """
    Return (outer_frame, inner_frame, canvas).
    Pack/grid widgets into inner_frame; outer_frame fills the parent.
    """
    outer = tk.Frame(parent)
    canvas = tk.Canvas(outer, highlightthickness=0, width=width, height=height)
    scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
    inner = tk.Frame(canvas)

    def _on_inner_configure(_event):
        refresh_scroll_region(canvas, inner)

    inner.bind("<Configure>", _on_inner_configure)
    window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    def _resize_inner(event):
        canvas.itemconfigure(window_id, width=max(event.width, 1))

    canvas.bind("<Configure>", _resize_inner)
    bind_mousewheel(outer, canvas.yview, watch_configure=inner)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    return outer, inner, canvas


def create_dialog_shell(
    parent,
    *,
    title: str,
    geometry: str,
    minsize: tuple[int, int] | None = None,
    bg: str | None = None,
    transient: bool = True,
    grab: bool = False,
) -> tuple[tk.Toplevel, ttk.Frame, ttk.Frame, tk.Canvas, Callable[[], None]]:
    """
    Standard scrollable dialog layout with a pinned footer.

    Returns (dialog, inner, footer, canvas, refresh_scroll).
    Pack header into dialog before the scroll host, or into inner for scrolling headers.
    """
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.geometry(geometry)
    if minsize:
        dialog.minsize(*minsize)
    if bg:
        dialog.configure(bg=bg)
    if transient:
        dialog.transient(parent)
    if grab:
        dialog.grab_set()

    footer = ttk.Frame(dialog, padding=(12, 10))
    footer.pack(side=tk.BOTTOM, fill=tk.X)

    scroll_host = ttk.Frame(dialog)
    scroll_host.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    outer, inner, canvas = make_scrollable_frame(scroll_host)
    outer.pack(fill=tk.BOTH, expand=True)

    def refresh_scroll() -> None:
        refresh_scroll_region(canvas, inner)

    return dialog, inner, footer, canvas, refresh_scroll
