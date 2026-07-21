"""Daily practice logging dialog (SPEC-318)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

import practices
from theme import FONTS, style_text_widget

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker

_FIELD_LABELS = {
    practices.FIELD_DURATION: "Duration (min)",
    practices.FIELD_COMPLETIONS: "Completions",
    practices.FIELD_SETS: "Sets",
    practices.FIELD_HOLD: "Hold (sec)",
    practices.FIELD_QUALITY: "Quality (1–10)",
}


def show_practice_log_dialog(
    tracker: PersonalDevelopmentTracker, parent: tk.Misc | None = None
) -> tk.Toplevel:
    theme = tracker.theme
    parent = parent or tracker.root
    dlg = tk.Toplevel(parent)
    dlg.title("Log daily practice")
    dlg.geometry("440x560")
    dlg.minsize(380, 480)
    dlg.configure(bg=theme["bg"])
    dlg.transient(parent)
    dlg.attributes("-topmost", True)

    preset_summaries = practices.list_presets()
    preset_by_title = {p["title"]: p for p in preset_summaries}
    domain_names = list(tracker.categories.keys())

    body = ttk.Frame(dlg, padding=12)
    body.pack(fill=tk.BOTH, expand=True)

    ttk.Label(body, text="Log a daily practice", font=FONTS["heading"]).pack(anchor="w")

    ttk.Label(body, text="Practice").pack(anchor="w", pady=(8, 0))
    preset_title = tk.StringVar(value=preset_summaries[0]["title"])
    ttk.Combobox(
        body,
        textvariable=preset_title,
        values=[p["title"] for p in preset_summaries],
        state="readonly",
    ).pack(fill=tk.X, pady=2)

    hint_var = tk.StringVar(value="")
    ttk.Label(body, textvariable=hint_var, style="Muted.TLabel", wraplength=400).pack(
        anchor="w", pady=(0, 6)
    )

    row = ttk.Frame(body)
    row.pack(fill=tk.X, pady=2)
    ttk.Label(row, text="Date").pack(side=tk.LEFT)
    date_var = tk.StringVar(value=tracker.today_str())
    ttk.Entry(row, textvariable=date_var, width=14).pack(side=tk.LEFT, padx=6)
    ttk.Label(row, text="Life domain").pack(side=tk.LEFT, padx=(8, 0))
    domain_var = tk.StringVar(value=domain_names[0] if domain_names else "")
    ttk.Combobox(row, textvariable=domain_var, values=domain_names, width=20, state="readonly").pack(
        side=tk.LEFT, padx=4
    )

    fields_frame = ttk.Frame(body)
    fields_frame.pack(fill=tk.X, pady=(6, 0))

    field_vars: dict[str, tk.Variable] = {}
    notes_widget: dict[str, tk.Text] = {}

    def rebuild_fields(*_args) -> None:
        for child in fields_frame.winfo_children():
            child.destroy()
        field_vars.clear()
        notes_widget.clear()
        preset = preset_by_title.get(preset_title.get()) or preset_summaries[0]
        hint_var.set(preset.get("hint", ""))
        if preset["domain"] in domain_names:
            domain_var.set(preset["domain"])
        labels = preset.get("labels", {})
        for field in preset["fields"]:
            if field == practices.FIELD_NOTES:
                ttk.Label(fields_frame, text="Notes").pack(anchor="w", pady=(6, 0))
                text = tk.Text(fields_frame, height=3, wrap=tk.WORD, font=FONTS["body"])
                text.pack(fill=tk.X)
                style_text_widget(text, theme)
                notes_widget["notes"] = text
                continue
            if field == practices.FIELD_PER_SIDE:
                var = tk.BooleanVar(value=False)
                ttk.Checkbutton(fields_frame, text="Per side", variable=var).pack(anchor="w", pady=2)
                field_vars[field] = var
                continue
            label = labels.get(field) or _FIELD_LABELS.get(field, field)
            line = ttk.Frame(fields_frame)
            line.pack(fill=tk.X, pady=2)
            ttk.Label(line, text=label, width=18).pack(side=tk.LEFT)
            var = tk.StringVar(value="")
            ttk.Entry(line, textvariable=var, width=10).pack(side=tk.LEFT)
            field_vars[field] = var

    preset_title.trace_add("write", rebuild_fields)
    rebuild_fields()

    def save() -> None:
        preset = preset_by_title.get(preset_title.get()) or preset_summaries[0]
        kwargs = {
            "name": preset["title"],
            "date": date_var.get().strip() or tracker.today_str(),
            "preset": preset["id"],
            "domain": domain_var.get().strip(),
        }
        for field, var in field_vars.items():
            kwargs[field] = var.get()
        if "notes" in notes_widget:
            kwargs["notes"] = notes_widget["notes"].get("1.0", "end-1c").strip()
        try:
            tracker.practices = practices.add_practice(tracker.practices, **kwargs)
        except ValueError as exc:
            messagebox.showwarning("Log practice", str(exc), parent=dlg)
            return
        logged = practices.list_practices(tracker.practices)[-1]
        if kwargs["domain"]:
            practices.merge_practice_line(
                tracker.entries,
                date_str=logged["date"],
                domain=kwargs["domain"],
                item=logged,
            )
            tracker._invalidate_caches()
            tracker.refresh_dashboard(full=False)
        tracker.save_data(flush=True)
        dlg.destroy()

    footer = ttk.Frame(dlg, padding=12)
    footer.pack(fill=tk.X, side=tk.BOTTOM)
    ttk.Button(footer, text="Save practice", style="Accent.TButton", command=save).pack(side=tk.LEFT)
    ttk.Button(footer, text="Cancel", command=dlg.destroy).pack(side=tk.RIGHT)
    return dlg
