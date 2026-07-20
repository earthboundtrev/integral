"""Always-on-top Quick Capture panel (SPEC-314)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

import quick_capture
from theme import FONTS, style_text_widget

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker


def open_quick_capture_panel(tracker: PersonalDevelopmentTracker) -> tk.Toplevel:
    """Create or raise the topmost capture panel. Caller owns lifecycle."""
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
    win.geometry("380x420")
    win.configure(bg=theme["bg"])
    win.attributes("-topmost", True)
    win.resizable(True, True)

    def on_close() -> None:
        # Closing the panel turns Capture mode off (lightweight when not in use).
        tracker.set_quick_capture_enabled(False, persist=True)

    win.protocol("WM_DELETE_WINDOW", on_close)

    pad = ttk.Frame(win, padding=12)
    pad.pack(fill=tk.BOTH, expand=True)

    ttk.Label(pad, text="Quick Capture", font=FONTS["subtitle"]).pack(anchor="w")
    ttk.Label(
        pad,
        text="Park a link into a life domain, or start a journal thought.",
        style="Muted.TLabel",
        wraplength=340,
    ).pack(anchor="w", pady=(2, 10))

    link_box = ttk.LabelFrame(pad, text="Link → day entry", padding=8)
    link_box.pack(fill=tk.X)

    ttk.Label(link_box, text="URL").pack(anchor="w")
    url_var = tk.StringVar()
    url_entry = ttk.Entry(link_box, textvariable=url_var)
    url_entry.pack(fill=tk.X, pady=(2, 6))

    ttk.Label(link_box, text="Title (optional — YouTube may auto-fill)").pack(anchor="w")
    title_var = tk.StringVar()
    title_entry = ttk.Entry(link_box, textvariable=title_var)
    title_entry.pack(fill=tk.X, pady=(2, 6))

    ttk.Label(link_box, text="Category").pack(anchor="w")
    categories = list(tracker.categories.keys())
    category_var = tk.StringVar(value=categories[0] if categories else "")
    cat_combo = ttk.Combobox(
        link_box,
        textvariable=category_var,
        values=categories,
        state="readonly",
    )
    cat_combo.pack(fill=tk.X, pady=(2, 8))

    status_var = tk.StringVar(value="")
    status_label = ttk.Label(link_box, textvariable=status_var, style="Muted.TLabel", wraplength=320)
    status_label.pack(anchor="w", pady=(0, 4))

    def resolve_title_if_needed() -> None:
        url = url_var.get().strip()
        if title_var.get().strip() or not quick_capture.is_youtube_url(url):
            return
        status_var.set("Fetching YouTube title…")
        win.update_idletasks()
        fetched = quick_capture.fetch_youtube_title(url)
        if fetched:
            title_var.set(fetched)
            status_var.set("Title filled from YouTube.")
        else:
            status_var.set("Could not fetch title — save still works.")

    def on_url_focus_out(_event=None) -> None:
        resolve_title_if_needed()

    url_entry.bind("<FocusOut>", on_url_focus_out)

    def save_link() -> None:
        url = url_var.get().strip()
        category = category_var.get().strip()
        if not url:
            messagebox.showinfo("Quick Capture", "Paste a URL first.", parent=win)
            return
        if not quick_capture.looks_like_url(url):
            messagebox.showinfo("Quick Capture", "URL should start with http:// or https://", parent=win)
            return
        if not category or category not in tracker.categories:
            messagebox.showinfo("Quick Capture", "Pick a life category.", parent=win)
            return
        resolve_title_if_needed()
        title = title_var.get().strip()
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
        status_var.set(f"Saved to {category} for today.")
        url_var.set("")
        title_var.set("")

    def open_full_log() -> None:
        category = category_var.get().strip()
        if not category or category not in tracker.categories:
            messagebox.showinfo("Quick Capture", "Pick a life category.", parent=win)
            return
        tracker.root.deiconify()
        tracker.root.lift()
        tracker.open_log_dialog(category)

    btns = ttk.Frame(link_box)
    btns.pack(fill=tk.X, pady=(4, 0))
    ttk.Button(btns, text="Save link", style="Accent.TButton", command=save_link).pack(side=tk.LEFT)
    ttk.Button(btns, text="Open full log", command=open_full_log).pack(side=tk.LEFT, padx=6)

    journal_box = ttk.LabelFrame(pad, text="Journal", padding=8)
    journal_box.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
    ttk.Label(
        journal_box,
        text="Optional seed (a thought, X link, …) — then Journal now.",
        style="Muted.TLabel",
        wraplength=320,
    ).pack(anchor="w")
    seed_text = tk.Text(journal_box, height=3, wrap=tk.WORD, font=FONTS["body"])
    seed_text.pack(fill=tk.BOTH, expand=True, pady=(4, 8))
    style_text_widget(seed_text, theme)

    def journal_now() -> None:
        seed = seed_text.get("1.0", "end-1c").strip()
        tracker.root.deiconify()
        tracker.root.lift()
        from journal_ui import show_journal_window

        show_journal_window(tracker, tracker.today_str(), seed=seed or None)
        seed_text.delete("1.0", tk.END)

    ttk.Button(
        journal_box,
        text="Journal now",
        style="Accent.TButton",
        command=journal_now,
    ).pack(anchor="w")

    ttk.Button(pad, text="Turn off Quick Capture", command=on_close).pack(anchor="e", pady=(10, 0))

    url_entry.focus_set()
    return win


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
