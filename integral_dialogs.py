"""Export, backup, milestones, vault, and onboarding dialogs for Integral."""

from __future__ import annotations

import os
from datetime import datetime
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
import tkinter as tk
from typing import TYPE_CHECKING, Any, Callable

from integral_io import (
    export_fitness_sessions_csv,
    export_journal_csv,
    export_life_entries_csv,
    export_milestones_csv,
    load_backup,
    restore_backup_to_path,
    write_backup,
)
import domain_templates
from milestones import current_quarter_label, merge_milestones, milestone_summary
from notifications import normalize_notification_settings, show_windows_notification
from paths import APP_NAME
from theme import FONTS, style_listbox, style_text_widget
from vault import CRYPTO_AVAILABLE, encrypt_payload, is_encrypted_file
import autostart_windows
import protocol_windows
import quick_capture
import ui_scroll

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker


def show_export_dialog(tracker: PersonalDevelopmentTracker) -> None:
    folder = filedialog.askdirectory(title="Choose export folder")
    if not folder:
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    life_path = os.path.join(folder, f"integral-life-{stamp}.csv")
    fitness_path = os.path.join(folder, f"integral-fitness-{stamp}.csv")
    milestone_path = os.path.join(folder, f"integral-milestones-{stamp}.csv")
    journal_path = os.path.join(folder, f"integral-journal-{stamp}.csv")
    try:
        life_rows = export_life_entries_csv(tracker.entries, tracker.categories, life_path)
        fitness_rows = export_fitness_sessions_csv(tracker.sessions, tracker.programs, fitness_path)
        milestone_rows = export_milestones_csv(tracker.milestones, milestone_path)
        journal_rows = export_journal_csv(tracker.journal, journal_path)
        messagebox.showinfo(
            "Export complete",
            f"Exported to:\n{life_path}\n({life_rows} life rows)\n\n"
            f"{fitness_path}\n({fitness_rows} fitness rows)\n\n"
            f"{milestone_path}\n({milestone_rows} milestones)\n\n"
            f"{journal_path}\n({journal_rows} journal entries)",
        )
    except OSError as exc:
        messagebox.showerror("Export failed", str(exc))


