"""Fitness program tracking UI."""



from __future__ import annotations



import tkinter as tk

from datetime import datetime

from tkinter import messagebox, scrolledtext, ttk

from typing import Any, Callable



from fitness.engine import evaluate_session_log, load_program_definitions, compute_program_state

from fitness.intelligence import find_personal_records, get_last_program_session, smart_defaults_for_program

from fitness_graphs import open_fitness_graphs

from theme import style_text_widget





SaveCallback = Callable[[], None]





class FitnessHub:

    def __init__(

        self,

        parent: tk.Misc,

        *,

        sessions: list[dict],

        program_state: dict,

        programs: dict[str, dict] | None = None,

        settings: dict | None = None,

        theme: dict,

        on_save: SaveCallback,

    ) -> None:

        self.parent = parent

        self.sessions = sessions

        self.program_state = program_state

        self.settings = settings or {}

        self.theme = theme

        self.on_save = on_save

        self.programs = programs or load_program_definitions()



        self.window = tk.Toplevel(parent)

        self.window.title("Fitness Hub — Multi-Program Tracking")

        self.window.geometry("1000x720")

        self.window.configure(bg=theme["bg"])

        self.window.transient(parent)



        header = ttk.Frame(self.window)

        header.pack(fill=tk.X, padx=15, pady=12)

        ttk.Label(

            header,

            text="Fitness Programs",

            font=("Helvetica", 18, "bold"),

        ).pack(side=tk.LEFT)

        ttk.Button(header, text="Fitness Charts", command=self._open_charts).pack(side=tk.RIGHT, padx=6)

        ttk.Button(header, text="Session History", command=self._show_history).pack(side=tk.RIGHT)



        body = ttk.Frame(self.window)

        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        body.columnconfigure(0, weight=1)



        for row, (program_id, program) in enumerate(self.programs.items()):

            card = self._program_card(body, program_id, program)

            card.grid(row=row, column=0, sticky="ew", pady=8)



        footer = ttk.Frame(self.window)

        footer.pack(fill=tk.X, padx=15, pady=10)

        ttk.Button(footer, text="Log New Session", command=self._open_log_dialog).pack(side=tk.LEFT)

        ttk.Button(footer, text="Repeat Last Session", command=self._repeat_last_session).pack(side=tk.LEFT, padx=8)

        ttk.Button(footer, text="Close", command=self.window.destroy).pack(side=tk.RIGHT)



    def _open_charts(self) -> None:

        open_fitness_graphs(self.window, self.sessions, self.programs, self.theme, settings=self.settings)



    def _show_history(self) -> None:

        window = tk.Toplevel(self.window)

        window.title("Fitness Session History")

        window.geometry("900x600")

        window.configure(bg=self.theme["bg"])

        text = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Consolas", 10))

        style_text_widget(text, self.theme)

        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)



        if not self.sessions:

            text.insert(tk.END, "No fitness sessions logged yet.")

            return



        for session in sorted(self.sessions, key=lambda item: item["date"], reverse=True):

            program = self.programs.get(session.get("program_id", ""), {})

            text.insert(tk.END, f"\n{'=' * 55}\n{session['date']} — {program.get('name', session.get('program_id'))}\n")

            if session.get("session_rpe"):

                text.insert(tk.END, f"RPE: {session['session_rpe']}")

                if session.get("duration_min"):

                    text.insert(tk.END, f"  |  {session['duration_min']} min")

                text.insert(tk.END, "\n")

            if session.get("notes"):

                text.insert(tk.END, f"Notes: {session['notes']}\n")

            for log in session.get("movement_logs", []):

                text.insert(tk.END, f"  {self._format_log(program, log)}\n")



    def _format_log(self, program: dict, log: dict) -> str:

        model = program.get("progression_model", "")

        if model == "weekly_rep_ramp":

            reps = log.get("reps_per_rite", {})

            target = log.get("target_reps", "?")

            parts = [f"{rite}: {reps.get(rite, 0)}" for rite in reps]

            cycle = log.get("cycle_duration_sec")

            extra = f", cycle {cycle}s" if cycle else ""

            return f"Target {target} — " + ", ".join(parts) + extra

        if model == "parc_step":

            reps = log.get("reps_per_set", [])

            rep_str = "/".join(str(value) for value in reps) if reps else ""

            height = log.get("height_cm")

            extra = f", height {height} cm" if height else ""

            return f"{log.get('chain_name', log.get('chain_key'))} step {log.get('step')} ({log.get('step_name')}) sets: {rep_str}{extra}"

        reps = log.get("reps_per_set", [])

        hold = log.get("hold_seconds")

        detail = f"hold {hold}s" if hold is not None else f"sets {'/'.join(str(v) for v in reps)}"

        return f"{log.get('movement_name', log.get('movement_key'))} step {log.get('step')} ({log.get('step_name')}) {detail}"



    def _program_card(self, parent: ttk.Frame, program_id: str, program: dict) -> ttk.Frame:

        frame = ttk.Frame(parent, borderwidth=2, relief="groove", padding=12)

        frame.columnconfigure(1, weight=1)



        ttk.Label(frame, text=program["name"], font=("Helvetica", 14, "bold")).grid(

            row=0, column=0, columnspan=2, sticky="w"

        )

        ttk.Label(frame, text=program.get("source", ""), wraplength=700).grid(

            row=1, column=0, columnspan=2, sticky="w", pady=(2, 8)

        )



        state = self.program_state.get(program_id, {})

        summary_lines = self._summarize_program(program, state)

        ttk.Label(frame, text=summary_lines, justify=tk.LEFT, wraplength=760).grid(

            row=2, column=0, columnspan=2, sticky="w"

        )



        ready = self._advancement_messages(program, state)

        if ready:

            ttk.Label(frame, text=ready, style="Accent.TLabel", wraplength=760).grid(

                row=3, column=0, columnspan=2, sticky="w", pady=(6, 0)

            )



        next_actions = self._next_action_lines(program, state)

        if next_actions:

            ttk.Label(frame, text=next_actions, wraplength=760).grid(

                row=4, column=0, columnspan=2, sticky="w", pady=(4, 0)

            )



        btn_row = ttk.Frame(frame)

        btn_row.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))

        ttk.Button(

            btn_row,

            text=f"Log {program['name']}",

            command=lambda pid=program_id: self._open_log_dialog(pid),

        ).pack(side=tk.LEFT)

        ttk.Button(

            btn_row,

            text="Program detail",

            command=lambda pid=program_id: self._show_program_detail(pid),

        ).pack(side=tk.LEFT, padx=8)

        return frame



    def _next_action_lines(self, program: dict, state: dict) -> str:

        model = program["progression_model"]

        if model == "weekly_rep_ramp":

            action = state.get("next_action")

            return f"Next: {action}" if action else ""

        lines = []

        if isinstance(state, dict):

            for key, item in state.items():

                if isinstance(item, dict) and item.get("next_action"):

                    label = key.replace("-", " ").title()

                    lines.append(f"{label}: {item['next_action']}")

        return "\n".join(lines[:3])



    def _summarize_program(self, program: dict, state: dict) -> str:

        model = program["progression_model"]

        if model == "weekly_rep_ramp":

            week = state.get("current_week", 1)

            target = state.get("target_reps", program["rules"]["start_reps_per_rite"])

            streak = state.get("consecutive_days", 0)

            return (

                f"Week {week} — target: {target} reps per rite (Kelder/Bradford ramp to 21)\n"

                f"Consecutive success days: {streak}"

            )

        if model == "parc_step":

            lines = []

            for chain in program.get("chains", []):

                chain_state = state.get(chain["id"], {})

                step = chain_state.get("current_step", 1)

                name = chain_state.get("step_name", chain["steps"][0]["name"])

                trend = chain_state.get("trend", "—")

                met = chain_state.get("sessions_meeting_standard")

                extra = f", {met} sessions at standard" if met is not None else ""

                lines.append(f"{chain['name']}: Step {step} ({name}) — {trend}{extra}")

            return "\n".join(lines) if lines else "No sessions yet — start at Step 1 on each chain."

        lines = []

        for movement in program.get("movements", []):

            chart = movement.get("chart")

            prefix = f"[{chart}] " if chart else ""

            movement_state = state.get(movement["id"], {})

            step = movement_state.get("current_step", 1)

            name = movement_state.get("step_name", movement["steps"][0]["name"])

            trend = movement_state.get("trend", "—")

            met = movement_state.get("sessions_meeting_standard")

            extra = f", {met} sessions at standard" if met is not None else ""

            lines.append(f"{prefix}{movement['name']}: Step {step} ({name}) — {trend}{extra}")

        if not lines:

            return f"Reference library — {len(program.get('movements', []))} exercise ladders. Open Program detail."

        if len(lines) > 6:

            return "\n".join(lines[:6]) + f"\n… +{len(lines) - 6} more (see Program detail)"

        return "\n".join(lines)



    def _advancement_messages(self, program: dict, state: dict) -> str:

        model = program["progression_model"]

        messages: list[str] = []

        if model == "weekly_rep_ramp" and state.get("ready_to_advance"):

            messages.append("All rites met target — eligible for +2 reps next week.")

        elif model in ("step_ladder", "parc_step"):

            for item in state.values() if isinstance(state, dict) else []:

                if isinstance(item, dict) and item.get("ready_to_advance"):

                    messages.extend(item.get("messages", ["Ready to advance"]))

        return " | ".join(messages)



    def _show_program_detail(self, program_id: str) -> None:

        program = self.programs[program_id]

        state = self.program_state.get(program_id, {})

        window = tk.Toplevel(self.window)

        window.title(f"{program['name']} — rules & progress")

        window.geometry("640x520")

        window.configure(bg=self.theme["bg"])



        text = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Helvetica", 11))

        style_text_widget(text, self.theme)

        text.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)



        text.insert(tk.END, f"{program.get('description', '')}\n\n")

        text.insert(tk.END, f"Source: {program.get('source', '')}\n")

        text.insert(tk.END, f"Progression: {program['progression_model']}\n")

        if program.get("program_type") == "reference":

            text.insert(tk.END, "Type: Reference library (official progressions for lookup & logging)\n")

        if program.get("notation"):

            text.insert(tk.END, f"Notation: {program['notation']}\n")

        if program.get("rules"):

            text.insert(tk.END, "\nProgram rules:\n")

            for key, value in program["rules"].items():

                text.insert(tk.END, f"  {key}: {value}\n")

        if program.get("charts"):

            text.insert(tk.END, "\nCharts:\n")

            for chart in program["charts"]:

                text.insert(tk.END, f"  • {chart.get('name', chart.get('id'))}: {chart.get('emphasis', '')}\n")

        if program.get("reference_sections"):

            text.insert(tk.END, "\nReference sections:\n")

            for section in program["reference_sections"]:

                text.insert(tk.END, f"  {section.get('name', section.get('id'))}\n")

                if section.get("summary"):

                    text.insert(tk.END, f"    {section['summary']}\n")

        text.insert(tk.END, "\n")



        if program["progression_model"] == "weekly_rep_ramp":

            text.insert(tk.END, "Official weekly schedule:\n")

            for entry in program.get("weekly_schedule", []):

                text.insert(tk.END, f"  Week {entry['week']}: {entry['reps_per_rite']} reps/rite\n")

            evidence = state.get("evidence", [])

            if evidence:

                text.insert(tk.END, "\nAdvancement evidence:\n")

                for line in evidence:

                    text.insert(tk.END, f"  {line}\n")

        elif program["progression_model"] == "parc_step":

            for chain in program.get("chains", []):

                chain_state = state.get(chain["id"], {})

                text.insert(tk.END, f"\n{chain['name']} — step {chain_state.get('current_step', 1)}\n")

                for line in chain_state.get("evidence", []):

                    text.insert(tk.END, f"  {line}\n")

        else:

            for movement in program.get("movements", []):

                movement_state = state.get(movement["id"], {})

                text.insert(tk.END, f"\n{movement['name']} — step {movement_state.get('current_step', 1)}\n")

                for line in movement_state.get("evidence", []):

                    text.insert(tk.END, f"  {line}\n")



        records = find_personal_records(self.sessions, program_id)

        if records:

            text.insert(tk.END, "\nPersonal records:\n")

            for record in records[:8]:

                text.insert(tk.END, f"  {record['date']}: {record['label']} = {record['value']}\n")



    def _repeat_last_session(self) -> None:

        if not self.sessions:

            messagebox.showinfo("No sessions", "Log a session first, then repeat it here.")

            return

        last = sorted(self.sessions, key=lambda item: item["date"])[-1]

        program_id = last.get("program_id")

        if not program_id or program_id not in self.programs:

            messagebox.showwarning("Unknown program", "Could not identify program for last session.")

            return

        copy = {

            "date": datetime.now().strftime("%Y-%m-%d"),

            "program_id": program_id,

            "movement_logs": [dict(log) for log in last.get("movement_logs", [])],

            "notes": last.get("notes", ""),

            "session_rpe": last.get("session_rpe"),

            "duration_min": last.get("duration_min"),

        }

        self.sessions.append(copy)

        self.program_state = compute_program_state(self.programs, self.sessions, self.settings)

        self.on_save()

        messagebox.showinfo("Repeated", f"Copied last {self.programs[program_id]['name']} session for today.")

        self.window.destroy()

        open_fitness_hub(

            self.parent,

            sessions=self.sessions,

            program_state=self.program_state,

            programs=self.programs,

            settings=self.settings,

            theme=self.theme,

            on_save=self.on_save,

        )



    def _open_log_dialog(self, program_id: str | None = None) -> None:

        if not self.programs:

            messagebox.showwarning("No programs", "Program definitions not found in programs/.")

            return



        dialog = tk.Toplevel(self.window)

        dialog.title("Log Fitness Session")

        dialog.geometry("620x820")

        dialog.configure(bg=self.theme["bg"])

        dialog.transient(self.window)

        dialog.grab_set()



        today = datetime.now().strftime("%Y-%m-%d")

        ttk.Label(dialog, text=f"Date: {today}", font=("Helvetica", 11, "bold")).pack(anchor="w", padx=15, pady=8)



        ttk.Label(dialog, text="Program:").pack(anchor="w", padx=15)

        program_var = tk.StringVar(value=program_id or next(iter(self.programs)))

        program_combo = ttk.Combobox(

            dialog,

            textvariable=program_var,

            values=list(self.programs.keys()),

            state="readonly",

            width=40,

        )

        program_combo.pack(anchor="w", padx=15, pady=4)



        meta = ttk.Frame(dialog)

        meta.pack(fill=tk.X, padx=15, pady=4)

        ttk.Label(meta, text="Session RPE (1-10):").pack(side=tk.LEFT)

        rpe_var = tk.IntVar(value=7)

        ttk.Spinbox(meta, from_=1, to=10, textvariable=rpe_var, width=5).pack(side=tk.LEFT, padx=6)

        ttk.Label(meta, text="Duration (min):").pack(side=tk.LEFT, padx=(12, 0))

        duration_var = tk.IntVar(value=20)

        ttk.Spinbox(meta, from_=5, to=180, textvariable=duration_var, width=6).pack(side=tk.LEFT, padx=6)



        form_frame = ttk.Frame(dialog)

        form_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)



        notes_label = ttk.Label(dialog, text="Session notes")

        notes_text = scrolledtext.ScrolledText(dialog, height=5, wrap=tk.WORD)

        style_text_widget(notes_text, self.theme)



        field_widgets: dict[str, Any] = {}



        def rebuild_form(*_args: object) -> None:

            for child in form_frame.winfo_children():

                child.destroy()

            field_widgets.clear()

            program = self.programs[program_var.get()]

            defaults = smart_defaults_for_program(program, self.sessions, self.program_state)

            rpe_var.set(int(defaults.get("session_rpe", 7)))

            duration_var.set(int(defaults.get("duration_min", 20)))

            model = program["progression_model"]

            if model == "weekly_rep_ramp":

                self._build_tibetan_form(form_frame, program, field_widgets, defaults)

            elif model == "parc_step":

                self._build_parc_form(form_frame, program, field_widgets, defaults)

            else:

                self._build_cc_form(form_frame, program, field_widgets, defaults)



        program_var.trace_add("write", rebuild_form)

        rebuild_form()



        notes_label.pack(anchor="w", padx=15)

        notes_text.pack(fill=tk.X, padx=15, pady=4)



        def save_session() -> None:

            program = self.programs[program_var.get()]

            movement_logs = self._collect_logs(program, field_widgets)

            if not movement_logs:

                messagebox.showwarning("Missing data", "Add at least one movement log.")

                return

            session = {

                "date": today,

                "program_id": program["id"],

                "movement_logs": movement_logs,

                "notes": notes_text.get("1.0", tk.END).strip(),

                "session_rpe": rpe_var.get(),

                "duration_min": duration_var.get(),

            }

            self.sessions.append(session)

            self.program_state = compute_program_state(self.programs, self.sessions, self.settings)

            self.on_save()

            dialog.destroy()



            state = self.program_state.get(program["id"], {})

            hints: list[str] = []

            for log in movement_logs:

                result = evaluate_session_log(log, program)

                if result.get("ready_to_advance"):

                    hints.extend(result.get("messages", []))



            if program["progression_model"] == "weekly_rep_ramp" and state.get("ready_to_advance"):

                evidence = state.get("evidence", [])

                detail = "\n".join(evidence) if evidence else ""

                if messagebox.askyesno("Advance reps?", f"Standards met.\n\n{detail}\n\nRecord +2 reps for next week?"):

                    self._apply_tibetan_advance(program)

            elif program["progression_model"] in ("step_ladder", "parc_step"):

                for key, item in (state.items() if isinstance(state, dict) else []):

                    if isinstance(item, dict) and item.get("ready_to_advance"):

                        evidence = "\n".join(item.get("evidence", []))

                        if messagebox.askyesno(

                            "Advance step?",

                            f"{key}: standards met.\n\n{evidence}\n\nLog next step on your next session?",

                        ):

                            hints.append(f"Next session: try step {item.get('current_step', 1) + 1}")



            if hints:

                messagebox.showinfo("Advancement", "\n".join(hints))

            else:

                messagebox.showinfo("Saved", "Fitness session logged.")

            self.window.destroy()

            open_fitness_hub(

                self.parent,

                sessions=self.sessions,

                program_state=self.program_state,

                programs=self.programs,

                settings=self.settings,

                theme=self.theme,

                on_save=self.on_save,

            )



        btns = ttk.Frame(dialog)

        btns.pack(pady=12)

        ttk.Button(btns, text="Save Session", command=save_session).pack(side=tk.LEFT, padx=8)

        ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)



    def _apply_tibetan_advance(self, program: dict) -> None:

        last = get_last_program_session(self.sessions, program["id"])

        if not last:

            return

        for log in last.get("movement_logs", []):

            current = int(log.get("target_reps", program["rules"]["start_reps_per_rite"]))

            log["target_reps"] = min(current + 2, program["rules"]["target_reps_per_rite"])

        self.program_state = compute_program_state(self.programs, self.sessions, self.settings)

        self.on_save()



    def _build_cc_form(

        self,

        parent: ttk.Frame,

        program: dict,

        fields: dict,

        defaults: dict,

    ) -> None:

        movement_default = defaults.get("movement_key", program["movements"][0]["id"])

        ttk.Label(parent, text="Movement:").grid(row=0, column=0, sticky="w", pady=4)

        movement_var = tk.StringVar(value=movement_default)

        movement_combo = ttk.Combobox(

            parent,

            textvariable=movement_var,

            values=[movement["id"] for movement in program["movements"]],

            state="readonly",

            width=30,

        )

        movement_combo.grid(row=0, column=1, sticky="w", pady=4)



        ttk.Label(parent, text="Step:").grid(row=1, column=0, sticky="w", pady=4)

        step_var = tk.IntVar(value=int(defaults.get("step", 1)))

        ttk.Spinbox(parent, from_=1, to=10, textvariable=step_var, width=6).grid(row=1, column=1, sticky="w", pady=4)



        standards_label = ttk.Label(parent, text="", wraplength=480)

        standards_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=4)



        reps_default = ",".join(str(value) for value in defaults.get("reps_per_set", [10, 10, 10]))

        ttk.Label(parent, text="Reps per set (comma-separated):").grid(row=3, column=0, sticky="w", pady=4)

        reps_var = tk.StringVar(value=reps_default)

        ttk.Entry(parent, textvariable=reps_var, width=24).grid(row=3, column=1, sticky="w", pady=4)



        hold_default = defaults.get("hold_seconds")

        ttk.Label(parent, text="OR hold seconds:").grid(row=4, column=0, sticky="w", pady=4)

        hold_var = tk.StringVar(value=str(hold_default) if hold_default is not None else "")

        ttk.Entry(parent, textvariable=hold_var, width=12).grid(row=4, column=1, sticky="w", pady=4)



        ttk.Label(parent, text="Form quality (1-10):").grid(row=5, column=0, sticky="w", pady=4)

        form_var = tk.IntVar(value=int(defaults.get("form_quality", 8)))

        ttk.Spinbox(parent, from_=1, to=10, textvariable=form_var, width=6).grid(row=5, column=1, sticky="w", pady=4)



        def update_standards(*_args: object) -> None:

            movement = next(item for item in program["movements"] if item["id"] == movement_var.get())

            step_def = movement["steps"][step_var.get() - 1]

            standards_label.config(

                text=f"Official B/I/P: {step_def['beginner']} | {step_def['intermediate']} | {step_def['progression']}"

            )



        movement_var.trace_add("write", update_standards)

        step_var.trace_add("write", update_standards)

        update_standards()



        fields["cc"] = {

            "movement_var": movement_var,

            "step_var": step_var,

            "reps_var": reps_var,

            "hold_var": hold_var,

            "form_var": form_var,

        }



    def _build_tibetan_form(

        self,

        parent: ttk.Frame,

        program: dict,

        fields: dict,

        defaults: dict,

    ) -> None:

        target = int(defaults.get("target_reps", program["rules"]["start_reps_per_rite"]))

        ttk.Label(

            parent,

            text=f"Official week target: {target} reps per rite (+2/week to 21)",

            font=("Helvetica", 10, "bold"),

        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)



        rite_defaults = defaults.get("reps_per_rite", {})

        rite_vars: dict[str, tk.IntVar] = {}

        for index, rite in enumerate(program["movements"], start=1):

            ttk.Label(parent, text=f"{rite['name']}:").grid(row=index, column=0, sticky="w", pady=3)

            var = tk.IntVar(value=int(rite_defaults.get(rite["id"], target)))

            ttk.Spinbox(parent, from_=0, to=30, textvariable=var, width=6).grid(row=index, column=1, sticky="w", pady=3)

            rite_vars[rite["id"]] = var



        row = len(program["movements"]) + 1

        ttk.Label(parent, text="Cycle duration (sec, optional):").grid(row=row, column=0, sticky="w", pady=4)

        cycle_var = tk.StringVar(value=str(defaults.get("cycle_duration_sec") or ""))

        ttk.Entry(parent, textvariable=cycle_var, width=12).grid(row=row, column=1, sticky="w", pady=4)



        fields["tibetan"] = {"target_reps": target, "rite_vars": rite_vars, "cycle_var": cycle_var}



    def _build_parc_form(

        self,

        parent: ttk.Frame,

        program: dict,

        fields: dict,

        defaults: dict,

    ) -> None:

        chain_default = defaults.get("chain_key", program["chains"][0]["id"])

        ttk.Label(parent, text="Chain:").grid(row=0, column=0, sticky="w", pady=4)

        chain_var = tk.StringVar(value=chain_default)

        ttk.Combobox(

            parent,

            textvariable=chain_var,

            values=[chain["id"] for chain in program["chains"]],

            state="readonly",

            width=30,

        ).grid(row=0, column=1, sticky="w", pady=4)



        ttk.Label(parent, text="Step:").grid(row=1, column=0, sticky="w", pady=4)

        step_var = tk.IntVar(value=int(defaults.get("step", 1)))

        ttk.Spinbox(parent, from_=1, to=10, textvariable=step_var, width=6).grid(row=1, column=1, sticky="w", pady=4)



        standards_label = ttk.Label(parent, text="", wraplength=480)

        standards_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=4)



        reps_default = ",".join(str(value) for value in defaults.get("reps_per_set", [5, 5, 5]))

        ttk.Label(parent, text="Reps per set (comma-separated):").grid(row=3, column=0, sticky="w", pady=4)

        reps_var = tk.StringVar(value=reps_default)

        ttk.Entry(parent, textvariable=reps_var, width=24).grid(row=3, column=1, sticky="w", pady=4)



        height_default = defaults.get("height_cm")

        ttk.Label(parent, text="Height cm (vertical leap only):").grid(row=4, column=0, sticky="w", pady=4)

        height_var = tk.StringVar(value=str(height_default) if height_default is not None else "")

        ttk.Entry(parent, textvariable=height_var, width=12).grid(row=4, column=1, sticky="w", pady=4)



        def update_standards(*_args: object) -> None:

            chain = next(item for item in program["chains"] if item["id"] == chain_var.get())

            step_def = chain["steps"][step_var.get() - 1]

            standards_label.config(

                text=f"Official B/I/P: {step_def['beginner']} | {step_def['intermediate']} | {step_def['progression']}"

            )



        chain_var.trace_add("write", update_standards)

        step_var.trace_add("write", update_standards)

        update_standards()



        fields["parc"] = {

            "chain_var": chain_var,

            "step_var": step_var,

            "reps_var": reps_var,

            "height_var": height_var,

        }



    def _collect_logs(self, program: dict, fields: dict) -> list[dict]:

        model = program["progression_model"]

        if model == "weekly_rep_ramp":

            block = fields.get("tibetan", {})

            log: dict[str, Any] = {

                "target_reps": block.get("target_reps"),

                "reps_per_rite": {rite_id: var.get() for rite_id, var in block.get("rite_vars", {}).items()},

            }

            cycle_raw = block.get("cycle_var", tk.StringVar()).get().strip()

            if cycle_raw:

                try:

                    log["cycle_duration_sec"] = float(cycle_raw)

                except ValueError:

                    pass

            return [log]

        if model == "parc_step":

            block = fields.get("parc", {})

            chain = next(item for item in program["chains"] if item["id"] == block["chain_var"].get())

            step = block["step_var"].get()

            step_def = chain["steps"][step - 1]

            reps = self._parse_reps(block["reps_var"].get())

            log = {

                "chain_key": chain["id"],

                "chain_name": chain["name"],

                "step": step,

                "step_name": step_def["name"],

                "reps_per_set": reps,

            }

            height_raw = block["height_var"].get().strip()

            if height_raw:

                try:

                    log["height_cm"] = float(height_raw)

                except ValueError:

                    pass

            return [log]



        block = fields.get("cc", {})

        movement = next(item for item in program["movements"] if item["id"] == block["movement_var"].get())

        step = block["step_var"].get()

        step_def = movement["steps"][step - 1]

        hold_raw = block["hold_var"].get().strip()

        log = {

            "movement_key": movement["id"],

            "movement_name": movement["name"],

            "step": step,

            "step_name": step_def["name"],

            "form_quality": block["form_var"].get(),

        }

        if hold_raw:

            try:

                log["hold_seconds"] = float(hold_raw)

            except ValueError:

                log["reps_per_set"] = self._parse_reps(block["reps_var"].get())

        else:

            log["reps_per_set"] = self._parse_reps(block["reps_var"].get())

        return [log]



    @staticmethod

    def _parse_reps(raw: str) -> list[int]:

        values: list[int] = []

        for part in raw.split(","):

            part = part.strip()

            if not part:

                continue

            try:

                values.append(int(part))

            except ValueError:

                continue

        return values





def open_fitness_hub(

    parent: tk.Misc,

    *,

    sessions: list[dict],

    program_state: dict,

    programs: dict[str, dict] | None = None,

    settings: dict | None = None,

    theme: dict,

    on_save: SaveCallback,

) -> None:

    FitnessHub(

        parent,

        sessions=sessions,

        program_state=program_state,

        programs=programs,

        settings=settings,

        theme=theme,

        on_save=on_save,

    )


