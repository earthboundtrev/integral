"""Shared scrolling helpers for Tkinter windows and dialogs."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

_dialog_scroll_refs: dict[int, int] = {}
_wheel_bound_widgets: set[int] = set()

# Paint at ~120Hz max so full-speed input still lands as one place move (#66/#68).
_SCROLL_FLUSH_MS = 8
_WHEEL_PIXELS = 28


def _scroll_amount(event) -> int:
    num = getattr(event, "num", None)
    delta = getattr(event, "delta", 0) or 0
    if num == 5:
        return 1
    if num == 4:
        return -1
    if not delta:
        return 0
    steps = int(delta / 120)
    if steps == 0:
        steps = 1 if delta > 0 else -1
    # Positive Windows delta → scroll up → negative Tk units.
    return -steps


def _descendant_ids(widget: tk.Misc) -> tuple[int, ...]:
    ids: list[int] = [id(widget)]
    for child in widget.winfo_children():
        ids.extend(_descendant_ids(child))
    return tuple(ids)


def coalesce_scroll_command(
    scroll_command: Callable[..., object],
    schedule_widget: tk.Misc,
    *,
    interval_ms: int = _SCROLL_FLUSH_MS,
) -> Callable[..., object]:
    """
    Batch rapid scroll/moveto calls into one flush per interval.

    Relative ``scroll`` units accumulate; absolute ``moveto`` keeps only the
    latest fraction (critical for fast scrollbar drags — #68).
    """
    state: dict = {"amount": 0, "moveto": None, "after_id": None}

    def flush() -> None:
        state["after_id"] = None
        moveto = state["moveto"]
        amount = state["amount"]
        state["moveto"] = None
        state["amount"] = 0
        try:
            if not schedule_widget.winfo_exists():
                return
            if moveto is not None:
                scroll_command("moveto", moveto)
            elif amount:
                scroll_command("scroll", amount, "units")
        except tk.TclError:
            return

    def cancel() -> None:
        """Drop pending deltas without applying (e.g. before external moveto)."""
        after_id = state["after_id"]
        state["after_id"] = None
        state["amount"] = 0
        state["moveto"] = None
        if after_id is not None:
            try:
                schedule_widget.after_cancel(after_id)
            except (tk.TclError, ValueError):
                pass

    def _schedule() -> None:
        if state["after_id"] is not None:
            return
        try:
            state["after_id"] = schedule_widget.after(interval_ms, flush)
        except tk.TclError:
            flush()

    def wrapped(*args):
        if not args:
            return scroll_command(*args)

        cmd = args[0]
        if cmd == "scroll":
            try:
                amount = int(args[1])
            except (TypeError, ValueError, IndexError):
                return scroll_command(*args)
            # Relative scroll after a pending moveto: apply moveto first conceptually
            # by dropping relative into amount only when no moveto pending.
            if state["moveto"] is not None:
                # Convert to a nudge after the absolute position on flush — just
                # accumulate units; flush prefers moveto. Clear amount if moveto wins.
                state["amount"] += amount
            else:
                state["amount"] += amount
            _schedule()
            return None

        if cmd == "moveto":
            try:
                state["moveto"] = float(args[1])
            except (TypeError, ValueError, IndexError):
                return scroll_command(*args)
            state["amount"] = 0
            _schedule()
            return None

        # Other commands (e.g. scroll pages already handled): flush then pass through.
        cancel()
        return scroll_command(*args)

    wrapped.flush = flush  # type: ignore[attr-defined]
    wrapped.cancel = cancel  # type: ignore[attr-defined]
    wrapped._coalesce_state = state  # type: ignore[attr-defined]
    return wrapped


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
    a binding refresh after children are packed. The returned callable also
    exposes ``.coalesced_scroll`` — use that for scrollbar ``command=`` so a
    pending wheel flush cannot jump after a drag (#66).

    Wheel motion is coalesced so fast flicks do not tear embedded buttons (#66/#68).
    """
    coalesced = coalesce_scroll_command(scroll_command, container)

    def on_mousewheel(event):
        amount = _scroll_amount(event)
        if amount:
            coalesced("scroll", amount, "units")
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
    refresh_bindings.coalesced_scroll = coalesced  # type: ignore[attr-defined]
    return refresh_bindings


def activate_dialog_scrolling(toplevel: tk.Misc, canvas: tk.Misc) -> None:
    """Bind wheel scrolling to one dialog scroll view without global bind_all."""
    key = id(toplevel)
    _dialog_scroll_refs[key] = _dialog_scroll_refs.get(key, 0) + 1
    outer = getattr(canvas, "master", canvas)

    def on_destroy(event):
        if event.widget is not toplevel:
            return
        remaining = _dialog_scroll_refs.get(key, 1) - 1
        if remaining <= 0:
            _dialog_scroll_refs.pop(key, None)
        else:
            _dialog_scroll_refs[key] = remaining

    if _dialog_scroll_refs[key] == 1:
        yview = getattr(canvas, "yview", None)
        if yview is not None:
            bind_mousewheel(outer, yview, watch_configure=canvas)
    toplevel.bind("<Destroy>", on_destroy, add="+")


def refresh_scroll_region(view: tk.Misc, inner: tk.Misc) -> None:
    refresh = getattr(view, "refresh_metrics", None)
    if callable(refresh):
        refresh()
        return
    inner.update_idletasks()
    view.update_idletasks()
    bbox = view.bbox("all")
    if bbox:
        view.configure(scrollregion=bbox)


def configure_treeview_scroll(tree) -> None:
    """Ensure a Treeview scrolls with its scrollbar and mouse wheel."""
    bind_mousewheel(tree, tree.yview)


class PlaceScrollView:
    """
    Canvas-compatible scroll facade: one clipped viewport + place()'d inner frame.

    Moving a single frame (instead of canvas.create_window + xview/yview) lets
    Windows keep ttk buttons coherent at full scrollbar / wheel speed (#68).
    """

    def __init__(
        self,
        viewport: tk.Frame,
        inner: tk.Misc,
        *,
        horizontal: bool,
        unit_pixels: int = _WHEEL_PIXELS,
    ) -> None:
        self._viewport = viewport
        self._inner = inner
        self._horizontal = horizontal
        self._unit_pixels = unit_pixels
        self._offset = 0
        self._content = 1
        self._visible = 1
        self._scrollcommand: Callable[..., object] | None = None
        self._layout_pending = False
        if horizontal:
            inner.place(x=0, y=0, relheight=1)
        else:
            inner.place(x=0, y=0, relwidth=1)

    # --- tk widget passthrough used by callers / style_canvas ---
    def configure(self, cnf=None, **kw):
        if cnf and isinstance(cnf, dict):
            kw = {**cnf, **kw}
        # scrollregion is meaningful only for Canvas; ignore on place view.
        kw.pop("scrollregion", None)
        kw.pop("xscrollcommand", None)
        kw.pop("yscrollcommand", None)
        if "bg" in kw or "background" in kw or "highlightthickness" in kw:
            return self._viewport.configure(**{k: v for k, v in kw.items() if k in ("bg", "background", "highlightthickness")})
        return None

    config = configure

    def cget(self, key):
        if key in ("bg", "background", "highlightthickness"):
            return self._viewport.cget(key)
        if key == "scrollregion":
            if self._horizontal:
                return f"0 0 {self._content} {self._visible}"
            return f"0 0 {self._visible} {self._content}"
        raise tk.TclError(f"unknown option '{key}'")

    def winfo_exists(self):
        return self._viewport.winfo_exists()

    def winfo_width(self):
        return self._viewport.winfo_width()

    def winfo_height(self):
        return self._viewport.winfo_height()

    def after(self, *args, **kwargs):
        return self._viewport.after(*args, **kwargs)

    def after_cancel(self, *args, **kwargs):
        return self._viewport.after_cancel(*args, **kwargs)

    def after_idle(self, *args, **kwargs):
        return self._viewport.after_idle(*args, **kwargs)

    def bind(self, *args, **kwargs):
        return self._viewport.bind(*args, **kwargs)

    def bbox(self, _what="all"):
        if self._horizontal:
            return (0, 0, max(self._content, self._visible), max(self._visible, 1))
        return (0, 0, max(self._visible, 1), max(self._content, self._visible))

    @property
    def master(self):
        return self._viewport.master

    def refresh_metrics(self) -> None:
        if not self._viewport.winfo_exists():
            return
        self._inner.update_idletasks()
        if self._horizontal:
            self._visible = max(self._viewport.winfo_width(), 1)
            self._content = max(self._inner.winfo_reqwidth(), 1)
            # Keep inner at least viewport-tall for hit targets.
            self._inner.place_configure(height=max(self._viewport.winfo_height(), 1))
        else:
            self._visible = max(self._viewport.winfo_height(), 1)
            self._content = max(self._inner.winfo_reqheight(), 1)
            self._inner.place_configure(width=max(self._viewport.winfo_width(), 1))
        self._apply_offset(self._offset, force=True)

    def schedule_layout(self, _event=None) -> None:
        if self._layout_pending:
            return
        self._layout_pending = True

        def run() -> None:
            self._layout_pending = False
            self.refresh_metrics()

        try:
            self._viewport.after_idle(run)
        except tk.TclError:
            self._layout_pending = False

    def _max_offset(self) -> int:
        return max(0, self._content - self._visible)

    def _fractions(self) -> tuple[str, str]:
        max_off = self._max_offset()
        if max_off <= 0 or self._content <= 0:
            return ("0.0", "1.0")
        first = self._offset / self._content
        last = (self._offset + self._visible) / self._content
        return (f"{first:.6f}", f"{min(last, 1.0):.6f}")

    def _emit(self) -> None:
        if self._scrollcommand is None:
            return
        first, last = self._fractions()
        try:
            self._scrollcommand(first, last)
        except tk.TclError:
            pass

    def _apply_offset(self, offset: int, *, force: bool = False) -> None:
        offset = max(0, min(int(offset), self._max_offset()))
        if not force and offset == self._offset:
            self._emit()
            return
        self._offset = offset
        try:
            if self._horizontal:
                self._inner.place_configure(x=-offset)
            else:
                self._inner.place_configure(y=-offset)
        except tk.TclError:
            return
        self._emit()

    def set_scrollcommand(self, command: Callable[..., object] | None) -> None:
        self._scrollcommand = command
        self._emit()

    def xview(self, *args):
        if not self._horizontal:
            return self._fractions() if not args else None
        if not args:
            return self._fractions()
        return self._view_cmd(*args)

    def yview(self, *args):
        if self._horizontal:
            return self._fractions() if not args else None
        if not args:
            return self._fractions()
        return self._view_cmd(*args)

    def xview_moveto(self, fraction) -> None:
        if self._horizontal:
            self._view_cmd("moveto", fraction)

    def yview_moveto(self, fraction) -> None:
        if not self._horizontal:
            self._view_cmd("moveto", fraction)

    def _view_cmd(self, *args):
        if not args:
            return self._fractions()
        cmd = args[0]
        if cmd == "moveto":
            try:
                frac = float(args[1])
            except (TypeError, ValueError, IndexError):
                return None
            self._apply_offset(int(frac * self._content))
            return None
        if cmd == "scroll":
            try:
                amount = int(args[1])
            except (TypeError, ValueError, IndexError):
                return None
            unit = args[2] if len(args) > 2 else "units"
            if unit == "pages":
                delta = amount * max(self._visible - self._unit_pixels, self._unit_pixels)
            else:
                delta = amount * self._unit_pixels
            self._apply_offset(self._offset + delta)
            return None
        return None


def make_horizontal_scroll_row(parent, *, height: int = 44, overflow_hint: str = "Scroll for more →"):
    """
    Horizontal strip for toolbars that overflow on narrow windows.

    Returns (host, inner, view). Pack buttons into inner with side=tk.LEFT.

    Uses a clipped place() viewport (not canvas.create_window) so full-speed
    scrollbar / wheel motion does not ghost ttk buttons (#68).
    """
    host = ttk.Frame(parent)
    hint = ttk.Label(host, text="", style="Muted.TLabel")
    hint.pack(side=tk.RIGHT, padx=(6, 0))

    strip = ttk.Frame(host)
    strip.pack(side=tk.LEFT, fill=tk.X, expand=True)

    viewport = tk.Frame(strip, height=height, highlightthickness=0, bd=0)
    viewport.pack(side=tk.TOP, fill=tk.X, expand=True)
    viewport.pack_propagate(False)

    scrollbar = ttk.Scrollbar(strip, orient=tk.HORIZONTAL)
    inner = ttk.Frame(viewport)
    view = PlaceScrollView(viewport, inner, horizontal=True)

    state: dict = {
        "scrollbar_shown": False,
        "hint_text": "",
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

    def on_xscroll(first, last) -> None:
        scrollbar.set(first, last)
        state["scroll_last"] = last
        if state.get("hint_after_id") is not None:
            return

        def apply_hint() -> None:
            state["hint_after_id"] = None
            if not viewport.winfo_exists():
                return
            view.refresh_metrics()
            overflow = view._content > view._visible + 2
            if not overflow:
                _set_overflow_chrome(False, "")
                return
            try:
                right = float(state.get("scroll_last", last))
            except (TypeError, ValueError):
                _left, right = view.xview()
                right = float(right)
            _set_overflow_chrome(True, overflow_hint if right < 0.99 else "")

        try:
            state["hint_after_id"] = viewport.after(_SCROLL_FLUSH_MS, apply_hint)
        except tk.TclError:
            apply_hint()

    view.set_scrollcommand(on_xscroll)

    refresh_wheel = bind_mousewheel(
        strip,
        view.xview,
        horizontal=True,
        watch_configure=inner,
    )
    scrollbar.configure(command=refresh_wheel.coalesced_scroll)

    def on_layout(_event=None) -> None:
        view.schedule_layout()

    inner.bind("<Configure>", on_layout)
    viewport.bind("<Configure>", on_layout)
    view.schedule_layout()
    return host, inner, view


def make_bounded_vertical_scroll(
    parent,
    *,
    max_height: int,
    overflow_hint: str = "↓ Scroll for more",
):
    """
    Vertical scroll area with a fixed max height and an overflow hint label.

    Returns (wrapper, inner, view).
    """
    wrapper = ttk.Frame(parent)
    hint = ttk.Label(wrapper, text="", style="Muted.TLabel")
    hint.pack(side=tk.BOTTOM, anchor="e", pady=(2, 0))

    outer, inner, view = make_scrollable_frame(wrapper, height=max_height)
    outer.pack(fill=tk.X, expand=False)

    scrollbar = next((w for w in outer.winfo_children() if isinstance(w, ttk.Scrollbar)), None)
    state = {"hint": "", "pending": False}

    def update_hint() -> None:
        view.refresh_metrics()
        content_height = view._content
        visible_height = view._visible
        desired = ""
        if content_height > visible_height + 2:
            _top, bottom = view.yview()
            desired = overflow_hint if float(bottom) < 0.99 else ""
        if desired != state["hint"]:
            state["hint"] = desired
            hint.config(text=desired)

    def schedule_hint(_event=None) -> None:
        if state["pending"]:
            return
        state["pending"] = True

        def run() -> None:
            state["pending"] = False
            if view.winfo_exists():
                update_hint()

        view.after_idle(run)

    def on_yscroll(first, last):
        if scrollbar is not None:
            scrollbar.set(first, last)
        state["scroll_last"] = last
        if state.get("hint_after_id") is not None:
            return

        def apply_hint() -> None:
            state["hint_after_id"] = None
            if view.winfo_exists():
                update_hint()

        try:
            state["hint_after_id"] = view.after(_SCROLL_FLUSH_MS, apply_hint)
        except tk.TclError:
            update_hint()

    view.set_scrollcommand(on_yscroll)
    inner.bind("<Configure>", schedule_hint, add="+")
    view.bind("<Configure>", schedule_hint, add="+")
    schedule_hint()
    return wrapper, inner, view


def make_scrollable_frame(parent, *, width=None, height=None):
    """
    Return (outer_frame, inner_frame, view).

    Pack/grid widgets into inner_frame; outer_frame fills the parent.
    Place-based clipped scrolling keeps ttk chrome coherent at full speed (#68).
    """
    outer = tk.Frame(parent)
    viewport = tk.Frame(outer, highlightthickness=0, bd=0, width=width, height=height)
    scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL)
    inner = tk.Frame(viewport)
    view = PlaceScrollView(viewport, inner, horizontal=False)

    if height is not None:
        viewport.configure(height=height)
        viewport.pack_propagate(False)

    viewport.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    view.set_scrollcommand(scrollbar.set)
    refresh_wheel = bind_mousewheel(outer, view.yview, watch_configure=inner)
    scrollbar.configure(command=refresh_wheel.coalesced_scroll)

    inner.bind("<Configure>", view.schedule_layout)
    viewport.bind("<Configure>", view.schedule_layout)
    view.schedule_layout()
    return outer, inner, view


def create_dialog_shell(
    parent,
    *,
    title: str,
    geometry: str,
    minsize: tuple[int, int] | None = None,
    bg: str | None = None,
    transient: bool = True,
    grab: bool = False,
) -> tuple[tk.Toplevel, ttk.Frame, ttk.Frame, PlaceScrollView, Callable[[], None]]:
    """
    Standard scrollable dialog layout with a pinned footer.

    Returns (dialog, inner, footer, view, refresh_scroll).
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

    outer, inner, view = make_scrollable_frame(scroll_host)
    outer.pack(fill=tk.BOTH, expand=True)

    def refresh_scroll() -> None:
        refresh_scroll_region(view, inner)

    return dialog, inner, footer, view, refresh_scroll