def show_backup_dialog(tracker: PersonalDevelopmentTracker) -> None:
    window = tk.Toplevel(tracker.root)
    window.title("Backup & Restore")
    window.geometry("520x320")
    window.configure(bg=tracker.theme["bg"])
    window.transient(tracker.root)

    ttk.Label(
        window,
        text="Back up your full journal (life areas, general journal, fitness + milestones) as JSON.\n"
        "Restore replaces the current data file (a .bak copy is kept).",
        wraplength=480,
    ).pack(anchor="w", padx=15, pady=15)

    def backup_now() -> None:
        path = filedialog.asksaveasfilename(
            title="Save backup",
            defaultextension=".json",
            filetypes=[("JSON backup", "*.json"), ("All files", "*.*")],
            initialfile=f"integral-backup-{datetime.now().strftime('%Y%m%d')}.json",
        )
        if not path:
            return
        try:
            write_backup(tracker._payload(), path)
            messagebox.showinfo("Backup saved", f"Backup written to:\n{path}")
        except OSError as exc:
            messagebox.showerror("Backup failed", str(exc))

    def restore_now() -> None:
        path = filedialog.askopenfilename(
            title="Restore backup",
            filetypes=[("JSON backup", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        if not messagebox.askyesno(
            "Confirm restore",
            "This replaces your current journal with the backup. Continue?",
        ):
            return
        try:
            backup = load_backup(path)
            restore_backup_to_path(backup, tracker.data_path, make_copy=True)
            tracker.load_data()
            tracker.create_dashboard()
            window.destroy()
            messagebox.showinfo("Restored", "Journal restored from backup.")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Restore failed", str(exc))

    buttons = ttk.Frame(window)
    buttons.pack(fill=tk.X, padx=15, pady=10)
    ttk.Button(buttons, text="Export Backup…", command=backup_now).pack(side=tk.LEFT, padx=4)
    ttk.Button(buttons, text="Restore from Backup…", command=restore_now).pack(side=tk.LEFT, padx=4)
    ttk.Button(buttons, text="Close", command=window.destroy).pack(side=tk.RIGHT)


def show_milestones_dialog(tracker: PersonalDevelopmentTracker) -> None:
    window = tk.Toplevel(tracker.root)
    window.title("Quarterly Milestones")
    window.geometry("720x520")
    window.minsize(640, 420)
    window.configure(bg=tracker.theme["bg"])
    window.transient(tracker.root)

    year, quarter, label = current_quarter_label()

    buttons = ttk.Frame(window)
    buttons.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=12)
    add_btn = ttk.Button(buttons, text="Add")
    add_btn.pack(side=tk.LEFT)
    apply_btn = ttk.Button(buttons, text="Apply")
    apply_btn.pack(side=tk.LEFT, padx=8)
    save_btn = ttk.Button(buttons, text="Save & Close")
    save_btn.pack(side=tk.RIGHT)
    ttk.Button(buttons, text="Cancel", command=window.destroy).pack(side=tk.RIGHT, padx=8)

    ttk.Label(window, text=f"{label} — track what matters this quarter", font=("Helvetica", 13, "bold")).pack(
        side=tk.TOP, anchor="w", padx=12, pady=12
    )

    body = ttk.Frame(window)
    body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12)
    body.columnconfigure(0, weight=1)
    body.rowconfigure(0, weight=1)

    listbox = tk.Listbox(body, height=12, exportselection=False)
    listbox.grid(row=0, column=0, sticky="nsew")
    style_listbox(listbox, tracker.theme)

    editor = ttk.Frame(body)
    editor.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
    editor.columnconfigure(0, weight=1)

    title_var = tk.StringVar()
    status_var = tk.StringVar(value="open")
    notes_text = scrolledtext.ScrolledText(editor, height=8, wrap=tk.WORD)
    style_text_widget(notes_text, tracker.theme)

    ttk.Label(editor, text="Title").grid(row=0, column=0, sticky="w")
    ttk.Entry(editor, textvariable=title_var, width=40).grid(row=1, column=0, sticky="ew", pady=(0, 8))
    ttk.Label(editor, text="Status").grid(row=2, column=0, sticky="w")
    ttk.Combobox(editor, textvariable=status_var, values=["open", "in_progress", "done"], state="readonly").grid(
        row=3, column=0, sticky="w", pady=(0, 8)
    )
    ttk.Label(editor, text="Notes").grid(row=4, column=0, sticky="w")
    notes_text.grid(row=5, column=0, sticky="nsew")
    editor.rowconfigure(5, weight=1)

    working = list(tracker.milestones)

    def refresh_list(select_index: int | None = None) -> None:
        listbox.delete(0, tk.END)
        for item in working:
            status = item.get("status", "open")
            mark = "✓" if status == "done" else "○"
            listbox.insert(tk.END, f"{mark} {item.get('title', '')}")
        if select_index is not None and 0 <= select_index < len(working):
            listbox.selection_set(select_index)
            load_selected()

    def load_selected(*_args: object) -> None:
        selection = listbox.curselection()
        if not selection:
            return
        item = working[selection[0]]
        title_var.set(item.get("title", ""))
        status_var.set(item.get("status", "open"))
        notes_text.delete("1.0", tk.END)
        notes_text.insert("1.0", item.get("notes", ""))

    def apply_editor() -> None:
        selection = listbox.curselection()
        if not selection:
            return
        item = working[selection[0]]
        item["title"] = title_var.get().strip() or item.get("title", "Untitled")
        item["status"] = status_var.get()
        item["notes"] = notes_text.get("1.0", tk.END).strip()
        if item["status"] == "done" and not item.get("completed_date"):
            item["completed_date"] = datetime.now().strftime("%Y-%m-%d")
        refresh_list(selection[0])

    def add_milestone() -> None:
        working.append(
            {
                "year": year,
                "quarter": quarter,
                "title": f"New milestone for {label}",
                "status": "open",
                "notes": "",
                "completed_date": "",
            }
        )
        refresh_list(len(working) - 1)

    def save_all() -> None:
        apply_editor()
        tracker.milestones = working
        tracker._invalidate_caches()
        tracker.save_data()
        window.destroy()
        messagebox.showinfo("Saved", milestone_summary(tracker.milestones))
        tracker.refresh_dashboard()

    listbox.bind("<<ListboxSelect>>", load_selected)

    add_btn.configure(command=add_milestone)
    apply_btn.configure(command=apply_editor)
    save_btn.configure(command=save_all)

    refresh_list(0 if working else None)


def show_security_dialog(tracker: PersonalDevelopmentTracker) -> None:
    window = tk.Toplevel(tracker.root)
    window.title("Data & Security")
    window.geometry("580x560")
    window.minsize(520, 480)
    window.configure(bg=tracker.theme["bg"])
    window.transient(tracker.root)

    outer, inner, _canvas = ui_scroll.make_scrollable_frame(window)
    outer.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=8)

    encrypted = bool(tracker.settings.get("encryption_enabled"))
    ttk.Label(inner, text="Encryption at rest", font=("Helvetica", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 4))
    status = "ON — journal file is encrypted" if encrypted else "OFF — journal stored as plain JSON"
    ttk.Label(inner, text=status, wraplength=500).pack(anchor="w", padx=15)

    if not CRYPTO_AVAILABLE:
        ttk.Label(
            inner,
            text="Install cryptography for encryption: pip install cryptography",
            foreground=tracker.theme.get("accent", "#5B8DEF"),
            wraplength=500,
        ).pack(anchor="w", padx=15, pady=8)

    ttk.Label(
        inner,
        text="Passphrase is kept in memory for this session only. "
        "If you forget it, encrypted data cannot be recovered.",
        wraplength=500,
    ).pack(anchor="w", padx=15, pady=8)

    def enable_encryption() -> None:
        if not CRYPTO_AVAILABLE:
            messagebox.showwarning("Unavailable", "Install cryptography first.")
            return
        passphrase = simpledialog.askstring("Set passphrase", "Choose a passphrase:", show="*", parent=window)
        if not passphrase:
            return
        confirm = simpledialog.askstring("Confirm", "Re-enter passphrase:", show="*", parent=window)
        if passphrase != confirm:
            messagebox.showerror("Mismatch", "Passphrases do not match.")
            return
        try:
            tracker.vault_passphrase = passphrase
            tracker.settings["encryption_enabled"] = True
            tracker.save_data()
            window.destroy()
            messagebox.showinfo("Enabled", "Journal encryption is now enabled.")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Failed", str(exc))

    def disable_encryption() -> None:
        if encrypted:
            passphrase = simpledialog.askstring("Unlock", "Enter current passphrase:", show="*", parent=window)
            if not passphrase:
                return
            tracker.vault_passphrase = passphrase
        tracker.settings["encryption_enabled"] = False
        tracker.vault_passphrase = None
        tracker.save_data()
        window.destroy()
        messagebox.showinfo("Disabled", "Journal saved as plain JSON.")

    def change_passphrase() -> None:
        if not encrypted:
            messagebox.showinfo("Not encrypted", "Enable encryption first.")
            return
        old = simpledialog.askstring("Current", "Current passphrase:", show="*", parent=window)
        if not old:
            return
        new = simpledialog.askstring("New", "New passphrase:", show="*", parent=window)
        if not new:
            return
        confirm = simpledialog.askstring("Confirm", "Confirm new passphrase:", show="*", parent=window)
        if new != confirm:
            messagebox.showerror("Mismatch", "Passphrases do not match.")
            return
        try:
            payload = tracker._payload()
            encrypt_payload(payload, new)  # validate crypto works
            tracker.vault_passphrase = new
            tracker.save_data()
            messagebox.showinfo("Updated", "Passphrase changed.")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Failed", str(exc))

    enc_buttons = ttk.Frame(inner)
    enc_buttons.pack(fill=tk.X, padx=15, pady=(8, 12))
    if not encrypted:
        ttk.Button(enc_buttons, text="Enable encryption…", command=enable_encryption).pack(side=tk.LEFT)
    else:
        ttk.Button(enc_buttons, text="Change passphrase…", command=change_passphrase).pack(side=tk.LEFT, padx=4)
        ttk.Button(enc_buttons, text="Disable encryption…", command=disable_encryption).pack(side=tk.LEFT, padx=4)

    ttk.Separator(inner, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=15, pady=8)
    ttk.Label(inner, text="Reminders & background", font=("Helvetica", 13, "bold")).pack(
        anchor="w", padx=15, pady=(4, 4)
    )
    ttk.Label(
        inner,
        text="Windows toasts only fire while Integral is running. The portable zip is not an "
        "installed background service — enable the options below so reminders can keep working "
        "after you close the window or after you sign in.",
        wraplength=500,
        style="Muted.TLabel",
    ).pack(anchor="w", padx=15, pady=(0, 8))

    tracker.settings = normalize_notification_settings(tracker.settings)
    notes = tracker.settings["notifications"]
    if autostart_windows.is_supported():
        notes["start_with_windows"] = autostart_windows.is_enabled()
        tracker.settings["notifications"] = notes
    reminders_on = tk.BooleanVar(value=bool(notes.get("enabled", True)))
    minimize_on_close = tk.BooleanVar(value=bool(notes.get("minimize_on_close", False)))
    start_with_windows = tk.BooleanVar(value=bool(notes.get("start_with_windows", False)))

    def persist_notification_flags() -> None:
        tracker.settings = normalize_notification_settings(tracker.settings)
        tracker.settings["notifications"]["enabled"] = bool(reminders_on.get())
        tracker.settings["notifications"]["minimize_on_close"] = bool(minimize_on_close.get())
        tracker.settings["notifications"]["start_with_windows"] = bool(start_with_windows.get())
        tracker.save_data(flush=True)

    def on_reminders_toggle() -> None:
        persist_notification_flags()

    def on_minimize_toggle() -> None:
        persist_notification_flags()

    def on_autostart_toggle() -> None:
        if not autostart_windows.is_supported():
            start_with_windows.set(False)
            messagebox.showinfo("Start with Windows", "Only available on Windows.", parent=window)
            return
        try:
            autostart_windows.set_enabled(bool(start_with_windows.get()))
        except OSError as exc:
            start_with_windows.set(autostart_windows.is_enabled())
            messagebox.showerror("Start with Windows", str(exc), parent=window)
            return
        persist_notification_flags()

    ttk.Checkbutton(
        inner,
        text="Enable daily reminder toasts (while Integral is running)",
        variable=reminders_on,
        command=on_reminders_toggle,
    ).pack(anchor="w", padx=15, pady=2)
    ttk.Checkbutton(
        inner,
        text="Minimize to taskbar on close (keep reminders running)",
        variable=minimize_on_close,
        command=on_minimize_toggle,
    ).pack(anchor="w", padx=15, pady=2)
    autostart_cb = ttk.Checkbutton(
        inner,
        text="Start Integral with Windows",
        variable=start_with_windows,
        command=on_autostart_toggle,
    )
    autostart_cb.pack(anchor="w", padx=15, pady=2)
    if not autostart_windows.is_supported():
        autostart_cb.state(["disabled"])

    ttk.Label(
        inner, text="Practice reminders", font=("Helvetica", 12, "bold")
    ).pack(anchor="w", padx=15, pady=(10, 2))
    ttk.Label(
        inner,
        text="Nudges for specific routines (e.g. \"Five Tibetan Rites + 10 min breathing\"). "
        "Each fires once per day at its time while Integral is running.",
        wraplength=500,
        style="Muted.TLabel",
    ).pack(anchor="w", padx=15, pady=(0, 6))

    practice_list = ttk.Frame(inner)
    practice_list.pack(fill=tk.X, padx=15, pady=(0, 4))

    def refresh_practice_reminders() -> None:
        for child in practice_list.winfo_children():
            child.destroy()
        tracker.settings = normalize_notification_settings(tracker.settings)
        reminders = tracker.settings["notifications"].get("practice_reminders") or []
        if not reminders:
            ttk.Label(
                practice_list, text="No practice reminders yet.", style="Muted.TLabel"
            ).pack(anchor="w")
            return
        for index, reminder in enumerate(reminders):
            row = ttk.Frame(practice_list)
            row.pack(fill=tk.X, pady=1)
            state = "" if reminder.get("enabled", True) else " (off)"
            ttk.Label(
                row, text=f"{reminder['time']}  —  {reminder['label']}{state}"
            ).pack(side=tk.LEFT)
            ttk.Button(
                row,
                text="Remove",
                width=8,
                command=lambda i=index: remove_practice_reminder(i),
            ).pack(side=tk.RIGHT)

    def remove_practice_reminder(index: int) -> None:
        tracker.settings = normalize_notification_settings(tracker.settings)
        reminders = list(tracker.settings["notifications"].get("practice_reminders") or [])
        if 0 <= index < len(reminders):
            reminders.pop(index)
            tracker.settings["notifications"]["practice_reminders"] = reminders
            tracker.save_data(flush=True)
        refresh_practice_reminders()

    add_row = ttk.Frame(inner)
    add_row.pack(fill=tk.X, padx=15, pady=(2, 4))
    new_label = tk.StringVar()
    new_time = tk.StringVar(value="07:00")
    ttk.Entry(add_row, textvariable=new_label, width=32).pack(side=tk.LEFT)
    ttk.Label(add_row, text="at").pack(side=tk.LEFT, padx=4)
    ttk.Entry(add_row, textvariable=new_time, width=7).pack(side=tk.LEFT)

    def add_practice_reminder() -> None:
        label = new_label.get().strip()
        time_value = new_time.get().strip()
        if not label:
            messagebox.showinfo("Practice reminder", "Enter a practice name.", parent=window)
            return
        tracker.settings = normalize_notification_settings(tracker.settings)
        reminders = list(tracker.settings["notifications"].get("practice_reminders") or [])
        reminders.append({"label": label, "time": time_value, "enabled": True})
        tracker.settings["notifications"]["practice_reminders"] = reminders
        tracker.settings = normalize_notification_settings(tracker.settings)
        if not any(
            r["label"] == label for r in tracker.settings["notifications"]["practice_reminders"]
        ):
            messagebox.showinfo(
                "Practice reminder", "Use a valid time as HH:MM (24h).", parent=window
            )
            return
        tracker.save_data(flush=True)
        new_label.set("")
        refresh_practice_reminders()

    ttk.Button(add_row, text="Add", width=6, command=add_practice_reminder).pack(
        side=tk.LEFT, padx=6
    )
    refresh_practice_reminders()

    ttk.Separator(inner, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=15, pady=12)
    ttk.Label(inner, text="Quick Capture", font=("Helvetica", 13, "bold")).pack(
        anchor="w", padx=15, pady=(4, 4)
    )
    ttk.Label(
        inner,
        text="Optional always-on-top panel for parking links into a life domain or starting a "
        "journal thought while you browse. Off by default — when off, no overlay and no "
        "YouTube title lookups.",
        wraplength=500,
        style="Muted.TLabel",
    ).pack(anchor="w", padx=15, pady=(0, 8))

    tracker.settings = quick_capture.apply_quick_capture_settings(
        tracker.settings,
        quick_capture.normalize_quick_capture_settings(tracker.settings),
    )
    capture_on = tk.BooleanVar(value=quick_capture.is_quick_capture_enabled(tracker.settings))

    def on_quick_capture_toggle() -> None:
        tracker.set_quick_capture_enabled(bool(capture_on.get()), persist=True)

    ttk.Checkbutton(
        inner,
        text="Enable Quick Capture panel (always on top)",
        variable=capture_on,
        command=on_quick_capture_toggle,
    ).pack(anchor="w", padx=15, pady=2)

    ttk.Separator(inner, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=15, pady=12)
    ttk.Label(inner, text="OS deep links", font=("Helvetica", 13, "bold")).pack(
        anchor="w", padx=15, pady=(4, 4)
    )
    ttk.Label(
        inner,
        text="Register integral:// so links like integral://journal/{id} pasted in a browser, "
        "chat, or notes app open Integral to that journal entry. Uses your user account only (HKCU).",
        wraplength=500,
        style="Muted.TLabel",
    ).pack(anchor="w", padx=15, pady=(0, 8))

    protocol_on = tk.BooleanVar(
        value=bool(tracker.settings.get("os_protocol_enabled", protocol_windows.is_registered()))
    )
    if protocol_windows.is_supported():
        protocol_on.set(protocol_windows.is_registered())

    def on_protocol_toggle() -> None:
        if not protocol_windows.is_supported():
            protocol_on.set(False)
            messagebox.showinfo("OS deep links", "Only available on Windows.", parent=window)
            return
        try:
            protocol_windows.set_registered(bool(protocol_on.get()))
        except OSError as exc:
            protocol_on.set(protocol_windows.is_registered())
            messagebox.showerror("OS deep links", str(exc), parent=window)
            return
        tracker.settings["os_protocol_enabled"] = bool(protocol_on.get())
        tracker.save_data(flush=True)

    protocol_cb = ttk.Checkbutton(
        inner,
        text="Register integral:// protocol with Windows",
        variable=protocol_on,
        command=on_protocol_toggle,
    )
    protocol_cb.pack(anchor="w", padx=15, pady=2)
    if not protocol_windows.is_supported():
        protocol_cb.state(["disabled"])

    def send_test() -> None:
        ok = show_windows_notification(APP_NAME, "Test notification from Integral — reminders are working.")
        if ok:
            messagebox.showinfo("Test notification", "Toast dispatched. If you did not see it, check Windows notification settings for Integral / PowerShell.", parent=window)
        else:
            messagebox.showwarning(
                "Test notification",
                "Could not send a Windows toast from this session (non-Windows or blocked).",
                parent=window,
            )

    rem_buttons = ttk.Frame(inner)
    rem_buttons.pack(fill=tk.X, padx=15, pady=(10, 8))
    ttk.Button(rem_buttons, text="Send test notification", command=send_test).pack(side=tk.LEFT)
    ttk.Button(
        rem_buttons,
        text="Quit Integral completely",
        command=lambda: (window.destroy(), tracker.quit_app()),
    ).pack(side=tk.LEFT, padx=8)

    footer = ttk.Frame(window, padding=(15, 8, 15, 12))
    footer.pack(side=tk.BOTTOM, fill=tk.X)
    ttk.Button(footer, text="Close", command=window.destroy).pack(side=tk.RIGHT)


