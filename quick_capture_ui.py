"""Always-on-top Quick Capture panel (SPEC-314 + SPEC-315)."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

import deep_work as dw
import focus_shield
import quick_capture
import todos
from theme import FONTS, style_canvas, style_text_widget
import ui_scroll
from ui_scroll import refresh_scroll_region

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker

QUICK_LOG_CHOICES = (
    ("Life domain log…", "life"),
    ("Journal", "journal"),
    ("Log exercise", "exercise"),
    ("Log daily practice", "practice"),
    ("Fitness Hub", "fitness"),
    ("Body composition", "body"),
    ("Plan tomorrow", "plan"),
    ("Writing projects", "writing"),
)


def open_quick_capture_panel(tracker: PersonalDevelopmentTracker) -> tk.Toplevel:
    existing = getattr(tracker, "_quick_capture_win", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                existing.lift()
                existing.focus_force()
                return existing
        except tk.TclError:
            pass

    theme = tracker.theme
    win = tk.Toplevel(tracker.root)
    tracker._quick_capture_win = win
    win.title("Quick Capture")
    win.geometry("420x720")
    win.configure(bg=theme["bg"])
    win.attributes("-topmost", True)
    win.resizable(True, True)

    def on_close() -> None:
        tracker.set_quick_capture_enabled(False, persist=True)

    win.protocol("WM_DELETE_WINDOW", on_close)

    try:
        return _build_quick_capture_body(tracker, win, theme, on_close)
    except Exception:
        # Don't leave a blank cached Toplevel if build fails mid-way.
        tracker._quick_capture_win = None
        try:
            win.destroy()
        except tk.TclError:
            pass
        raise


def _build_quick_capture_body(tracker, win, theme, on_close) -> tk.Toplevel:
    # Pin footer first so scroll body cannot eat the whole window.
    footer = ttk.Frame(win, padding=(12, 8))
    footer.pack(side=tk.BOTTOM, fill=tk.X)
    ttk.Button(footer, text="Turn off Quick Capture", command=on_close).pack(anchor="e")

    scroll_host = ttk.Frame(win)
    scroll_host.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    outer, inner, canvas = ui_scroll.make_scrollable_frame(scroll_host)
    # Dark-theme ttk labels are light; unstyled tk.Canvas defaults to SystemButtonFace.
    style_canvas(canvas, theme)
    outer.configure(bg=theme["bg"])
    inner.configure(bg=theme["bg"])
    outer.pack(fill=tk.BOTH, expand=True)

    pad = ttk.Frame(inner, padding=12)
    pad.pack(fill=tk.X, expand=False)

    # FONTS key is "subheading" (not "subtitle") — wrong key crashed build after
    # caching the empty Toplevel, so later opens only lifted a blank shell.
    ttk.Label(pad, text="Quick Capture", font=FONTS["subheading"]).pack(anchor="w")
    ttk.Label(
        pad,
        text="Todos, links, journal, quick log, and Deep Work — off when you close this.",
        style="Muted.TLabel",
        wraplength=380,
    ).pack(anchor="w", pady=(2, 8))

    # --- Deep Work + focus shield ---
    dw_box = ttk.LabelFrame(pad, text="Deep Work + focus shield", padding=8)
    dw_box.pack(fill=tk.X, pady=(0, 10))
    dw_timer_var = tk.StringVar(value="Not running")
    ttk.Label(dw_box, textvariable=dw_timer_var, font=FONTS["subheading"]).pack(anchor="w")

    def refresh_dw_timer() -> None:
        session = getattr(tracker, "_deep_work_session", None)
        if session and session.running:
            dw_timer_var.set(f"Remaining {session.format_mmss()}")
        elif getattr(tracker, "_focus_shield", None) and tracker._focus_shield.active:
            dw_timer_var.set("Focus shield on (no timer)")
        else:
            dw_timer_var.set("Not running")
        try:
            if win.winfo_exists():
                win.after(1000, refresh_dw_timer)
        except tk.TclError:
            pass

    def start_deep_work_flow() -> None:
        if tracker._deep_work_session and tracker._deep_work_session.running:
            messagebox.showinfo(
                "Deep Work",
                f"Already running — {tracker._deep_work_session.format_mmss()} left.",
                parent=win,
            )
            return
        _show_deep_work_shield_dialog(tracker, parent=win)

    def end_deep_work() -> None:
        tracker.end_deep_work(completed=False)
        refresh_dw_timer()

    def extend_deep_work() -> None:
        tracker.extend_deep_work()
        refresh_dw_timer()

    dw_btns = ttk.Frame(dw_box)
    dw_btns.pack(fill=tk.X, pady=(6, 0))
    ttk.Button(dw_btns, text="Start Deep Work…", style="Accent.TButton", command=start_deep_work_flow).pack(
        side=tk.LEFT
    )
    ttk.Button(dw_btns, text="+10 min", command=extend_deep_work).pack(side=tk.LEFT, padx=4)
    ttk.Button(dw_btns, text="End", command=end_deep_work).pack(side=tk.LEFT)

    # --- Today / Upcoming todos (collapsible) ---
    def _make_section(title: str, section_key: str) -> tk.Frame:
        box = ttk.Frame(pad)
        box.pack(fill=tk.X, expand=False, pady=(0, 10))
        body = tk.Frame(box, bg=theme["bg"])
        header_var = tk.StringVar()
        state = {"collapsed": quick_capture.is_section_collapsed(tracker.settings, section_key)}

        def render_header() -> None:
            header_var.set(f"{'▸' if state['collapsed'] else '▾'}  {title}")

        def apply_visibility() -> None:
            if state["collapsed"]:
                body.pack_forget()
            else:
                body.pack(fill=tk.X, expand=False, pady=(4, 0))
            win.update_idletasks()
            refresh_scroll_region(canvas, inner)

        def toggle(_event=None) -> None:
            state["collapsed"] = not state["collapsed"]
            tracker.settings = quick_capture.set_section_collapsed(
                tracker.settings, section_key, state["collapsed"]
            )
            tracker.save_data(flush=True)
            render_header()
            apply_visibility()

        header = ttk.Label(box, textvariable=header_var, style="Subheading.TLabel", cursor="hand2")
        header.pack(fill=tk.X)
        header.bind("<Button-1>", toggle)
        render_header()
        apply_visibility()
        return body

    today_list = _make_section("Today’s todos", "today")
    upcoming_list = _make_section("Upcoming (scheduled)", "upcoming")

    add_frame = ttk.Frame(pad)
    add_frame.pack(fill=tk.X, pady=(0, 10))
    ttk.Label(add_frame, text="New todo").pack(anchor="w")
    new_text = tk.StringVar()
    ttk.Entry(add_frame, textvariable=new_text).pack(fill=tk.X, pady=2)
    row = ttk.Frame(add_frame)
    row.pack(fill=tk.X, pady=2)
    ttk.Label(row, text="Work date").pack(side=tk.LEFT)
    date_var = tk.StringVar(value=tracker.today_str())
    ttk.Entry(row, textvariable=date_var, width=12).pack(side=tk.LEFT, padx=6)
    ttk.Label(row, text="Category").pack(side=tk.LEFT, padx=(8, 0))
    cat_names = [""] + list(tracker.categories.keys())
    new_cat = tk.StringVar(value="")
    ttk.Combobox(row, textvariable=new_cat, values=cat_names, width=22, state="readonly").pack(
        side=tk.LEFT, padx=4
    )

    def persist_todos() -> None:
        tracker.todos = todos.normalize_todos(tracker.todos)
        tracker.save_data(flush=True)

    def rebuild_todo_lists() -> None:
        for child in today_list.winfo_children():
            child.destroy()
        for child in upcoming_list.winfo_children():
            child.destroy()
        today = tracker.today_str()
        edit_categories = list(tracker.categories.keys())
        today_items = todos.items_for_day(tracker.todos, today)
        today_ids = [i["id"] for i in today_items]
        for item in today_items:
            _todo_row(
                today_list, tracker, item, persist_todos, rebuild_todo_lists, win,
                sibling_ids=today_ids, categories=edit_categories,
            )
        upcoming = todos.upcoming_items(tracker.todos, today)
        upcoming_ids = [i["id"] for i in upcoming]
        for item in upcoming:
            _todo_row(
                upcoming_list, tracker, item, persist_todos, rebuild_todo_lists, win,
                upcoming=True, sibling_ids=upcoming_ids, categories=edit_categories,
            )
        if not today_list.winfo_children():
            ttk.Label(today_list, text="No todos for today.", style="Muted.TLabel").pack(anchor="w")
        if not upcoming_list.winfo_children():
            ttk.Label(upcoming_list, text="Nothing scheduled ahead.", style="Muted.TLabel").pack(
                anchor="w"
            )
        win.update_idletasks()
        refresh_scroll_region(canvas, inner)

    def add_todo() -> None:
        text = new_text.get().strip()
        if not text:
            messagebox.showinfo("Todos", "Enter a todo.", parent=win)
            return
        try:
            tracker.todos = todos.add_todo(
                tracker.todos,
                text=text,
                work_date=date_var.get().strip() or tracker.today_str(),
                category=new_cat.get().strip(),
            )
        except ValueError as exc:
            messagebox.showwarning("Todos", str(exc), parent=win)
            return
        persist_todos()
        new_text.set("")
        date_var.set(tracker.today_str())
        new_cat.set("")
        rebuild_todo_lists()

    ttk.Button(add_frame, text="Add todo", style="Accent.TButton", command=add_todo).pack(
        anchor="w", pady=(4, 0)
    )

    # --- Quick log launcher ---
    log_box = ttk.LabelFrame(pad, text="Quick log", padding=8)
    log_box.pack(fill=tk.X, pady=(0, 10))
    log_type = tk.StringVar(value=QUICK_LOG_CHOICES[0][0])
    ttk.Combobox(
        log_box,
        textvariable=log_type,
        values=[label for label, _ in QUICK_LOG_CHOICES],
        state="readonly",
    ).pack(fill=tk.X)
    log_cat = tk.StringVar(value=list(tracker.categories.keys())[0] if tracker.categories else "")
    ttk.Label(log_box, text="Life domain (when applicable)", style="Muted.TLabel").pack(
        anchor="w", pady=(6, 0)
    )
    ttk.Combobox(
        log_box,
        textvariable=log_cat,
        values=list(tracker.categories.keys()),
        state="readonly",
    ).pack(fill=tk.X, pady=2)

    def open_quick_log() -> None:
        label = log_type.get()
        kind = dict(QUICK_LOG_CHOICES).get(label, "")
        tracker.root.deiconify()
        tracker.root.lift()
        if kind == "life":
            cat = log_cat.get().strip()
            if not cat:
                messagebox.showinfo("Quick log", "Pick a life domain.", parent=win)
                return
            tracker.open_log_dialog(cat)
        elif kind == "journal":
            from journal_ui import show_journal_window

            show_journal_window(tracker, tracker.today_str())
        elif kind == "exercise":
            tracker.show_log_exercise()
        elif kind == "practice":
            tracker.show_log_practice()
        elif kind == "fitness":
            tracker.show_fitness_hub()
        elif kind == "body":
            tracker.show_fitness_hub()
            messagebox.showinfo(
                "Body composition",
                "Opened Fitness Hub — use Body Composition from there.",
                parent=win,
            )
        elif kind == "plan":
            tracker.show_plan_tomorrow()
        elif kind == "writing":
            tracker.show_writing_projects()

    ttk.Button(log_box, text="Open", style="Accent.TButton", command=open_quick_log).pack(
        anchor="w", pady=(8, 0)
    )

    # --- Link capture (SPEC-314) ---
    link_box = ttk.LabelFrame(pad, text="Link → day entry", padding=8)
    link_box.pack(fill=tk.X, pady=(0, 10))
    url_var = tk.StringVar()
    title_var = tk.StringVar()
    link_cat = tk.StringVar(value=list(tracker.categories.keys())[0] if tracker.categories else "")
    ttk.Entry(link_box, textvariable=url_var).pack(fill=tk.X, pady=2)
    ttk.Entry(link_box, textvariable=title_var).pack(fill=tk.X, pady=2)
    ttk.Combobox(
        link_box, textvariable=link_cat, values=list(tracker.categories.keys()), state="readonly"
    ).pack(fill=tk.X, pady=2)
    link_status = tk.StringVar(value="")
    ttk.Label(link_box, textvariable=link_status, style="Muted.TLabel", wraplength=360).pack(anchor="w")

    def save_link() -> None:
        url = url_var.get().strip()
        category = link_cat.get().strip()
        if not url or not quick_capture.looks_like_url(url):
            messagebox.showinfo("Quick Capture", "Paste an http(s) URL.", parent=win)
            return
        if category not in tracker.categories:
            messagebox.showinfo("Quick Capture", "Pick a category.", parent=win)
            return
        title = title_var.get().strip()
        if not title and quick_capture.is_youtube_url(url):
            fetched = quick_capture.fetch_youtube_title(url)
            if fetched:
                title = fetched
                title_var.set(fetched)
        quick_capture.merge_day_entry_starter(
            tracker.entries,
            date_str=tracker.today_str(),
            category=category,
            url=url,
            title=title,
        )
        tracker._invalidate_caches()
        tracker.save_data(flush=True)
        tracker.refresh_dashboard(full=False)
        link_status.set(f"Saved to {category}.")
        url_var.set("")
        title_var.set("")

    ttk.Button(link_box, text="Save link", style="Accent.TButton", command=save_link).pack(
        anchor="w", pady=(4, 0)
    )

    # --- Journal ---
    journal_box = ttk.LabelFrame(pad, text="Journal", padding=8)
    journal_box.pack(fill=tk.X, pady=(0, 10))
    seed_text = tk.Text(journal_box, height=3, wrap=tk.WORD, font=FONTS["body"])
    seed_text.pack(fill=tk.X)
    style_text_widget(seed_text, theme)

    def journal_now() -> None:
        seed = seed_text.get("1.0", "end-1c").strip()
        tracker.root.deiconify()
        tracker.root.lift()
        from journal_ui import show_journal_window

        show_journal_window(tracker, tracker.today_str(), seed=seed or None)
        seed_text.delete("1.0", tk.END)

    ttk.Button(journal_box, text="Journal now", style="Accent.TButton", command=journal_now).pack(
        anchor="w", pady=(6, 0)
    )

    rebuild_todo_lists()
    refresh_dw_timer()
    win.update_idletasks()
    refresh_scroll_region(canvas, inner)
    canvas.yview_moveto(0)
    return win


def _todo_row(
    parent, tracker, item, persist, rebuild, win,
    *, upcoming: bool = False, sibling_ids=None, categories=None,
) -> None:
    row = ttk.Frame(parent)
    row.pack(fill=tk.X, pady=2)
    done_var = tk.BooleanVar(value=bool(item["done"]))

    def on_toggle() -> None:
        was_done = bool(item["done"])
        now_done = bool(done_var.get())
        tracker.todos = todos.update_todo(tracker.todos, item["id"], done=now_done)
        if now_done and not was_done and item.get("category"):
            quick_capture.merge_todo_done_line(
                tracker.entries,
                date_str=tracker.today_str(),
                category=item["category"],
                text=item["text"],
            )
            tracker._invalidate_caches()
            tracker.refresh_dashboard(full=False)
        persist()
        rebuild()

    ttk.Checkbutton(row, variable=done_var, command=on_toggle).pack(side=tk.LEFT)

    def on_remove() -> None:
        tracker.todos = todos.remove_todo(tracker.todos, item["id"])
        persist()
        rebuild()

    def on_move(delta: int) -> None:
        tracker.todos = todos.move_todo(tracker.todos, item["id"], list(sibling_ids or []), delta)
        persist()
        rebuild()

    def on_edit() -> None:
        def after_save() -> None:
            persist()
            rebuild()

        _edit_todo_dialog(tracker, item, categories or [], after_save, win)

    # Right-side controls; pack right-to-left so the visual order is ↑ ↓ ✎ ✕.
    ttk.Button(row, text="✕", width=3, command=on_remove).pack(side=tk.RIGHT)
    ttk.Button(row, text="✎", width=3, command=on_edit).pack(side=tk.RIGHT)
    ttk.Button(row, text="↓", width=3, command=lambda: on_move(1)).pack(side=tk.RIGHT)
    ttk.Button(row, text="↑", width=3, command=lambda: on_move(-1)).pack(side=tk.RIGHT)

    label = item["text"]
    if upcoming:
        label = f"{item['work_date']} — {label}"
    elif item["work_date"] < tracker.today_str() and not item["done"]:
        label = f"(overdue {item['work_date']}) {label}"
    if item.get("category"):
        label = f"{label}  [{item['category']}]"
    ttk.Label(row, text=label, wraplength=200).pack(side=tk.LEFT, fill=tk.X, expand=True)


def _edit_todo_dialog(tracker, item, categories, on_saved, parent) -> None:
    theme = tracker.theme
    dlg = tk.Toplevel(parent)
    dlg.title("Edit todo")
    dlg.configure(bg=theme["bg"])
    dlg.transient(parent)
    dlg.attributes("-topmost", True)
    dlg.geometry("380x250")

    body = ttk.Frame(dlg, padding=12)
    body.pack(fill=tk.BOTH, expand=True)

    ttk.Label(body, text="Text").pack(anchor="w")
    text_var = tk.StringVar(value=item["text"])
    ttk.Entry(body, textvariable=text_var).pack(fill=tk.X, pady=(0, 6))

    ttk.Label(body, text="Work date (YYYY-MM-DD)").pack(anchor="w")
    date_var = tk.StringVar(value=item["work_date"])
    ttk.Entry(body, textvariable=date_var, width=14).pack(anchor="w", pady=(0, 6))

    ttk.Label(body, text="Category").pack(anchor="w")
    cat_var = tk.StringVar(value=item.get("category", ""))
    ttk.Combobox(
        body, textvariable=cat_var, values=[""] + list(categories or []), state="readonly"
    ).pack(fill=tk.X, pady=(0, 6))

    def save() -> None:
        try:
            tracker.todos = todos.update_todo(
                tracker.todos,
                item["id"],
                text=text_var.get().strip(),
                work_date=date_var.get().strip(),
                category=cat_var.get().strip(),
            )
        except (ValueError, KeyError) as exc:
            messagebox.showwarning("Edit todo", str(exc), parent=dlg)
            return
        dlg.destroy()
        on_saved()

    footer = ttk.Frame(dlg, padding=12)
    footer.pack(fill=tk.X, side=tk.BOTTOM)
    ttk.Button(footer, text="Save", style="Accent.TButton", command=save).pack(side=tk.LEFT)
    ttk.Button(footer, text="Cancel", command=dlg.destroy).pack(side=tk.RIGHT)


def _show_deep_work_shield_dialog(tracker: PersonalDevelopmentTracker, *, parent) -> None:
    theme = tracker.theme
    dlg = tk.Toplevel(parent)
    dlg.title("Start Deep Work")
    dlg.configure(bg=theme["bg"])
    dlg.transient(parent)
    dlg.attributes("-topmost", True)
    dlg.geometry("460x520")

    settings = dw.normalize_deep_work_settings(tracker.settings)
    minutes_var = tk.IntVar(value=int(settings["last_minutes"]))
    use_shield = tk.BooleanVar(value=focus_shield.is_supported())

    body = ttk.Frame(dlg, padding=12)
    body.pack(fill=tk.BOTH, expand=True)
    ttk.Label(body, text="Duration (minutes)").pack(anchor="w")
    ttk.Spinbox(body, from_=1, to=240, textvariable=minutes_var, width=8).pack(anchor="w", pady=4)

    shield_frame = ttk.LabelFrame(body, text="Focus shield — minimize these apps", padding=8)
    shield_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
    ttk.Checkbutton(
        shield_frame,
        text="Enable focus shield (Windows)",
        variable=use_shield,
    ).pack(anchor="w")

    checks: list[tuple[tk.BooleanVar, focus_shield.WindowInfo]] = []
    list_host = ttk.Frame(shield_frame)
    list_host.pack(fill=tk.BOTH, expand=True, pady=6)
    if focus_shield.is_supported():
        windows = focus_shield.list_top_level_windows(exclude_pids={os.getpid()})
        # Limit list length for UI
        for info in windows[:40]:
            var = tk.BooleanVar(value=True)
            checks.append((var, info))
            ttk.Checkbutton(
                list_host,
                text=f"{info.process_name}: {info.title[:50]}",
                variable=var,
            ).pack(anchor="w")
        if not windows:
            ttk.Label(list_host, text="No other windows found.", style="Muted.TLabel").pack(anchor="w")
    else:
        use_shield.set(False)
        ttk.Label(
            list_host,
            text="Focus shield is Windows-only. Timer still works.",
            style="Muted.TLabel",
            wraplength=400,
        ).pack(anchor="w")

    def on_start() -> None:
        try:
            minutes = int(minutes_var.get())
        except (TypeError, ValueError, tk.TclError):
            messagebox.showwarning("Deep Work", "Enter a valid duration.", parent=dlg)
            return
        if minutes < 1:
            messagebox.showwarning("Deep Work", "Duration must be at least 1 minute.", parent=dlg)
            return
        tracker.settings = dw.apply_deep_work_settings(
            tracker.settings,
            {"last_minutes": minutes, "reduce_chrome": True},
        )
        tracker.save_data(flush=True)
        minimize = [info for var, info in checks if var.get()] if use_shield.get() else []
        dlg.destroy()
        tracker.start_deep_work(minutes, focus_minimize_windows=minimize or None)

    footer = ttk.Frame(dlg, padding=12)
    footer.pack(fill=tk.X, side=tk.BOTTOM)
    ttk.Button(footer, text="Start", style="Accent.TButton", command=on_start).pack(side=tk.LEFT)
    ttk.Button(footer, text="Cancel", command=dlg.destroy).pack(side=tk.RIGHT)


def close_quick_capture_panel(tracker: PersonalDevelopmentTracker) -> None:
    win = getattr(tracker, "_quick_capture_win", None)
    tracker._quick_capture_win = None
    if win is None:
        return
    try:
        if win.winfo_exists():
            win.destroy()
    except tk.TclError:
        pass
