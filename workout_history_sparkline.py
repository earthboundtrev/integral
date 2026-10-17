"""Tk Canvas sparkline for per-exercise workout history (#117). No matplotlib."""

from __future__ import annotations

import tkinter as tk
from typing import Sequence

from progression.recent_compare import compute_volume_score


def best_set_metric_for_rows(rows) -> tuple[float | None, str]:
    """Best single-set volume score across workout set rows."""
    best: float | None = None
    kind = ""
    for row in rows:
        score, k = compute_volume_score(
            sets=row.sets,
            reps=row.reps,
            weight_kg=row.weight_kg,
            hold_seconds=row.hold_seconds,
        )
        if score is None:
            continue
        if best is None or score > best:
            best = score
            kind = k
    return best, kind


def format_metric_number(value: float) -> str:
    """Locale-neutral number (ASCII period decimal separator)."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"


def metric_unit_label(kind: str) -> str:
    if kind == "weighted":
        return "kg·vol"
    if kind == "hold":
        return "s hold·vol"
    if kind == "reps":
        return "rep·vol"
    return ""


def format_metric_display(value: float | None, kind: str) -> str:
    if value is None:
        return "—"
    unit = metric_unit_label(kind)
    num = format_metric_number(value)
    return f"{num} {unit}".strip()


def sparkline_accessibility_summary(
    values: Sequence[float],
    dates: Sequence[str],
    kind: str,
) -> str:
    """Text summary: first, last, and best values (screen readers)."""
    if not values:
        return "Trend: no logged sessions yet."
    unit = metric_unit_label(kind)
    first_v = format_metric_number(values[0])
    last_v = format_metric_number(values[-1])
    best_idx = max(range(len(values)), key=lambda i: values[i])
    best_v = format_metric_number(values[best_idx])
    best_date = dates[best_idx] if best_idx < len(dates) else ""
    return (
        f"Trend chart. First session {dates[0]}: {first_v} {unit}. "
        f"Latest session {dates[-1]}: {last_v} {unit}. "
        f"Best {best_v} {unit} on {best_date}."
    )


def draw_sparkline(
    canvas: tk.Canvas,
    values: Sequence[float],
    *,
    theme: dict,
    padding: int = 8,
) -> None:
    """Draw a polyline oldest→newest (values order must be oldest first)."""
    canvas.delete("all")
    width = max(int(canvas.winfo_width()), 120)
    height = max(int(canvas.winfo_height()), 48)
    canvas.configure(width=width, height=height)

    bg = theme.get("surface", "#FFFFFF")
    fg = theme.get("fg", "#1A1D21")
    accent = theme.get("accent", "#2F7A7B")
    muted = theme.get("muted", "#666666")
    canvas.configure(bg=bg, highlightthickness=1, highlightbackground=theme.get("card_border", muted))

    if not values:
        canvas.create_text(
            width // 2,
            height // 2,
            text="No trend data",
            fill=muted,
            font=("Helvetica", 9),
        )
        return

    inner_w = max(width - padding * 2, 1)
    inner_h = max(height - padding * 2, 1)
    vmin = min(values)
    vmax = max(values)
    span = vmax - vmin
    if span <= _EPS:
        span = vmax if vmax > 0 else 1.0
        vmin = vmax - span

    points: list[float] = []
    n = len(values)
    for i, v in enumerate(values):
        x = padding + (inner_w * i / max(n - 1, 1))
        norm = (v - vmin) / span
        y = padding + inner_h * (1.0 - norm)
        points.extend([x, y])

    if n == 1:
        x, y = points[0], points[1]
        canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=accent, outline=accent)
    else:
        canvas.create_line(*points, fill=accent, width=2, smooth=True)
        canvas.create_oval(points[0] - 3, points[1] - 3, points[0] + 3, points[1] + 3, fill=fg, outline=fg)
        canvas.create_oval(
            points[-2] - 3,
            points[-1] - 3,
            points[-2] + 3,
            points[-1] + 3,
            fill=accent,
            outline=accent,
        )
    canvas.create_text(padding, height - 2, text="older", anchor=tk.SW, fill=muted, font=("Helvetica", 8))
    canvas.create_text(width - padding, height - 2, text="newer", anchor=tk.SE, fill=muted, font=("Helvetica", 8))


_EPS = 1e-9


def default_sparkline_height(widget: tk.Misc | None = None, *, base: int = 56) -> int:
    """Scale sparkline height for HiDPI (125–175%+) so the line is not clipped."""
    dpi = 96.0
    if widget is not None:
        try:
            dpi = float(widget.winfo_fpixels("1i"))
        except tk.TclError:
            pass
    return max(base, int(round(base * dpi / 96.0)))
