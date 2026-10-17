"""One-screen daily reflection — all domains, single Save (#113)."""

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import TYPE_CHECKING, Callable

import ui_scroll
from entry_payload import (
    build_entry_payload,
    collect_touched_checklist,
    collect_touched_metrics,
    merge_entry_updates,
)
from inline_validation import make_inline_error_label, set_field_error
from insights.engine import category_insight
from theme import FONTS, style_text_widget

_UI_FONT = FONTS.get("body", ("Segoe UI", 10))
from todays_log import filter_todays_log_categories, pinned_domains
from ui_accent import wire_dialog_accent_keys

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker

REFLECT_WINDOW_KEY = "reflect"
DOMAIN_COUNT = 18  # stated in PR — default category count at ship time


def ordered_reflect_domains(category_names: list[str], settings: dict | None) -> list[str]:
    pins = pinned_domains(settings)
    return filter_todays_log_categories(
        category_names,
        query="",
        status="all",
        logged_names=set(),
        pinned_names=pins,
    )


class RatingRow(ttk.Frame):
    """One focus unit: 1–10 rating chips; unset until chosen."""

    def __init__(
        self,
        master: tk.Misc,
        theme: dict,
        *,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master, style="Surface.TFrame")
        self.theme = theme
        self._on_change = on_change
        self._rating: int | None = None
        self._cells: list[tk.Label] = []
        accent = theme.get("accent", "#2F7A7B")
        muted = theme.get("muted_fg", "#6B7280")
        selected_bg = theme.get("accent_soft", "#D1E7E7")
        self._colors = {
            "accent": accent,
            "muted": muted,
            "selected_bg": selected_bg,
            "fg": theme.get("fg", "#111"),
        }

        self.configure(takefocus=True)
        for n in range(1, 11):
            lbl = tk.Label(
                self,
                text=str(n),
                width=3,
                relief=tk.GROOVE,
                bd=1,
                font=_UI_FONT,
                bg=theme.get("surface", "#FFF"),
                fg=muted,
                cursor="hand2",
            )
            lbl.pack(side=tk.LEFT, padx=1)
            lbl.bind("<Button-1>", lambda e, val=n: self._pick(val, toggle=True))
            self._cells.append(lbl)

        self._selected_label = tk.Label(
            self,
            text="",
            font=(*_UI_FONT[:2], "bold") if len(_UI_FONT) >= 2 else ("Segoe UI", 11, "bold"),
            fg=accent,
            bg=theme.get("surface", "#FFF"),
        )
        self._selected_label.pack(side=tk.LEFT, padx=(8, 0))

        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<Left>", self._key_left)
        self.bind("<Right>", self._key_right)
        self.bind("<Delete>", self._key_clear)
        self.bind("<BackSpace>", self._key_clear)
        for n in range(1, 10):
            self.bind(str(n), lambda e, val=n: self._pick(val, toggle=False))
        self.bind("0", lambda e: self._pick(10, toggle=False))
        for lbl in self._cells:
            lbl.bind("<FocusIn>", lambda e: self.focus_set())

    def _on_focus_in(self, _event=None) -> None:
        try:
            self.update_idletasks()
            self.event_generate("<Visibility>")
        except tk.TclError:
            pass

    def get_rating(self) -> int | None:
        return self._rating

    def set_rating(self, value: int | None) -> None:
        if value is not None and not (1 <= int(value) <= 10):
            value = None
        self._rating = int(value) if value is not None else None
        self._refresh_cells()

    def clear(self) -> None:
        self.set_rating(None)

    def _pick(self, val: int, *, toggle: bool) -> None:
        if toggle and self._rating == val:
            self.clear()
        else:
            self.set_rating(val)
        if self._on_change:
            self._on_change()

    def _key_left(self, _event) -> str:
        if self._rating is None:
            self._pick(1, toggle=False)
        elif self._rating > 1:
            self._pick(self._rating - 1, toggle=False)
        return "break"

    def _key_right(self, _event) -> str:
        if self._rating is None:
            self._pick(1, toggle=False)
        elif self._rating < 10:
            self._pick(self._rating + 1, toggle=False)
        return "break"

    def _key_clear(self, _event) -> str:
        self.clear()
        if self._on_change:
            self._on_change()
        return "break"

    def _refresh_cells(self) -> None:
        sel = self._rating
        for idx, lbl in enumerate(self._cells, start=1):
            if sel == idx:
                lbl.config(
                    bg=self._colors["selected_bg"],
                    fg=self._colors["accent"],
                    relief=tk.SOLID,
                    bd=2,
                    font=FONTS.get("body_bold", _UI_FONT),
                )
            else:
                lbl.config(
                    bg=self.theme.get("surface", "#FFF"),
                    fg=self._colors["muted"],
                    relief=tk.GROOVE,
                    bd=1,
                    font=_UI_FONT,
                )
        if sel is not None:
            self._selected_label.config(text=f"Selected: {sel}")
        else:
            self._selected_label.config(text="")


