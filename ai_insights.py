"""Lightweight local AI insights via Ollama (optional dependency)."""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta
from typing import Any, Callable

import journal
from theme import style_text_widget

DEFAULT_MODEL = "llama3.2:3b"
MAX_NOTE_CHARS = 140
MAX_JOURNAL_EXCERPTS = 4
MAX_JOURNAL_CHARS = 200
MAX_FITNESS_LINES = 6

INSIGHT_KINDS: dict[str, dict[str, str]] = {
    "weekly_review": {
        "label": "Weekly Review",
        "system": (
            "You are a wise, compassionate, concise life coach. Give practical, kind insights "
            "based only on the data provided. Keep responses to 4-8 short paragraphs. "
            "Focus on patterns, wins, gentle suggestions."
        ),
        "user_intro": (
            "Here is recent holistic life data from Integral (18 life domains, journal, fitness). "
            "Give me an honest review with 1-2 concrete next steps. Do not invent data."
        ),
    },
    "emotional_patterns": {
        "label": "Emotional Patterns",
        "system": (
            "You are a calm, observant coach focused on emotional wellbeing and energy. "
            "Spot patterns in mood, stress, and relational notes. Be kind and specific. "
            "4-6 short paragraphs maximum."
        ),
        "user_intro": (
            "Focus on emotional, relational, burnout, and journal signals in this data. "
            "Name patterns you see and one gentle experiment for the coming week."
        ),
    },
}


def ollama_installed() -> bool:
    try:
        import ollama  # noqa: F401

        return True
    except ImportError:
        return False


def _parse_day(date_str: str) -> date | None:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def _date_range(days: int) -> tuple[date, date]:
    end = datetime.now().date()
    start = end - timedelta(days=max(1, days) - 1)
    return start, end


def _in_range(day: date, start: date, end: date) -> bool:
    return start <= day <= end


def _truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def collect_recent_context(
    entries: dict,
    categories: dict,
    *,
    journal_data: dict | None = None,
    fitness_settings: dict | None = None,
    days: int = 7,
) -> str:
    """Build a compact plain-text summary for the model (no embeddings/RAG)."""
    start, end = _date_range(days)
    lines = [f"Period: {start.isoformat()} to {end.isoformat()} ({days} days)", ""]

    lines.append("=== LIFE DOMAINS ===")
    any_domain = False
    for cat_name in categories:
        ratings: list[float] = []
        note_bits: list[str] = []
        days_logged = 0
        offset = 0
        while True:
            day = start + timedelta(days=offset)
            if day > end:
                break
            offset += 1
            date_str = day.isoformat()
            entry = entries.get(date_str, {}).get(cat_name)
            if not entry:
                continue
            days_logged += 1
            rating = entry.get("rating")
            if rating is not None:
                try:
                    ratings.append(float(rating))
                except (TypeError, ValueError):
                    pass
            note = (entry.get("notes") or "").strip()
            if note:
                note_bits.append(_truncate(note, MAX_NOTE_CHARS))

        if days_logged == 0:
            continue
        any_domain = True
        chunk = f"{cat_name}: {days_logged}/{days} days logged"
        if ratings:
            chunk += f", avg rating {sum(ratings) / len(ratings):.1f}/10"
        if note_bits:
            chunk += f"; notes: {' | '.join(note_bits[:2])}"
        lines.append(chunk)

    if not any_domain:
        lines.append("(No life-domain logs in this period.)")

    lines.append("")
    lines.append("=== JOURNAL ===")
    journal_lines: list[str] = []
    if journal_data:
        for item in journal.list_entries(journal_data):
            day = _parse_day(str(item.get("entry_date", "")))
            if day is None or not _in_range(day, start, end):
                continue
            title = item.get("title") or item.get("prompt") or "Entry"
            body = _truncate((item.get("body") or "").strip(), MAX_JOURNAL_CHARS)
            if not body:
                continue
            journal_lines.append(f"{day.isoformat()} — {title}: {body}")
            if len(journal_lines) >= MAX_JOURNAL_EXCERPTS:
                break
    lines.extend(journal_lines or ["(No journal entries in this period.)"])

    lines.append("")
    lines.append("=== FITNESS ===")
    fitness_lines = _collect_fitness_lines(fitness_settings, start, end)
    lines.extend(fitness_lines or ["(No workout sessions in this period.)"])

    return "\n".join(lines)


