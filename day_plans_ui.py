"""UI for planning tomorrow and reviewing plan vs actual."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk
from typing import TYPE_CHECKING

import day_plans
import ui_scroll
from theme import FONTS, style_text_widget

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker


def show_plan_window(tracker: "PersonalDevelopmentTracker", plan_date: str | None = None) -> None:
    theme = tracker.theme
    target = plan_date or day_plans.tomorrow_from().isoformat()

    win = tk.Toplevel(tracker.root)
    win.title("Plan Your Day")
    win.geometry("920x760")
    win.configure(bg=theme["bg"])
    win.transient(tracker.root)

    header = ttk.Frame(win, padding=(16, 14, 16, 8))
    header.pack(fill=tk.X)
    ttk.Label(header, text="Plan Your Day", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        header,
        text="Set intentions for an upcoming day. Tomorrow morning, Integral compares this plan "
        "with what you actually log.",
        style="Muted.TLabel",
        wraplength=860,
    ).pack(anchor="w", pady=(4, 0))

    body = ttk.Frame(win, padding=(16, 0, 16, 8))
    body.pack(fill=tk.BOTH, expand=True)

    top = ttk.LabelFrame(body, text="Plan date", padding=10, style="Card.TLabelframe")
    top.pack(fill=tk.X, pady=(0, 10))
    date_var = tk.StringVar(value=target)
    ttk.Label(top, text="Planning for", style="OnSurfaceMuted.TLabel").pack(side=tk.LEFT)
    ttk.Entry(top, textvariable=date_var, width=12).pack(side=tk.LEFT, padx=(8, 16))
    ttk.Label(
        top,
        text="Usually tomorrow — you can pick another future date.",
        style="OnSurfaceMuted.TLabel",
    ).pack(side=tk.LEFT)

    outer, inner, _canvas = ui_scroll.make_scrollable_frame(body)
    outer.pack(fill=tk.BOTH, expand=True)

    ttk.Label(inner, text="Day intention", style="OnSurfaceSubheading.TLabel").pack(anchor="w", padx=4)
    day_text = scrolledtext.ScrolledText(inner, height=5, wrap=tk.WORD, font=FONTS["body"])
    day_text.pack(fill=tk.X, padx=4, pady=(4, 12))
    style_text_widget(day_text, theme)

    ttk.Label(inner, text="Fitness intention (optional)", style="OnSurfaceSubheading.TLabel").pack(
        anchor="w", padx=4
    )
    fitness_var = tk.StringVar(value="")
    ttk.Entry(inner, textvariable=fitness_var).pack(fill=tk.X, padx=4, pady=(4, 12))

    ttk.Label(
        inner,
        text="Life areas you expect to focus on (notes and optional target rating)",
        style="OnSurfaceSubheading.TLabel",
    ).pack(anchor="w", padx=4, pady=(4, 0))

    category_vars: dict[str, dict[str, tk.Variable]] = {}
    for cat_name in tracker.categories:
        card = ttk.LabelFrame(inner, text=cat_name, padding=8, style="Card.TLabelframe")
        card.pack(fill=tk.X, padx=4, pady=6)
        include_var = tk.BooleanVar(value=False)
        notes_var = tk.StringVar(value="")
        rating_var = tk.StringVar(value="")
        category_vars[cat_name] = {
            "include": include_var,
            "notes": notes_var,
            "rating": rating_var,
        }
        ttk.Checkbutton(card, text="Include in plan", variable=include_var).pack(anchor="w")
        row = ttk.Frame(card, style="Surface.TFrame")
        row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(row, text="Intention", width=10).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=notes_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Label(row, text="Target /10", width=10).pack(side=tk.LEFT)
        ttk.Spinbox(row, from_=1, to=10, textvariable=rating_var, width=5).pack(side=tk.LEFT)

    def load_plan_for_date(*_args: object) -> None:
        plan = day_plans.plan_for_date(tracker.day_plans, date_var.get().strip())
        day_text.delete("1.0", tk.END)
        fitness_var.set("")
        for vars_map in category_vars.values():
            vars_map["include"].set(False)
            vars_map["notes"].set("")
            vars_map["rating"].set("")
        if not plan:
            return
        if plan.get("day_intention"):
            day_text.insert("1.0", plan["day_intention"])
        fitness_var.set(plan.get("fitness_note") or "")
        for cat_name, item in (plan.get("categories") or {}).items():
            if cat_name not in category_vars:
                continue
            category_vars[cat_name]["include"].set(True)
            category_vars[cat_name]["notes"].set(item.get("notes") or "")
            if item.get("rating") is not None:
                category_vars[cat_name]["rating"].set(str(item["rating"]))

    def save_plan() -> None:
        planned_for = date_var.get().strip()
        categories: dict[str, dict] = {}
        for cat_name, vars_map in category_vars.items():
            if not vars_map["include"].get():
                continue
            rating_raw = str(vars_map["rating"].get()).strip()
            rating = int(rating_raw) if rating_raw.isdigit() else None
            notes = vars_map["notes"].get().strip()
            if rating is None and not notes:
                continue
            payload: dict = {"notes": notes}
            if rating is not None:
                payload["rating"] = rating
            categories[cat_name] = payload
        try:
            tracker.day_plans = day_plans.upsert_plan(
                dict(tracker.day_plans),
                planned_for,
                day_intention=day_text.get("1.0", tk.END).strip(),
                fitness_note=fitness_var.get().strip(),
                categories=categories,
            )
        except ValueError as exc:
            messagebox.showwarning("Plan", str(exc), parent=win)
            return
        tracker.save_data(flush=True)
        tracker.refresh_dashboard()
        messagebox.showinfo("Saved", f"Plan saved for {planned_for}.", parent=win)

    date_var.trace_add("write", load_plan_for_date)
    load_plan_for_date()

    footer = ttk.Frame(win, padding=12)
    footer.pack(fill=tk.X)
    ttk.Separator(footer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))
    ttk.Button(footer, text="Save Plan", style="Accent.TButton", command=save_plan).pack(side=tk.RIGHT)
    ttk.Button(footer, text="Close", command=win.destroy).pack(side=tk.RIGHT, padx=(0, 8))


def show_plan_comparison_window(tracker: "PersonalDevelopmentTracker", date_str: str) -> None:
    theme = tracker.theme
    plan = day_plans.plan_for_date(tracker.day_plans, date_str)
    comparison = day_plans.compare_plan_to_actual(
        plan,
        tracker.entries.get(date_str, {}),
        all_categories=list(tracker.categories.keys()),
    )

    win = tk.Toplevel(tracker.root)
    win.title("Plan vs Actual")
    win.geometry("820x680")
    win.configure(bg=theme["bg"])
    win.transient(tracker.root)

    header = ttk.Frame(win, padding=(16, 14, 16, 8))
    header.pack(fill=tk.X)
    ttk.Label(header, text="Plan vs Actual", style="Title.TLabel").pack(anchor="w")
    ttk.Label(header, text=date_str, style="Muted.TLabel").pack(anchor="w", pady=(2, 0))
    ttk.Label(header, text=comparison["summary"], wraplength=760).pack(anchor="w", pady=(8, 0))

    outer, inner, _canvas = ui_scroll.make_scrollable_frame(win)
    outer.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

    if comparison.get("day_intention"):
        block = ttk.LabelFrame(inner, text="Day intention", padding=10, style="Card.TLabelframe")
        block.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(block, text=comparison["day_intention"], wraplength=740).pack(anchor="w")

    if comparison.get("fitness_note"):
        block = ttk.LabelFrame(inner, text="Fitness intention", padding=10, style="Card.TLabelframe")
        block.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(block, text=comparison["fitness_note"], wraplength=740).pack(anchor="w")

    for row in comparison.get("categories") or []:
        card = ttk.LabelFrame(
            inner,
            text=f"{row['category']} — {day_plans.format_category_status(row['status'])}",
            padding=10,
            style="Card.TLabelframe",
        )
        card.pack(fill=tk.X, pady=6)
        planned = row.get("planned") or {}
        actual = row.get("actual") or {}
        if planned.get("notes"):
            ttk.Label(card, text=f"Planned: {planned['notes']}", wraplength=720).pack(anchor="w")
        if planned.get("rating") is not None:
            ttk.Label(card, text=f"Target rating: {planned['rating']}/10").pack(anchor="w")
        if actual:
            ttk.Label(
                card,
                text=f"Actual rating: {actual.get('rating', '?')}/10",
                style="OnSurfaceMuted.TLabel",
            ).pack(anchor="w", pady=(4, 0))
            if actual.get("notes"):
                ttk.Label(card, text=f"Actual notes: {actual['notes']}", wraplength=720).pack(anchor="w")
        elif row["status"] == "not_logged":
            ttk.Label(card, text="Not logged yet.", style="OnSurfaceMuted.TLabel").pack(anchor="w")

    footer = ttk.Frame(win, padding=12)
    footer.pack(fill=tk.X)
    ttk.Button(
        footer,
        text="Explore full day",
        command=lambda: (win.destroy(), tracker.show_day_explorer(date_str)),
    ).pack(side=tk.LEFT)
    ttk.Button(footer, text="Close", command=win.destroy).pack(side=tk.RIGHT)