class DomainReflectRow:
    """State holder for one domain on the reflect page."""

    def __init__(
        self,
        cat_name: str,
        cat_data: dict,
        existing: dict,
        theme: dict,
        parent: tk.Misc,
        scroll_canvas: tk.Canvas,
    ) -> None:
        self.cat_name = cat_name
        self.cat_data = cat_data
        self.theme = theme
        self.scroll_canvas = scroll_canvas
        self.frame = ttk.Frame(parent, style="Card.TFrame", padding=(12, 10))
        self.details_built = False
        self.check_vars: dict[str, tk.BooleanVar] = {}
        self.metric_vars: dict[str, tk.Variable] = {}
        self.checklist_touched: set[str] = set()
        self.metrics_touched: set[str] = set()
        self.details_frame: ttk.Frame | None = None
        self._existing_entry = existing
        self._full_form_btn: ttk.Button | None = None

        header = ttk.Frame(self.frame, style="Card.TFrame")
        header.pack(fill=tk.X)
        ttk.Label(header, text=cat_name, style="Subheading.TLabel").pack(side=tk.LEFT, anchor="w")
        self._full_form_btn = ttk.Button(header, text="Full form…", command=lambda: None)
        self._full_form_btn.pack(side=tk.RIGHT)

        self.rating_row = RatingRow(self.frame, theme, on_change=self._clear_domain_error)
        self.rating_row.pack(fill=tk.X, pady=(6, 4))
        existing_rating = existing.get("rating")
        if existing_rating is not None:
            try:
                self.rating_row.set_rating(int(existing_rating))
            except (TypeError, ValueError):
                pass

        notes_label = ttk.Label(self.frame, text="Notes", style="Muted.TLabel")
        notes_label.pack(anchor="w", pady=(4, 0))
        self.notes = scrolledtext.ScrolledText(self.frame, height=3, wrap=tk.WORD, font=_UI_FONT)
        style_text_widget(self.notes, theme)
        self.notes.pack(fill=tk.X, pady=(2, 4))
        if existing.get("notes"):
            self.notes.insert("1.0", existing["notes"])

        def notes_key_filter(event: tk.Event) -> str | None:
            if event.char and event.char.isdigit():
                return "break"
            return None

        self.notes.bind("<Key>", notes_key_filter, add="+")

        def ctrl_enter_notes(_event: tk.Event) -> str:
            return "break"

        self.notes.bind("<Control-Return>", ctrl_enter_notes, add="+")
        self.notes.bind("<Control-s>", ctrl_enter_notes, add="+")

        self.domain_error = make_inline_error_label(self.frame, theme)

        self.details_toggle = ttk.Button(
            self.frame,
            text="Details…",
            command=self.toggle_details,
        )
        self.details_toggle.pack(anchor="w", pady=(2, 0))

        self.rating_row.bind("<Tab>", self._tab_from_rating, add="+")
        self.rating_row.bind("<space>", self._space_details, add="+")
        self.frame.bind("<FocusIn>", lambda e: self._scroll_into_view(), add="+")
        self.rating_row.bind("<FocusIn>", lambda e: self._scroll_into_view(), add="+")

    def _scroll_into_view(self) -> None:
        try:
            self.frame.update_idletasks()
            canvas = self.scroll_canvas
            bbox = canvas.bbox("all")
            if not bbox:
                return
            content_h = max(bbox[3] - bbox[1], 1)
            frame_y = self.frame.winfo_y()
            frame_h = self.frame.winfo_height()
            view_top_frac = canvas.yview()[0]
            view_bottom_frac = canvas.yview()[1]
            top_px = view_top_frac * content_h
            bottom_px = view_bottom_frac * content_h
            if frame_y < top_px:
                canvas.yview_moveto(max(0.0, (frame_y - 8) / content_h))
            elif frame_y + frame_h > bottom_px:
                canvas.yview_moveto(min(1.0, (frame_y + frame_h - canvas.winfo_height()) / content_h))
        except tk.TclError:
            pass

    def _tab_from_rating(self, _event) -> str | None:
        self.notes.focus_set()
        return "break"

    def _space_details(self, _event) -> str:
        self.toggle_details()
        return "break"

    def _clear_domain_error(self) -> None:
        set_field_error(self.domain_error, None)

    def toggle_details(self) -> None:
        if self.details_built:
            if self.details_frame is not None:
                if self.details_frame.winfo_ismapped():
                    self.details_frame.pack_forget()
                    self.details_toggle.config(text="Details…")
                else:
                    self.details_frame.pack(fill=tk.X, pady=(6, 0))
                    self.details_toggle.config(text="Hide details")
            return
        self._build_details()
        self.details_toggle.config(text="Hide details")

    def _build_details(self) -> None:
        self.details_built = True
        self.details_frame = ttk.Frame(self.frame, style="Card.TFrame")
        self.details_frame.pack(fill=tk.X, pady=(6, 0))

        existing = self._existing_entry

        ttk.Label(self.details_frame, text="Checklist", style="Muted.TLabel").pack(anchor="w")
        for item in self.cat_data.get("checklist", []):
            var = tk.BooleanVar(value=bool(existing.get("checklist", {}).get(item, False)))
            self.check_vars[item] = var

            def mark_touched(name=item) -> None:
                self.checklist_touched.add(name)

            ttk.Checkbutton(
                self.details_frame,
                text=item,
                variable=var,
                command=mark_touched,
            ).pack(anchor="w", padx=(8, 0))

        ttk.Label(self.details_frame, text="Metrics", style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
        for metric in self.cat_data.get("metrics", []):
            name = metric["name"]
            mtype = metric.get("type", "number")
            default = metric.get("default", 0)
            existing_val = existing.get("metrics", {}).get(name, default)
            row = ttk.Frame(self.details_frame)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"{name}:").pack(side=tk.LEFT)
            if mtype == "number":
                var: tk.Variable = tk.DoubleVar(value=float(existing_val))
                entry = ttk.Entry(row, textvariable=var, width=10)
            else:
                var = tk.IntVar(value=int(existing_val))
                entry = ttk.Spinbox(
                    row,
                    from_=metric.get("min", 1),
                    to=metric.get("max", 10),
                    textvariable=var,
                    width=6,
                )
            entry.pack(side=tk.LEFT, padx=6)
            self.metric_vars[name] = var

            def mark_metric(_e=None, metric_name=name) -> None:
                self.metrics_touched.add(metric_name)

            entry.bind("<FocusOut>", mark_metric, add="+")

    def set_full_form_command(self, cmd: Callable[[], None]) -> None:
        if self._full_form_btn is not None:
            self._full_form_btn.config(command=cmd)

    def notes_text(self) -> str:
        return self.notes.get("1.0", tk.END).strip()

    def validation_error(self) -> str | None:
        rating = self.rating_row.get_rating()
        notes = self.notes_text()
        if rating is None and notes:
            return "Rate this domain to save its notes"
        return None

    def build_payload(self) -> dict | None:
        rating = self.rating_row.get_rating()
        if rating is None:
            return None
        checklist = collect_touched_checklist(self.check_vars, touched=self.checklist_touched)
        metrics = collect_touched_metrics(
            self.metric_vars, self.cat_data, touched=self.metrics_touched
        )
        return build_entry_payload(
            self.cat_data,
            rating,
            checklist=checklist,
            metrics=metrics,
            notes=self.notes_text(),
        )


