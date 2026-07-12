"""Deep Work Mode UI — start dialog and session banner (SPEC-305)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

import creative_projects as cp
import deep_work as dw
from creative_ui import open_document_window

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker


def show_deep_work_start_dialog(tracker: PersonalDevelopmentTracker) -> None:
    theme = tracker.theme
    settings = dw.normalize_deep_work_settings(tracker.settings)

    win = tk.Toplevel(tracker.root)
    win.title("Deep Work")
    win.geometry("440x360")
    win.minsize(400, 320)
    win.configure(bg=theme["bg"])
    win.transient(tracker.root)
    win.grab_set()

    minutes_var = tk.IntVar(value=int(settings["last_minutes"]))
    open_writing = tk.BooleanVar(value=False)
    project_choice = tk.StringVar(value="")

    projects = cp.list_projects(tracker.creative_projects, include_archived=False)
    project_labels = [f"{p['title']} ({p['id']})" for p in projects]
    id_by_label = {f"{p['title']} ({p['id']})": p["id"] for p in projects}

    header = ttk.Frame(win, padding=(16, 14, 16, 8))
    header.pack(side=tk.TOP, fill=tk.X)
    ttk.Label(header, text="Deep Work", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        header,
        text="Quiet the chrome, set a timer, and focus. Optional: open a writing project.",
        style="Muted.TLabel",
        wraplength=400,
    ).pack(anchor="w", pady=(4, 0))

    body = ttk.Frame(win, padding=(16, 8, 16, 8))
    body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    ttk.Label(body, text="Duration", style="Subheading.TLabel").pack(anchor="w")
    presets = ttk.Frame(body)
    presets.pack(anchor="w", pady=(6, 8))
    for preset in dw.DEFAULT_PRESETS:
        ttk.Button(
            presets,
            text=f"{preset} min",
            command=lambda m=preset: minutes_var.set(m),
        ).pack(side=tk.LEFT, padx=(0, 6))

    custom = ttk.Frame(body)
    custom.pack(anchor="w", pady=(0, 12))
    ttk.Label(custom, text="Custom minutes").pack(side=tk.LEFT)
    ttk.Spinbox(custom, from_=1, to=240, textvariable=minutes_var, width=6).pack(side=tk.LEFT, padx=8)

    writing_frame = ttk.LabelFrame(body, text="Writing (optional)", padding=10)
    writing_frame.pack(fill=tk.X, pady=(4, 8))
    if projects:
        ttk.Checkbutton(
            writing_frame,
            text="Open inspiration + manuscript for a project",
            variable=open_writing,
        ).pack(anchor="w")
        combo = ttk.Combobox(
            writing_frame,
            textvariable=project_choice,
            values=project_labels,
            state="readonly",
            width=42,
        )
        combo.pack(anchor="w", pady=(6, 0))
        if project_labels:
            project_choice.set(project_labels[0])
    else:
        ttk.Label(
            writing_frame,
            text="No writing projects yet — Deep Work still works without them.",
            style="Muted.TLabel",
            wraplength=380,
        ).pack(anchor="w")

    footer = ttk.Frame(win, padding=(16, 8, 16, 14))
    footer.pack(side=tk.BOTTOM, fill=tk.X)

    def on_start() -> None:
        try:
            minutes = int(minutes_var.get())
        except (TypeError, ValueError, tk.TclError):
            messagebox.showwarning("Deep Work", "Enter a valid duration in minutes.", parent=win)
            return
        if minutes < 1:
            messagebox.showwarning("Deep Work", "Duration must be at least 1 minute.", parent=win)
            return

        tracker.settings = dw.apply_deep_work_settings(
            tracker.settings,
            {"last_minutes": minutes, "reduce_chrome": True},
        )
        tracker.save_data(flush=True)

        project_id = None
        if open_writing.get() and project_choice.get():
            project_id = id_by_label.get(project_choice.get())

        win.destroy()
        tracker.start_deep_work(minutes, writing_project_id=project_id)

    ttk.Button(footer, text="Start", style="Accent.TButton", command=on_start).pack(side=tk.LEFT)
    ttk.Button(footer, text="Cancel", command=win.destroy).pack(side=tk.RIGHT)


def open_writing_pair(tracker: PersonalDevelopmentTracker, project_id: str) -> None:
    open_document_window(tracker, project_id, cp.DOC_INSPIRATION)
    open_document_window(tracker, project_id, cp.DOC_MANUSCRIPT)
