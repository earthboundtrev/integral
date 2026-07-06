"""Journal window for Integral."""

from __future__ import annotations

import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, scrolledtext, ttk
from typing import TYPE_CHECKING

import journal
import ui_scroll
from theme import FONTS, style_listbox, style_text_widget

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker


def show_journal_window(tracker: PersonalDevelopmentTracker, entry_date: str | None = None) -> None:
    theme = tracker.theme
    win = tk.Toplevel(tracker.root)
    win.title("Journal")
    win.geometry("960x720")
    win.configure(bg=theme["bg"])
    win.transient(tracker.root)

    header = ttk.Frame(win, padding=(16, 14, 16, 8))
    header.pack(fill=tk.X)
    ttk.Label(header, text="Journal", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        header,
        text="Free write or use a prompt. Entries are encrypted when vault security is on. "
        "Backdated entries require an honest reason.",
        style="Muted.TLabel",
        wraplength=880,
    ).pack(anchor="w", pady=(4, 0))

    body = ttk.Frame(win, padding=(16, 0, 16, 8))
    body.pack(fill=tk.BOTH, expand=True)
    body.columnconfigure(0, weight=1)
    body.columnconfigure(1, weight=2)
    body.rowconfigure(0, weight=1)

    list_panel = ttk.LabelFrame(body, text="Entries", padding=8, style="Card.TLabelframe")
    list_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    list_panel.rowconfigure(0, weight=1)
    list_panel.columnconfigure(0, weight=1)

    entry_list = tk.Listbox(list_panel, exportselection=False, font=FONTS["body"])
    entry_list.grid(row=0, column=0, sticky="nsew")
    style_listbox(entry_list, theme)
    list_scroll = ttk.Scrollbar(list_panel, orient=tk.VERTICAL, command=entry_list.yview)
    entry_list.configure(yscrollcommand=list_scroll.set)
    list_scroll.grid(row=0, column=1, sticky="ns")

    editor = ttk.LabelFrame(body, text="Write", padding=10, style="Card.TLabelframe")
    editor.grid(row=0, column=1, sticky="nsew")
    editor.columnconfigure(0, weight=1)
    editor.rowconfigure(5, weight=1)

    date_var = tk.StringVar(value=entry_date or datetime.now().strftime("%Y-%m-%d"))
    prompt_var = tk.StringVar(value=journal.DEFAULT_PROMPTS[0])
    title_var = tk.StringVar(value="")
    backdate_var = tk.StringVar(value="")
    editing_id: dict[str, str | None] = {"value": None}

    row0 = ttk.Frame(editor, style="Surface.TFrame")
    row0.grid(row=0, column=0, sticky="ew", pady=(0, 6))
    ttk.Label(row0, text="Entry date", style="OnSurfaceMuted.TLabel").pack(side=tk.LEFT)
    date_entry = ttk.Entry(row0, textvariable=date_var, width=12)
    date_entry.pack(side=tk.LEFT, padx=(8, 16))
    ttk.Label(row0, text="Prompt", style="OnSurfaceMuted.TLabel").pack(side=tk.LEFT)
    prompt_combo = ttk.Combobox(
        row0,
        textvariable=prompt_var,
        values=tracker.journal.get("prompts", journal.DEFAULT_PROMPTS),
        width=34,
    )
    prompt_combo.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

    ttk.Label(editor, text="Title (optional)", style="OnSurfaceMuted.TLabel").grid(row=1, column=0, sticky="w")
    ttk.Entry(editor, textvariable=title_var).grid(row=2, column=0, sticky="ew", pady=(0, 8))

    backdate_frame = ttk.Frame(editor, style="Surface.TFrame")
    backdate_frame.grid(row=3, column=0, sticky="ew", pady=(0, 6))
    backdate_label = ttk.Label(
        backdate_frame,
        text="Why are you logging for a past date?",
        style="OnSurfaceSubheading.TLabel",
    )
    backdate_entry = ttk.Entry(backdate_frame, textvariable=backdate_var)
    backdate_hint = ttk.Label(
        backdate_frame,
        text=f"Required when the entry date is before today (min {journal.MIN_BACKDATE_REASON_LEN} chars).",
        style="OnSurfaceMuted.TLabel",
        wraplength=520,
    )

    ttk.Label(editor, text="Your thoughts", style="OnSurfaceMuted.TLabel").grid(row=4, column=0, sticky="w")
    body_text = scrolledtext.ScrolledText(editor, wrap=tk.WORD, height=16, borderwidth=0)
    body_text.grid(row=5, column=0, sticky="nsew", pady=(4, 0))
    style_text_widget(body_text, theme)

    def refresh_backdate_ui(*_args: object) -> None:
        parsed = journal.parse_entry_date(date_var.get())
        if parsed and parsed < date.today():
            backdate_label.pack(anchor="w")
            backdate_entry.pack(fill=tk.X, pady=(4, 2))
            backdate_hint.pack(anchor="w")
        else:
            backdate_label.pack_forget()
            backdate_entry.pack_forget()
            backdate_hint.pack_forget()

    date_var.trace_add("write", refresh_backdate_ui)
    refresh_backdate_ui()

    indexed_entries: list[dict] = []

    def refresh_list(select_id: str | None = None) -> None:
        nonlocal indexed_entries
        entry_list.delete(0, tk.END)
        indexed_entries = journal.list_entries(tracker.journal)
        select_index = 0
        for index, item in enumerate(indexed_entries):
            label = item.get("title") or item.get("prompt") or "Journal"
            suffix = " ↩" if item.get("backdate_reason") else ""
            entry_list.insert(tk.END, f"{item['entry_date']}  {label}{suffix}")
            if select_id and item.get("id") == select_id:
                select_index = index
        if indexed_entries:
            entry_list.selection_set(select_index)
            entry_list.see(select_index)

    def load_selected(_event=None) -> None:
        selection = entry_list.curselection()
        if not selection:
            return
        item = indexed_entries[selection[0]]
        editing_id["value"] = item["id"]
        date_var.set(item["entry_date"])
        prompt_var.set(item.get("prompt", journal.DEFAULT_PROMPTS[0]))
        title_var.set(item.get("title", ""))
        backdate_var.set(item.get("backdate_reason") or "")
        body_text.delete("1.0", tk.END)
        body_text.insert("1.0", item.get("body", ""))
        refresh_backdate_ui()

    def clear_editor() -> None:
        editing_id["value"] = None
        date_var.set(datetime.now().strftime("%Y-%m-%d"))
        prompt_var.set(journal.DEFAULT_PROMPTS[0])
        title_var.set("")
        backdate_var.set("")
        body_text.delete("1.0", tk.END)
        entry_list.selection_clear(0, tk.END)
        refresh_backdate_ui()

    def save_entry() -> None:
        entry_date = date_var.get().strip()
        reason = backdate_var.get().strip()
        error = journal.validate_backdate(entry_date, reason=reason)
        if error:
            messagebox.showwarning("Date", error, parent=win)
            return

        body = body_text.get("1.0", tk.END).strip()
        if not body:
            messagebox.showinfo("Journal", "Write something before saving.", parent=win)
            return

        try:
            item = journal.create_entry(
                entry_date,
                body,
                prompt=prompt_var.get(),
                title=title_var.get(),
                backdate_reason=reason or None,
                entry_id=editing_id["value"],
                written_at=None if not editing_id["value"] else None,
            )
        except ValueError as exc:
            messagebox.showwarning("Journal", str(exc), parent=win)
            return

        if editing_id["value"]:
            for existing in tracker.journal.get("entries", []):
                if existing.get("id") == editing_id["value"]:
                    item["written_at"] = existing.get("written_at", item["written_at"])
                    break

        journal.upsert_entry(tracker.journal, item)
        tracker._invalidate_caches()
        tracker.refresh_dashboard()
        tracker.save_data()
        saved_id = item["id"]
        clear_editor()
        refresh_list(select_id=saved_id)

    def delete_selected() -> None:
        selection = entry_list.curselection()
        if not selection:
            return
        item = indexed_entries[selection[0]]
        if not messagebox.askyesno("Delete entry", "Delete this journal entry?", parent=win):
            return
        journal.delete_entry(tracker.journal, item["id"])
        tracker._invalidate_caches()
        tracker.refresh_dashboard()
        tracker.save_data()
        clear_editor()
        refresh_list()

    entry_list.bind("<<ListboxSelect>>", load_selected)

    list_btns = ttk.Frame(list_panel)
    list_btns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    ttk.Button(list_btns, text="New", command=clear_editor).pack(side=tk.LEFT)
    ttk.Button(list_btns, text="Delete", command=delete_selected).pack(side=tk.LEFT, padx=6)

    editor_btns = ttk.Frame(editor)
    editor_btns.grid(row=6, column=0, sticky="ew", pady=(10, 0))
    ttk.Button(editor_btns, text="Save Entry", style="Accent.TButton", command=save_entry).pack(side=tk.LEFT)
    ttk.Button(editor_btns, text="Clear", command=clear_editor).pack(side=tk.LEFT, padx=8)

    footer = ttk.Frame(win, padding=(16, 8, 16, 12))
    footer.pack(fill=tk.X)
    ttk.Button(footer, text="Close", command=win.destroy).pack(side=tk.RIGHT)

    refresh_list()
    body_text.focus_set()
