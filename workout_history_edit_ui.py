"""In-pane editor for saved workout sessions (#286)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from fitness.set_field_validation import (
    SetFieldValidationError,
    format_hold_display,
    format_weight_display,
)
from inline_validation import make_inline_error_label, set_field_error
from progression.db import FitnessRepository
from progression.models import Exercise, WorkoutSession, WorkoutSet
from progression.session_edit import (
    SessionEditError,
    build_session_edit_payload,
    update_saved_workout_session,
)


class WorkoutSessionEditPanel(ttk.Frame):
    """Grid editor for one saved session (no Toplevel)."""

    _FIELD_ORDER = ("exercise", "sets", "reps", "hold", "weight")

    def __init__(
        self,
        parent: tk.Misc,
        repo: FitnessRepository,
        theme: dict,
        *,
        on_saved: Callable[[], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__(parent, style="Surface.TFrame")
        self.repo = repo
        self.theme = theme
        self.on_saved = on_saved
        self.on_cancel = on_cancel
        self._session: WorkoutSession | None = None
        self._exercises: list[Exercise] = []
        self._name_to_id: dict[str, str] = {}
        self._row_widgets: list[dict[str, tk.Misc]] = []
        self._bindings: list[tuple] = []

        toolbar = ttk.Frame(self, style="Surface.TFrame")
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(0, 4))
        self.date_label = ttk.Label(toolbar, text="", style="OnSurfaceSubheading.TLabel")
        self.date_label.pack(side=tk.TOP, anchor=tk.W)

        self.form_error = make_inline_error_label(self, theme)
        self.form_error.pack(side=tk.TOP, anchor=tk.W, fill=tk.X, padx=4)

        self.saved_note = tk.Label(
            self,
            text="",
            fg=theme.get("success", "#059669"),
            bg=theme.get("surface", theme.get("bg", "#FFFFFF")),
            wraplength=520,
            justify=tk.LEFT,
            anchor="w",
        )

        session_fields = ttk.Frame(self, style="Surface.TFrame")
        session_fields.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)
        self.duration_var = tk.StringVar()
        self.body_weight_var = tk.StringVar()
        self.notes_var = tk.StringVar()
        for label, var in (
            ("Duration (min)", self.duration_var),
            ("Body weight (kg)", self.body_weight_var),
        ):
            row = ttk.Frame(session_fields, style="Surface.TFrame")
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"{label}:", width=14).pack(side=tk.LEFT)
            ttk.Entry(row, textvariable=var, width=12).pack(side=tk.LEFT, fill=tk.X, expand=True)

        notes_row = ttk.Frame(session_fields, style="Surface.TFrame")
        notes_row.pack(fill=tk.X, pady=2)
        ttk.Label(notes_row, text="Notes:", width=14).pack(side=tk.LEFT, anchor=tk.N)
        notes_entry = ttk.Entry(notes_row, textvariable=self.notes_var)
        notes_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(
            self,
            text="Changing the exercise name only changes this row, not the catalog.",
            style="OnSurfaceMuted.TLabel",
            wraplength=520,
        ).pack(side=tk.TOP, anchor=tk.W, padx=4, pady=(0, 4))

        header = ttk.Frame(self, style="Surface.TFrame")
        header.pack(side=tk.TOP, fill=tk.X, padx=2)
        for col, width in (
            ("Exercise", 22),
            ("Sets", 5),
            ("Reps", 5),
            ("Hold", 6),
            ("Weight", 7),
        ):
            ttk.Label(header, text=col, width=width).pack(side=tk.LEFT, padx=1)

        self.rows_frame = ttk.Frame(self, style="Surface.TFrame")
        self.rows_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=2)

        btn_row = ttk.Frame(self, style="Surface.TFrame")
        btn_row.pack(side=tk.TOP, fill=tk.X, padx=4, pady=8)
        self.save_btn = ttk.Button(btn_row, text="Save", style="Accent.TButton", command=self._on_save)
        self.save_btn.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT)

        self._register_shortcuts()

    def _register_shortcuts(self) -> None:
        top = self.winfo_toplevel()
        self._bindings.append((top, "<Control-s>", self._ctrl_s))
        self._bindings.append((top, "<Control-S>", self._ctrl_s))
        self._bindings.append((self, "<Escape>", self._on_cancel_event))
        for widget, seq, handler in self._bindings:
            widget.bind(seq, handler, add="+")

    def unload_shortcuts(self) -> None:
        for widget, seq, _handler in self._bindings:
            try:
                widget.unbind(seq)
            except tk.TclError:
                pass
        self._bindings.clear()

    def _ctrl_s(self, _event=None) -> str:
        self._on_save()
        return "break"

    def _on_cancel_event(self, _event=None) -> str:
        self._on_cancel()
        return "break"

    def load_session(self, session: WorkoutSession, sets: list[WorkoutSet]) -> None:
        self._session = session
        self._exercises = self.repo.list_exercises()
        self._name_to_id = {ex.name: ex.id for ex in self._exercises}
        self.date_label.config(text=session.date)
        self.duration_var.set(str(session.duration_minutes or ""))
        self.body_weight_var.set(format_weight_display(session.body_weight_kg))
        self.notes_var.set(session.notes or "")
        set_field_error(self.form_error, None)
        self.saved_note.pack_forget()
        self.saved_note.config(text="")

        for child in self.rows_frame.winfo_children():
            child.destroy()
        self._row_widgets.clear()

        exercise_names = {ex.id: ex.name for ex in self._exercises}
        combo_values = [ex.name for ex in self._exercises]
        for wset in sets:
            row = ttk.Frame(self.rows_frame, style="Surface.TFrame")
            row.pack(fill=tk.X, pady=1)
            ex_var = tk.StringVar(value=exercise_names.get(wset.exercise_id, ""))
            combo = ttk.Combobox(
                row,
                textvariable=ex_var,
                values=combo_values,
                width=20,
                state="normal",
            )
            combo.pack(side=tk.LEFT, padx=1)
            sets_var = tk.StringVar(value=str(wset.sets or ""))
            reps_var = tk.StringVar(value=str(wset.reps or ""))
            hold_var = tk.StringVar(value=format_hold_display(wset.hold_seconds))
            weight_var = tk.StringVar(value=format_weight_display(wset.weight_kg))
            widgets: dict[str, tk.Misc] = {
                "set_id": wset.id,
                "ordinal": wset.ordinal,
                "exercise": combo,
                "sets": ttk.Entry(row, textvariable=sets_var, width=4),
                "reps": ttk.Entry(row, textvariable=reps_var, width=4),
                "hold": ttk.Entry(row, textvariable=hold_var, width=5),
                "weight": ttk.Entry(row, textvariable=weight_var, width=6),
            }
            widgets["sets"].pack(side=tk.LEFT, padx=1)
            widgets["reps"].pack(side=tk.LEFT, padx=1)
            widgets["hold"].pack(side=tk.LEFT, padx=1)
            widgets["weight"].pack(side=tk.LEFT, padx=1)
            widgets["vars"] = {
                "exercise": ex_var,
                "sets": sets_var,
                "reps": reps_var,
                "hold": hold_var,
                "weight": weight_var,
            }
            self._wire_row_navigation(widgets)
            self._row_widgets.append(widgets)

    def _wire_row_navigation(self, widgets: dict) -> None:
        row_index = len(self._row_widgets)

        def bind_field(field: str, widget: tk.Misc) -> None:
            def on_return(_event) -> str:
                self._focus_field(row_index + 1, field)
                return "break"

            def on_up(_event) -> str:
                self._focus_field(row_index - 1, field)
                return "break"

            def on_down(_event) -> str:
                self._focus_field(row_index + 1, field)
                return "break"

            widget.bind("<Return>", on_return, add="+")
            widget.bind("<Up>", on_up, add="+")
            widget.bind("<Down>", on_down, add="+")

        bind_field("exercise", widgets["exercise"])
        for key in ("sets", "reps", "hold", "weight"):
            bind_field(key, widgets[key])

    def _focus_field(self, row_index: int, field: str) -> None:
        if row_index < 0 or row_index >= len(self._row_widgets):
            return
        widget = self._row_widgets[row_index].get(field)
        if widget is not None:
            try:
                widget.focus_set()
                if isinstance(widget, ttk.Combobox):
                    widget.event_generate("<Button-1>")
            except tk.TclError:
                pass

    def _collect_rows(self) -> list[dict]:
        rows: list[dict] = []
        for widgets in self._row_widgets:
            vars_map = widgets["vars"]
            rows.append(
                {
                    "set_id": widgets["set_id"],
                    "exercise_name": vars_map["exercise"].get(),
                    "sets": vars_map["sets"].get(),
                    "reps": vars_map["reps"].get(),
                    "hold": vars_map["hold"].get(),
                    "weight": vars_map["weight"].get(),
                }
            )
        return rows

    def _on_save(self) -> None:
        if not self._session:
            return
        set_field_error(self.form_error, None)
        self.saved_note.pack_forget()
        try:
            payload = build_session_edit_payload(
                self.repo,
                self._session.id,
                notes_text=self.notes_var.get(),
                duration_text=self.duration_var.get(),
                body_weight_text=self.body_weight_var.get(),
                set_rows=self._collect_rows(),
            )
            update_saved_workout_session(self.repo, payload)
        except SetFieldValidationError as exc:
            set_field_error(self.form_error, str(exc))
            return
        except SessionEditError:
            set_field_error(self.form_error, "Could not save changes.")
            return
        except ValueError:
            set_field_error(self.form_error, "Could not save changes.")
            return
        except Exception as exc:
            from progression.sessions import fitness_db_file_label, is_fitness_db_lock_error

            if is_fitness_db_lock_error(exc):
                set_field_error(
                    self.form_error,
                    f"Database is busy. Close other apps using {fitness_db_file_label(self.repo)} and try again.",
                )
            else:
                set_field_error(self.form_error, "Could not save changes.")
            return

        self.saved_note.config(text="Saved changes to this session.")
        self.saved_note.pack(side=tk.TOP, anchor=tk.W, padx=4, pady=(0, 4))
        self.on_saved()

    def _on_cancel(self) -> None:
        set_field_error(self.form_error, None)
        self.on_cancel()