def save_reflect_page(
    tracker: PersonalDevelopmentTracker,
    rows: list[DomainReflectRow],
    *,
    date_str: str,
    page_error: tk.Label,
    on_done: Callable[[bool], None] | None = None,
) -> None:
    set_field_error(page_error, None)
    for row in rows:
        set_field_error(row.domain_error, None)

    rated_any = False
    errors: list[tuple[DomainReflectRow, str]] = []
    for row in rows:
        err = row.validation_error()
        if err:
            errors.append((row, err))
        elif row.rating_row.get_rating() is not None:
            rated_any = True

    if errors:
        for row, msg in errors:
            set_field_error(row.domain_error, msg)

    if not rated_any:
        set_field_error(page_error, "Rate at least one domain")
        return

    if errors:
        return

    prior_day = copy.deepcopy(tracker.entries.get(date_str))
    if date_str not in tracker.entries:
        tracker.entries[date_str] = {}

    changed = False
    for row in rows:
        payload = row.build_payload()
        if payload is None:
            continue
        existing = tracker.entries.get(date_str, {}).get(row.cat_name, {})
        merged = merge_entry_updates(existing, payload)
        if merged != existing:
            changed = True
        tracker.entries[date_str][row.cat_name] = merged

    if not changed:
        banner = tracker.ensure_status_banner()
        banner.show_success("Nothing to save — no changes.")
        if on_done:
            on_done(True)
        return

    tracker._invalidate_caches()
    guidance_parts: list[str] = []

    def on_saved(ok: bool, _err: BaseException | None) -> None:
        if not ok:
            if prior_day is None:
                tracker.entries.pop(date_str, None)
            else:
                tracker.entries[date_str] = prior_day
            tracker._invalidate_caches()
            if on_done:
                on_done(False)
            return
        tracker.refresh_dashboard()
        banner = tracker.ensure_status_banner()
        if guidance_parts and not tracker.settings.get("hide_post_log_guidance"):
            text = guidance_parts[0]
            if len(guidance_parts) > 1:
                text += f" (+{len(guidance_parts) - 1} more)"

            def hide_guidance_forever() -> None:
                tracker.settings["hide_post_log_guidance"] = True
                tracker.save_data(flush=True)
                banner.dismiss()

            banner.show_info(
                text,
                extra_actions=[("Don't show again", hide_guidance_forever)],
            )
        else:
            banner.show_success(f"Saved reflection for {date_str}.")
        if date_str == tracker.today_str() and tracker._reminder_scheduler is not None:
            tracker._reminder_scheduler.notify_logged_today()
        if on_done:
            on_done(True)

    for row in rows:
        if row.rating_row.get_rating() is None:
            continue
        hint = category_insight(tracker._get_insights(), row.cat_name)
        if hint and hint.suggested_actions and not tracker.settings.get("hide_post_log_guidance"):
            guidance_parts.append(f"{row.cat_name}: {hint.message} Try: {hint.suggested_actions[0]}")

    tracker.save_data(recompute_fitness=False, on_complete=on_saved)


