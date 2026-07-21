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

INSIGHT_KINDS: dict[str, dict[str, str | int]] = {
    "day_scanner": {
        "label": "Day Scanner",
        "default_days": 1,
        "system": (
            "You are a concise daily review coach for a holistic life tracker. "
            "Scan what was logged today across life domains, journal, and fitness. "
            "Name what is complete, what is missing, and one small action for tonight or tomorrow. "
            "3-5 short paragraphs maximum."
        ),
        "user_intro": (
            "This is a same-day scan of Integral data (18 life domains, journal, fitness). "
            "Summarize today honestly: wins, gaps, energy, and one practical next step. "
            "Do not invent data."
        ),
    },
    "weekly_review": {
        "label": "Weekly Review",
        "default_days": 7,
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
        "default_days": 7,
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
    "energy_burnout": {
        "label": "Energy & Burnout",
        "default_days": 7,
        "system": (
            "You are a burnout-aware coach. Focus on energy, sleep, boundaries, rest, and "
            "Burnout Prevention signals. Be direct but kind. 4-6 short paragraphs."
        ),
        "user_intro": (
            "Analyze energy, sleep, burnout-prevention checklists, and recovery patterns. "
            "Flag overload or neglect of rest. Suggest one sustainable adjustment."
        ),
    },
    "body_fitness": {
        "label": "Body & Movement",
        "default_days": 7,
        "system": (
            "You are a movement and recovery coach. Focus on Body & Presence, fitness sessions, "
            "movement metrics, and physical self-care. 4-6 short paragraphs."
        ),
        "user_intro": (
            "Review body, movement, exercise, sleep, and fitness session data. "
            "Note consistency, gaps, and one realistic movement goal."
        ),
    },
    "gaps_and_balance": {
        "label": "Gaps & Life Balance",
        "default_days": 30,
        "system": (
            "You are a holistic balance coach across many life domains (money, relationships, "
            "learning, spiritual, creative, etc.). Identify neglected areas and imbalance. "
            "4-6 short paragraphs."
        ),
        "user_intro": (
            "Which life domains were logged rarely or not at all? Where is the user's attention "
            "clustered vs missing? Suggest rebalancing without guilt-tripping."
        ),
    },
    "journal_themes": {
        "label": "Journal Themes",
        "default_days": 7,
        "system": (
            "You are a reflective writing coach. Extract recurring themes from journal entries "
            "and domain notes — what the person keeps processing. 4-6 short paragraphs."
        ),
        "user_intro": (
            "Read journal entries and notes across domains. Name recurring themes, open loops, "
            "and what seems unresolved. One prompt for the next journal entry."
        ),
    },
    "gut_symptoms": {
        "label": "Gut & Symptom Patterns",
        "default_days": 21,
        "system": (
            "You are a careful holistic-health coach (not a doctor). Look for relationships "
            "between daily practices (breathing, Five Tibetan Rites, yoga, diet adherence, "
            "supplements) and symptoms (gas, bloating, stomach comfort, energy, regularity). "
            "Only claim patterns the data supports; note when evidence is thin. Be practical "
            "and kind. 4-6 short paragraphs."
        ),
        "user_intro": (
            "Using the '[Practice ...]' log lines, symptom metrics, and notes below, tell me "
            "which practices seem to line up with better or worse symptoms, and suggest one "
            "experiment to confirm. Do not invent data or give medical advice."
        ),
    },
    "vitality_aging": {
        "label": "Vitality & Anti-Aging",
        "default_days": 30,
        "system": (
            "You are a careful longevity/vitality coach (not a doctor). Look for relationships "
            "between anti-inflammatory / antioxidant-supporting practices (diet, movement, sleep, "
            "stress down-regulation) and signs of energy, fatigue, inflammation, and perceived "
            "aging. Only claim what the data supports; flag thin evidence. Be practical and kind. "
            "4-6 short paragraphs."
        ),
        "user_intro": (
            "Focus on vitality, oxidative-stress/inflammation signs (fatigue, energy, perceived "
            "aging), and which practices line up with better days. Suggest one sustainable "
            "experiment. Do not invent data or give medical advice."
        ),
    },
    "sleep_hypersomnia": {
        "label": "Sleep & Hypersomnia",
        "default_days": 21,
        "system": (
            "You are a sleep-aware coach (not a doctor) attentive to idiopathic hypersomnia. "
            "Relate sleep hygiene, consistent wake time, morning light, and practices (e.g. Five "
            "Tibetan Rites, breathwork) to daytime sleepiness, sleep inertia, and next-day energy. "
            "Note that lower daytime sleepiness / sleep inertia is better. Be practical and kind. "
            "4-6 short paragraphs."
        ),
        "user_intro": (
            "Look at sleep metrics (daytime sleepiness, sleep inertia, hours slept) and how "
            "consistency of Rites + sleep hygiene lines up with sleepiness/energy. Suggest one "
            "adjustment. Do not invent data or give medical advice."
        ),
    },
    "neurodivergence_alignment": {
        "label": "Neurodivergence & Alignment",
        "default_days": 30,
        "system": (
            "You are a respectful, affirming coach for a high-functioning autistic adult exploring "
            "self-understanding. Surface themes from journal entries and domain notes around "
            "masking, sensory load, authenticity, and what autism means to them. Never pathologize; "
            "honor neurodivergence as difference. Be gentle and specific. 4-6 short paragraphs."
        ),
        "user_intro": (
            "Read journal reflections and neurodivergence/domain notes. Name recurring themes "
            "around masking, sensory needs, and self-understanding, and note progress. Offer one "
            "gentle prompt for further reflection. Do not invent data."
        ),
    },
    "life_alignment_goals": {
        "label": "Life Alignment & Goals",
        "default_days": 30,
        "system": (
            "You are a values-and-alignment coach. Compare stated goals/milestones and alignment "
            "signals with what the daily logs actually show. Name where life feels aligned vs "
            "where actions and intentions diverge, without guilt-tripping. Be direct but kind. "
            "4-6 short paragraphs."
        ),
        "user_intro": (
            "Using alignment metrics, goal/milestone notes, and journal reflections, tell me where "
            "I'm aligned vs drifting, and one concrete next step toward a stated goal. Do not "
            "invent data."
        ),
    },
}

INSIGHT_KIND_ORDER = list(INSIGHT_KINDS.keys())
PERIOD_DAY_OPTIONS = ("1", "7", "30")


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


def _format_period_label(days: int) -> str:
    if days == 1:
        return "today"
    return f"the last {days} days"


def _summarize_entry(entry: dict) -> str:
    parts: list[str] = []
    checklist = entry.get("checklist") or {}
    done = [label for label, checked in checklist.items() if checked]
    if done:
        parts.append(f"checklist done: {', '.join(done[:4])}")
    metrics = entry.get("metrics") or {}
    metric_bits = [
        f"{name}={value}"
        for name, value in metrics.items()
        if value not in (None, "", 0, 0.0)
    ]
    if metric_bits:
        parts.append(f"metrics: {', '.join(metric_bits[:4])}")
    note = (entry.get("notes") or "").strip()
    if note:
        parts.append(f"note: {_truncate(note, MAX_NOTE_CHARS)}")
    return "; ".join(parts)


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
    period_label = "Today only" if days == 1 else f"{start.isoformat()} to {end.isoformat()} ({days} days)"
    lines = [f"Period: {period_label}", ""]

    domain_days_logged = 0
    total_domain_entries = 0
    all_ratings: list[float] = []
    checklist_wins: list[str] = []

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
            total_domain_entries += 1
            rating = entry.get("rating")
            if rating is not None:
                try:
                    ratings.append(float(rating))
                    all_ratings.append(float(rating))
                except (TypeError, ValueError):
                    pass
            detail = _summarize_entry(entry)
            if detail:
                if days == 1:
                    note_bits.append(detail)
                else:
                    note_bits.append(_truncate(detail, MAX_NOTE_CHARS))
            checklist = entry.get("checklist") or {}
            for label, checked in checklist.items():
                if checked:
                    checklist_wins.append(f"{cat_name}: {label}")

        if days_logged == 0:
            continue
        domain_days_logged += 1
        any_domain = True
        chunk = f"{cat_name}: {days_logged}/{days} days logged"
        if ratings:
            chunk += f", avg rating {sum(ratings) / len(ratings):.1f}/10"
        if note_bits:
            joiner = " | " if days > 1 else " — "
            limit = 1 if days == 1 else 2
            chunk += f"; {joiner.join(note_bits[:limit])}"
        lines.append(chunk)

    if not any_domain:
        lines.append("(No life-domain logs in this period.)")

    lines.append("")
    lines.append("=== PERIOD SUMMARY ===")
    lines.append(
        f"Domains with any logs: {domain_days_logged}/{len(categories)}; "
        f"total domain-day entries: {total_domain_entries}"
    )
    if all_ratings:
        lines.append(f"Average rating across logged entries: {sum(all_ratings) / len(all_ratings):.1f}/10")
    if checklist_wins:
        lines.append(f"Checklist items completed ({len(checklist_wins)}): " + "; ".join(checklist_wins[:8]))
    else:
        lines.append("Checklist items completed: none recorded in this period.")

    logged_names = set()
    for cat_name in categories:
        for offset in range(days):
            day = start + timedelta(days=offset)
            if entries.get(day.isoformat(), {}).get(cat_name):
                logged_names.add(cat_name)
                break
    skipped = [name for name in categories if name not in logged_names]
    if skipped:
        preview = ", ".join(skipped[:10])
        if len(skipped) > 10:
            preview += f", … (+{len(skipped) - 10} more)"
        lines.append(f"Domains not logged in period: {preview}")

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
    period = _format_period_label(days)
    user_content = (
        f"{spec['user_intro']}\n\n"
        f"Data from {period}:\n\n{context}\n\n"
        "Respond in clear paragraphs. End with a short 'Next steps' section (1-2 items)."
    )
    return [
        {"role": "system", "content": str(spec["system"])},
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
    default_kind = "day_scanner" if default_days == 1 else "weekly_review"
    kind_var = tk.StringVar(value=str(INSIGHT_KINDS[default_kind]["label"]))
    model_var = tk.StringVar(value=DEFAULT_MODEL)

    ttk.Label(controls, text="Period").pack(side=tk.LEFT)
    days_combo = ttk.Combobox(
        controls,
        textvariable=days_var,
        values=list(PERIOD_DAY_OPTIONS),
        width=4,
        state="readonly",
    )
    days_combo.pack(side=tk.LEFT, padx=(6, 14))

    ttk.Label(controls, text="Insight type").pack(side=tk.LEFT)
    kind_labels = [str(INSIGHT_KINDS[key]["label"]) for key in INSIGHT_KIND_ORDER]
    kind_combo = ttk.Combobox(
        controls,
        textvariable=kind_var,
        values=kind_labels,
        state="readonly",
        width=22,
    )
    kind_combo.pack(side=tk.LEFT, padx=(6, 14))

    def _resolve_kind() -> str:
        label = kind_var.get()
        for key, spec in INSIGHT_KINDS.items():
            if spec["label"] == label:
                return key
        return "weekly_review"

    def _apply_kind_defaults(*_args) -> None:
        kind = _resolve_kind()
        suggested = int(INSIGHT_KINDS.get(kind, {}).get("default_days", 7))
        days_var.set(str(suggested))

    kind_var.trace_add("write", _apply_kind_defaults)

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
        "Pick an insight type and period, then click Get AI Insight.\n\n"
        "Day Scanner + Today (1) = same-day wrap-up across all logged domains.\n"
        "Weekly Review / Emotional Patterns work well with 7 or 30 days.\n\n"
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
