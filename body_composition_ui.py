"""Body composition logging UI."""

from datetime import datetime

from progression.db import FitnessRepository
from progression.models import BodyCompositionLog


def get_profile_repo() -> FitnessRepository:
    return FitnessRepository()


def format_body_log(log: BodyCompositionLog) -> str:
    parts = [f"{log.date}: {log.weight_kg} kg" if log.weight_kg else f"{log.date}"]
    if log.measurements:
        meas = ", ".join(f"{k}={v}" for k, v in log.measurements.items())
        parts.append(f"({meas})")
    if log.photo_path:
        parts.append(f"[photo: {log.photo_path}]")
    return " ".join(parts)


def show_body_composition_window(root, repo: FitnessRepository | None = None):
    import tkinter as tk
    from tkinter import messagebox, ttk

    repo = repo or get_profile_repo()
    repo.initialize()

    win = tk.Toplevel(root)
    win.title("Body Composition")
    win.geometry("640x520")
    win.transient(root)

    header = ttk.Frame(win, padding=10)
    header.pack(fill=tk.X)
    ttk.Label(header, text="Body Composition Log", font=("Helvetica", 14, "bold")).pack(anchor="w")
    ttk.Label(
        header,
        text="Track weight and measurements locally. Photos store a file path reference only.",
    ).pack(anchor="w", pady=4)

    list_frame = ttk.Frame(win, padding=10)
    list_frame.pack(fill=tk.BOTH, expand=True)

    columns = ("date", "weight", "measurements")
    tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)
    tree.heading("date", text="Date")
    tree.heading("weight", text="Weight (kg)")
    tree.heading("measurements", text="Measurements")
    tree.column("date", width=100)
    tree.column("weight", width=90, anchor="center")
    tree.column("measurements", width=380)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)

    import ui_scroll

    ui_scroll.configure_treeview_scroll(tree)

    def refresh():
        for item in tree.get_children():
            tree.delete(item)
        for log in repo.list_body_composition_logs():
            meas = ", ".join(f"{k}: {v}" for k, v in log.measurements.items())
            tree.insert(
                "",
                tk.END,
                iid=log.id,
                values=(log.date, log.weight_kg or "", meas),
            )

    def open_log_dialog():
        dialog = tk.Toplevel(win)
        dialog.title("Log Body Composition")
        dialog.geometry("400x400")
        dialog.transient(win)
        dialog.grab_set()

        import ui_scroll

        outer, inner, _canvas = ui_scroll.make_scrollable_frame(dialog)
        outer.pack(fill=tk.BOTH, expand=True)

        today = datetime.now().strftime("%Y-%m-%d")
        date_var = tk.StringVar(value=today)
        weight_var = tk.DoubleVar(value=0.0)
        waist_var = tk.DoubleVar(value=0.0)
        chest_var = tk.DoubleVar(value=0.0)
        hips_var = tk.DoubleVar(value=0.0)
        photo_var = tk.StringVar(value="")

        form = ttk.Frame(inner, padding=12)
        form.pack(fill=tk.BOTH, expand=True)

        for label, var in [
            ("Date (YYYY-MM-DD)", date_var),
            ("Weight (kg)", weight_var),
            ("Waist (cm)", waist_var),
            ("Chest (cm)", chest_var),
            ("Hips (cm)", hips_var),
            ("Photo path (optional)", photo_var),
        ]:
            row = ttk.Frame(form)
            row.pack(fill=tk.X, pady=4)
            ttk.Label(row, text=f"{label}:", width=22).pack(side=tk.LEFT)
            ttk.Entry(row, textvariable=var, width=20).pack(side=tk.LEFT)

        def save():
            measurements = {}
            if waist_var.get() > 0:
                measurements["waist_cm"] = waist_var.get()
            if chest_var.get() > 0:
                measurements["chest_cm"] = chest_var.get()
            if hips_var.get() > 0:
                measurements["hips_cm"] = hips_var.get()

            log = BodyCompositionLog(
                date=date_var.get().strip(),
                weight_kg=weight_var.get() if weight_var.get() > 0 else None,
                measurements=measurements,
                photo_path=photo_var.get().strip() or None,
            )
            repo.add_body_composition_log(log)
            dialog.destroy()
            refresh()
            messagebox.showinfo("Saved", "Body composition logged.")

        btns = ttk.Frame(inner, padding=10)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Save", command=save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)

    footer = ttk.Frame(win, padding=10)
    footer.pack(fill=tk.X)
    ttk.Button(footer, text="Log Entry", command=open_log_dialog).pack(side=tk.LEFT)
    ttk.Button(footer, text="Refresh", command=refresh).pack(side=tk.LEFT, padx=8)

    refresh()