def prompt_vault_unlock(tracker: PersonalDevelopmentTracker) -> bool:
    if not is_encrypted_file(tracker.data_path):
        return True
    for _attempt in range(3):
        passphrase = simpledialog.askstring(
            "Unlock Integral",
            "Enter your journal passphrase:",
            show="*",
            parent=tracker.root,
        )
        if passphrase is None:
            return False
        try:
            from vault import decrypt_payload
            import json

            with open(tracker.data_path, encoding="utf-8") as handle:
                envelope = json.load(handle)
            decrypt_payload(envelope, passphrase)
            tracker.vault_passphrase = passphrase
            return True
        except Exception:  # noqa: BLE001
            messagebox.showerror("Unlock failed", "Incorrect passphrase.")
    return False


def show_onboarding(tracker: PersonalDevelopmentTracker, on_done: Callable[[], None] | None = None) -> None:
    window = tk.Toplevel(tracker.root)
    window.title("Welcome to Integral")
    window.geometry("640x520")
    window.minsize(480, 400)
    window.configure(bg=tracker.theme["bg"])
    window.transient(tracker.root)
    window.grab_set()

    footer = ttk.Frame(window, padding=(0, 16))
    footer.pack(side=tk.BOTTOM, fill=tk.X)

    ttk.Label(window, text="Tend every area of your life.", font=("Helvetica", 18, "bold")).pack(
        side=tk.TOP, anchor="w", padx=20, pady=(20, 8)
    )
    body = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Helvetica", 11), height=14)
    style_text_widget(body, tracker.theme)
    body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=8)
    body.insert(
        tk.END,
        "Integral is free, open-source software — your data stays on this machine.\n\n"
        "Integral tracks development across the whole person — financial, physical, mental, "
        "emotional, spiritual, relational, cultural, and what you take in (food, art, books, content).\n\n"
        "Daily logging (keep it light):\n"
        "  • Pick any life area → 1–10 rating → Save. That's enough on hard days.\n"
        "  • You don't need every category every day — log what matters today.\n"
        "  • Add checklist ticks, metrics, and notes when you have energy.\n\n"
        "Overview shows a year-at-a-glance grid — click any day to explore.\n\n"
        "Fitness Hub includes reference tables from popular training books (CC, Tibetan Rites, "
        "Overcoming Gravity, and more). Integral is not sponsored by those authors — "
        "if you love a program, buy the book.\n\n"
        "Use Weekly Summary and Guidance for trends; Export and Backup in the footer when you want copies.\n",
    )
    body.config(state=tk.DISABLED)

    def finish() -> None:
        tracker.settings["onboarding_complete"] = True
        tracker.save_data()
        window.destroy()
        if on_done:
            on_done()

    def start_with_template() -> None:
        show_template_picker(tracker, window)

    ttk.Button(footer, text="Start with a template…", command=start_with_template).pack(
        side=tk.LEFT, padx=(20, 0)
    )
    ttk.Button(footer, text="Get started", command=finish).pack(side=tk.RIGHT, padx=(0, 20))