def _collect_fitness_lines(
    fitness_settings: dict | None,
    start: date,
    end: date,
) -> list[str]:
    try:
        from fitness_ui import get_profile_repo
        from progression.sessions import format_session_summary

        repo = get_profile_repo(fitness_settings)
        repo.initialize()
        lines: list[str] = []
        for session in repo.list_workout_sessions(limit=200):
            day = _parse_day(session.date)
            if day is None or not _in_range(day, start, end):
                continue
            summary = format_session_summary(repo, session)
            for index, line in enumerate(summary.splitlines()):
                if index == 0:
                    lines.append(line)
                elif index < 3:
                    lines.append(f"  {line}")
            lines.append("")
            if len(lines) >= MAX_FITNESS_LINES * 2:
                break
        return [line for line in lines if line.strip()]
    except Exception:
        return []


def build_chat_messages(context: str, *, kind: str = "weekly_review", days: int = 7) -> list[dict[str, str]]:
    spec = INSIGHT_KINDS.get(kind, INSIGHT_KINDS["weekly_review"])
    user_content = (
        f"{spec['user_intro']}\n\n"
        f"Data from the last {days} days:\n\n{context}\n\n"
        "Respond in clear paragraphs. End with a short 'Next steps' section (1-2 items)."
    )
    return [
        {"role": "system", "content": spec["system"]},
        {"role": "user", "content": user_content},
    ]


def fetch_insight(
    context: str,
    *,
    kind: str = "weekly_review",
    days: int = 7,
    model: str = DEFAULT_MODEL,
) -> str:
    """Blocking Ollama call. Run off the UI thread."""
    if not ollama_installed():
        raise RuntimeError(
            "The ollama package is not installed.\n\n"
            "Install with: pip install ollama\n"
            "Then install Ollama from https://ollama.com and run:\n"
            f"  ollama pull {model}"
        )

    from ollama import chat

    try:
        response = chat(model=model, messages=build_chat_messages(context, kind=kind, days=days))
    except Exception as exc:  # noqa: BLE001
        raise _friendly_ollama_error(exc, model) from exc

    message = response.get("message") or {}
    content = (message.get("content") or "").strip()
    if not content:
        raise RuntimeError("Ollama returned an empty response. Try again or choose a different model.")
    return content


def _friendly_ollama_error(exc: Exception, model: str) -> RuntimeError:
    text = str(exc).lower()
    if "connection" in text or "refused" in text or "connect" in text:
        return RuntimeError(
            "Cannot reach Ollama on localhost.\n\n"
            "1. Start the Ollama app (or run `ollama serve`)\n"
            f"2. Pull a small model: ollama pull {model}\n"
            "3. Try again"
        )
    if "not found" in text and "model" in text:
        return RuntimeError(
            f"Model '{model}' is not available.\n\n"
            f"Run: ollama pull {model}\n"
            "Then try again."
        )
    return RuntimeError(f"Ollama error: {exc}")


def run_insight_async(
    root,
    *,
    entries: dict,
    categories: dict,
    journal_data: dict | None,
    fitness_settings: dict | None,
    days: int,
    kind: str,
    model: str,
    on_start: Callable[[], None] | None = None,
    on_success: Callable[[str], None],
    on_error: Callable[[str], None],
) -> None:
    """Gather context and call Ollama on a background thread."""

    def worker() -> None:
        try:
            context = collect_recent_context(
                entries,
                categories,
                journal_data=journal_data,
                fitness_settings=fitness_settings,
                days=days,
            )
            if not context.strip():
                raise RuntimeError("No recent data to analyze. Log a few days first.")
            result = fetch_insight(context, kind=kind, days=days, model=model)
            root.after(0, lambda: on_success(result))
        except Exception as exc:  # noqa: BLE001
            root.after(0, lambda: on_error(str(exc)))

    if on_start:
        on_start()
    threading.Thread(target=worker, daemon=True).start()