def open_reflect_page(tracker: PersonalDevelopmentTracker) -> tk.Toplevel:
    existing_win = tracker._open_windows.get(REFLECT_WINDOW_KEY)
    if existing_win is not None:
        try:
            if existing_win.winfo_exists():
                existing_win.lift()
                existing_win.focus_force()
                return existing_win
        except tk.TclError:
            pass

    theme = tracker.theme
    date_str = tracker.today_str()
    win = tk.Toplevel(tracker.root)
    win.title("Reflect — today")
    win.geometry("960x680")
    win.minsize(720, 520)
    win.configure(bg=theme["bg"])
    win.transient(tracker.root)

    tracker._track_window(REFLECT_WINDOW_KEY, win)

    header = tk.Frame(win, bg=theme["bg"], padx=16, pady=12)
    header.pack(fill=tk.X)
    ttk.Label(
        header,
        text=f"Daily reflection — {date_str}",
        style="Heading.TLabel",
    ).pack(anchor="w")
    ttk.Label(
        header,
        text=f"All {len(tracker.categories)} domains — pinned first. Rate 1–10, optional notes; expand Details for checklist and metrics.",
        style="Muted.TLabel",
        wraplength=900,
    ).pack(anchor="w", pady=(4, 0))

    page_error = make_inline_error_label(header, theme)

    body_host = ttk.Frame(win)
    body_host.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))
    outer, inner, canvas = ui_scroll.make_scrollable_frame(body_host, theme=theme, chrome_bg=theme["bg"])
    outer.pack(fill=tk.BOTH, expand=True)
    day_entries = tracker.entries.get(date_str, {})
    names = ordered_reflect_domains(list(tracker.categories.keys()), tracker.settings)
    rows: list[DomainReflectRow] = []
    for cat_name in names:
        cat_data = tracker.categories[cat_name]
        existing = day_entries.get(cat_name, {})
        row = DomainReflectRow(
            cat_name,
            cat_data,
            existing,
            theme,
            inner,
            canvas,
        )
        row.set_full_form_command(lambda c=cat_name: tracker.open_log_dialog(c, date_str=date_str))
        row.frame.pack(fill=tk.X, pady=(0, 10))
        rows.append(row)

    footer = ttk.Frame(win, padding=(16, 12))
    footer.pack(fill=tk.X)
    ttk.Separator(footer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 8))
    btn_row = ttk.Frame(footer)
    btn_row.pack(fill=tk.X)
    save_btn = ttk.Button(btn_row, text="Save reflection", style="Accent.TButton")
    save_btn.pack(side=tk.LEFT, padx=(0, 8))
    cancel_btn = ttk.Button(btn_row, text="Close", command=win.destroy)
    cancel_btn.pack(side=tk.LEFT)

    def request_save() -> None:
        save_reflect_page(tracker, rows, date_str=date_str, page_error=page_error)

    save_btn.config(command=request_save)
    wire_dialog_accent_keys(win, save_btn, cancel_btn=cancel_btn)

    def save_shortcut(_event=None) -> str:
        request_save()
        return "break"

    win.bind("<Control-s>", save_shortcut, add="+")
    win.bind("<Control-Return>", save_shortcut, add="+")

    def on_close() -> None:
        dirty = False
        for row in rows:
            payload = row.build_payload()
            existing = tracker.entries.get(date_str, {}).get(row.cat_name, {})
            if payload is not None:
                merged = merge_entry_updates(existing, payload)
                if merged != existing:
                    dirty = True
            elif row.notes_text() and row.rating_row.get_rating() is None:
                dirty = True
            elif row.rating_row.get_rating() is not None:
                dirty = True
        if dirty:
            if not messagebox.askyesno(
                "Unsaved reflection",
                "You have unsaved ratings or notes. Close without saving?",
                parent=win,
            ):
                return
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_close)
    cancel_btn.config(command=on_close)

    return win