def show_template_picker(
    tracker: PersonalDevelopmentTracker,
    parent: tk.Misc | None = None,
    *,
    on_apply: Callable[[str], None] | None = None,
) -> tk.Toplevel:
    """Pick and apply a pre-configured domain template.

    When ``on_apply`` is given the caller handles the merge (e.g. into an editor's working
    copy). Otherwise the template is applied directly to ``tracker.categories`` and saved.
    """
    parent = parent or tracker.root
    dlg = tk.Toplevel(parent)
    dlg.title("Apply a template")
    dlg.geometry("560x460")
    dlg.minsize(420, 360)
    dlg.configure(bg=tracker.theme["bg"])
    dlg.transient(parent)
    dlg.grab_set()

    ttk.Label(dlg, text="Apply a domain template", font=FONTS["heading"]).pack(
        anchor="w", padx=16, pady=(16, 4)
    )
    ttk.Label(
        dlg,
        text="Adds a coherent set of Life Domains. Existing domains are never overwritten.",
        style="Muted.TLabel",
        wraplength=500,
    ).pack(anchor="w", padx=16, pady=(0, 8))

    templates = domain_templates.list_templates()
    selected = tk.StringVar(value=templates[0]["id"] if templates else "")

    list_frame = ttk.Frame(dlg)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)
    for template in templates:
        ttk.Radiobutton(
            list_frame,
            text=f"{template['title']}  ({template['domain_count']} domains)",
            value=template["id"],
            variable=selected,
        ).pack(anchor="w", pady=(4, 0))
        ttk.Label(
            list_frame, text=template["description"], style="Muted.TLabel", wraplength=480
        ).pack(anchor="w", padx=24, pady=(0, 6))

    def apply_selected() -> None:
        template_id = selected.get()
        if not template_id:
            return
        if on_apply is not None:
            on_apply(template_id)
            dlg.destroy()
            return
        merged, added, skipped = domain_templates.apply_template(tracker.categories, template_id)
        tracker.categories = merged
        tracker._invalidate_caches()
        tracker.save_data()
        tracker.refresh_dashboard()
        dlg.destroy()
        message = f"Added {len(added)} domain(s)."
        if skipped:
            message += f" Skipped {len(skipped)} already present."
        messagebox.showinfo("Template applied", message, parent=parent)

    controls = ttk.Frame(dlg, padding=12)
    controls.pack(fill=tk.X, side=tk.BOTTOM)
    ttk.Button(controls, text="Apply", style="Accent.TButton", command=apply_selected).pack(
        side=tk.LEFT
    )
    ttk.Button(controls, text="Cancel", command=dlg.destroy).pack(side=tk.RIGHT)
    return dlg
