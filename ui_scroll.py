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


def _descendant_ids(widget: tk.Misc) -> tuple[int, ...]:
    ids: list[int] = [id(widget)]
    for child in widget.winfo_children():
        ids.extend(_descendant_ids(child))
    return tuple(ids)


def bind_mousewheel(
    container: tk.Misc,
    scroll_command: Callable[..., object],
    *,
    horizontal: bool = False,
    watch_configure: tk.Misc | None = None,
) -> Callable[[], None]:
    """
    Bind wheel scrolling to a container and its descendants only.

    Avoids bind_all/unbind_all, which causes competing handlers, text overlap
    glitches, and crashes when multiple scroll areas exist in one window.

    Pass horizontal=True when scroll_command is an xview handler; Shift+wheel
    is bound as well for trackpads that emit that sequence.

    If watch_configure is set, rebinds only when the descendant widget set
    changes (not on every geometry Configure). Returns a callable that forces
    a binding refresh after children are packed.
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
        widget.bind(
            "<Destroy>",
            lambda event, wid=widget_id: _wheel_bound_widgets.discard(wid),
            add="+",
        )

    def bind_tree(widget: tk.Misc) -> None:
        bind_widget(widget)
        for child in widget.winfo_children():
            bind_tree(child)

    bound_sig: dict[str, tuple[int, ...] | None] = {"value": None}
    pending = {"active": False}

    def refresh_bindings(_event=None) -> None:
        if not container.winfo_exists():
            return
        sig = _descendant_ids(container)
        if sig == bound_sig["value"]:
            return
        bound_sig["value"] = sig
        bind_tree(container)

    def schedule_refresh(_event=None) -> None:
        if pending["active"]:
            return
        pending["active"] = True

        def run() -> None:
            pending["active"] = False
            refresh_bindings()

        container.after_idle(run)

    refresh_bindings()
    container.bind("<Map>", schedule_refresh, add="+")
    if watch_configure is not None:
        watch_configure.bind("<Configure>", schedule_refresh, add="+")
    return refresh_bindings


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

    The embedded window keeps its *natural* content width so trailing actions
    (e.g. Export) stay reachable via scrollbar / mousewheel. Only the height is
    matched to the canvas — forcing width to the viewport (as vertical scroll
    areas do) collapses overflow and hides later buttons.

    Geometry sync and wheel rebinds are coalesced / child-set gated so scrolling
    does not thrash layout (#48).
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

    state: dict = {
        "geom": None,
        "scrollbar_shown": False,
        "hint_text": "",
        "layout_pending": False,
    }

    def _set_overflow_chrome(show_bar: bool, hint_text: str) -> None:
        if show_bar != state["scrollbar_shown"]:
            state["scrollbar_shown"] = show_bar
            if show_bar:
                scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            else:
                scrollbar.pack_forget()
        if hint_text != state["hint_text"]:
            state["hint_text"] = hint_text
            hint.config(text=hint_text)

    def _apply_geometry() -> None:
        # One idle pass is enough; avoid re-entrant update_idletasks on xscroll.
        inner.update_idletasks()
        visible_w = max(canvas.winfo_width(), 1)
        visible_h = max(canvas.winfo_height(), height)
        content_w = max(inner.winfo_reqwidth(), 1)
        target_w = max(content_w, visible_w) if content_w <= visible_w else content_w
        geom = (target_w, visible_h, content_w, visible_w)
        if geom != state["geom"]:
            state["geom"] = geom
            canvas.itemconfigure(window_id, width=target_w, height=visible_h)
            bbox = canvas.bbox("all")
            if bbox:
                canvas.configure(scrollregion=bbox)

        bbox = canvas.bbox("all")
        if not bbox:
            _set_overflow_chrome(False, "")
            return
        content_width = bbox[2] - bbox[0]
        overflow = content_width > visible_w + 2
        if overflow:
            _left, right = canvas.xview()
            _set_overflow_chrome(True, overflow_hint if right < 0.99 else "")
        else:
            _set_overflow_chrome(False, "")

    def on_xscroll(first, last) -> None:
        scrollbar.set(first, last)
        # Hint only — never geometry sync or pack/unpack on the scroll path.
        if not state["scrollbar_shown"]:
            if state["hint_text"]:
                state["hint_text"] = ""
                hint.config(text="")
            return
        right = float(last)
        desired = overflow_hint if right < 0.99 else ""
        if desired != state["hint_text"]:
            state["hint_text"] = desired
            hint.config(text=desired)

    refresh_wheel = bind_mousewheel(
        viewport,
        canvas.xview,
        horizontal=True,
        watch_configure=inner,
    )

    def schedule_layout(_event=None) -> None:
        if state["layout_pending"]:
            return
        state["layout_pending"] = True

        def run() -> None:
            state["layout_pending"] = False
            if not canvas.winfo_exists():
                return
            _apply_geometry()
            refresh_wheel()

        canvas.after_idle(run)

    inner.bind("<Configure>", schedule_layout)
    canvas.bind("<Configure>", schedule_layout)
    canvas.configure(xscrollcommand=on_xscroll)

    canvas.pack(side=tk.TOP, fill=tk.X, expand=True)
    schedule_layout()
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
    state = {"hint": "", "pending": False}

    def update_hint() -> None:
        bbox = canvas.bbox("all")
        if not bbox:
            if state["hint"]:
                state["hint"] = ""
                hint.config(text="")
            return
        content_height = bbox[3] - bbox[1]
        visible_height = max(canvas.winfo_height(), 1)
        desired = ""
        if content_height > visible_height + 2:
            _top, bottom = canvas.yview()
            desired = overflow_hint if bottom < 0.99 else ""
        if desired != state["hint"]:
            state["hint"] = desired
            hint.config(text=desired)

    def schedule_hint(_event=None) -> None:
        if state["pending"]:
            return
        state["pending"] = True

        def run() -> None:
            state["pending"] = False
            if canvas.winfo_exists():
                update_hint()

        canvas.after_idle(run)

    def on_yscroll(first, last):
        if scrollbar is not None:
            scrollbar.set(first, last)
        update_hint()

    canvas.configure(yscrollcommand=on_yscroll)
    inner.bind("<Configure>", schedule_hint, add="+")
    canvas.bind("<Configure>", schedule_hint, add="+")
    schedule_hint()
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

    pending = {"active": False}

    def _on_inner_configure(_event):
        if pending["active"]:
            return
        pending["active"] = True

        def run() -> None:
            pending["active"] = False
            if canvas.winfo_exists():
                refresh_scroll_region(canvas, inner)

        canvas.after_idle(run)

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