def mount_insight_panel(
    parent,
    theme: dict,
    *,
    entries: dict,
    categories: dict,
    journal_data: dict | None = None,
    fitness_settings: dict | None = None,
    default_days: int = 7,
) -> None:
    """Classic Tkinter panel: options, status, scrollable result."""
    import tkinter as tk
    from tkinter import scrolledtext, ttk

    header = ttk.Frame(parent, padding=(12, 10, 12, 6))
    header.pack(fill=tk.X)
    ttk.Label(header, text="Local AI Insight", font=("Helvetica", 13, "bold")).pack(anchor="w")
    ttk.Label(
        header,
        text="Private coaching-style review via Ollama on this machine. No cloud, no embeddings.",
        style="Muted.TLabel",
        wraplength=900,
    ).pack(anchor="w", pady=(4, 0))

    controls = ttk.Frame(parent, padding=(12, 0, 12, 8))
    controls.pack(fill=tk.X)

    days_var = tk.StringVar(value=str(default_days))
    kind_var = tk.StringVar(value=INSIGHT_KINDS["weekly_review"]["label"])
    model_var = tk.StringVar(value=DEFAULT_MODEL)

    ttk.Label(controls, text="Period (days)").pack(side=tk.LEFT)
    days_combo = ttk.Combobox(controls, textvariable=days_var, values=["7", "30"], width=4, state="readonly")
    days_combo.pack(side=tk.LEFT, padx=(6, 14))

    ttk.Label(controls, text="Type").pack(side=tk.LEFT)
    kind_combo = ttk.Combobox(
        controls,
        textvariable=kind_var,
        values=[spec["label"] for spec in INSIGHT_KINDS.values()],
        state="readonly",
        width=20,
    )
    kind_combo.pack(side=tk.LEFT, padx=(6, 14))

    def _resolve_kind() -> str:
        label = kind_var.get()
        for key, spec in INSIGHT_KINDS.items():
            if spec["label"] == label:
                return key
        return "weekly_review"

    ttk.Label(controls, text="Model").pack(side=tk.LEFT)
    ttk.Entry(controls, textvariable=model_var, width=16).pack(side=tk.LEFT, padx=(6, 14))

    status_var = tk.StringVar(
        value="Ready."
        if ollama_installed()
        else "Optional: pip install ollama, start Ollama, then pull a small model."
    )
    status = ttk.Label(parent, textvariable=status_var, style="Muted.TLabel", padding=(12, 0))
    status.pack(fill=tk.X)

    result = scrolledtext.ScrolledText(parent, wrap=tk.WORD, font=("Helvetica", 11), height=22)
    result.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 12))
    style_text_widget(result, theme)
    result.insert(
        tk.END,
        "Click Get AI Insight for a concise review of your recent logs.\n\n"
        "Setup (one time):\n"
        "  1. Install Ollama from https://ollama.com\n"
        "  2. pip install ollama\n"
        f"  3. ollama pull {DEFAULT_MODEL}\n",
    )
    result.config(state=tk.DISABLED)

    run_btn = ttk.Button(controls, text="Get AI Insight", style="Accent.TButton")

    def set_busy(busy: bool) -> None:
        run_btn.config(state=tk.DISABLED if busy else tk.NORMAL)

    def show_result(text: str) -> None:
        result.config(state=tk.NORMAL)
        result.delete("1.0", tk.END)
        result.insert(tk.END, text)
        result.config(state=tk.DISABLED)

    def on_click() -> None:
        try:
            days = int(str(days_var.get()).strip())
        except (TypeError, ValueError, tk.TclError):
            days = default_days
        kind = _resolve_kind()
        model = model_var.get().strip() or DEFAULT_MODEL

        def on_start() -> None:
            status_var.set("Analyzing… (Ollama is thinking on your machine)")
            set_busy(True)
            show_result("")

        def on_success(text: str) -> None:
            status_var.set("Done.")
            set_busy(False)
            show_result(text)

        def on_error(message: str) -> None:
            status_var.set("Could not complete insight.")
            set_busy(False)
            show_result(message)

        run_insight_async(
            parent.winfo_toplevel(),
            entries=entries,
            categories=categories,
            journal_data=journal_data,
            fitness_settings=fitness_settings,
            days=days,
            kind=kind,
            model=model,
            on_start=on_start,
            on_success=on_success,
            on_error=on_error,
        )

    run_btn.config(command=on_click)
    run_btn.pack(side=tk.LEFT)


def show_insight_dialog(
    parent,
    theme: dict,
    *,
    entries: dict,
    categories: dict,
    journal_data: dict | None = None,
    fitness_settings: dict | None = None,
    default_days: int = 7,
) -> None:
    import tkinter as tk
    from tkinter import ttk

    dialog = tk.Toplevel(parent)
    dialog.title("AI Insight")
    dialog.geometry("920x720")
    dialog.minsize(640, 480)
    dialog.configure(bg=theme["bg"])
    dialog.transient(parent)

    footer = ttk.Frame(dialog, padding=(12, 10))
    footer.pack(side=tk.BOTTOM, fill=tk.X)
    ttk.Button(footer, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

    body = ttk.Frame(dialog)
    body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    mount_insight_panel(
        body,
        theme,
        entries=entries,
        categories=categories,
        journal_data=journal_data,
        fitness_settings=fitness_settings,
        default_days=default_days,
    )
