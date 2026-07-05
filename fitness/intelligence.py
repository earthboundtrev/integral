"""Advanced fitness progression intelligence."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def default_fitness_settings() -> dict[str, Any]:
    return {
        "tibetan_advance_consecutive_days": 7,
        "cc_sessions_for_advance": 2,
        "cc_min_form_quality": 7,
    }


def get_fitness_settings(settings: dict) -> dict[str, Any]:
    merged = default_fitness_settings()
    merged.update(settings.get("fitness", {}))
    return merged


def get_last_program_session(sessions: list[dict], program_id: str) -> dict | None:
    program_sessions = [session for session in sessions if session.get("program_id") == program_id]
    if not program_sessions:
        return None
    return sorted(program_sessions, key=lambda item: item["date"])[-1]


def smart_defaults_for_program(program: dict, sessions: list[dict], program_state: dict) -> dict[str, Any]:
    """Pre-fill log form from last session and current program state."""
    last = get_last_program_session(sessions, program.get("id", ""))
    state = program_state.get(program.get("id", ""), {})
    defaults: dict[str, Any] = {"notes": "", "session_rpe": 7, "duration_min": 20}

    if program["progression_model"] == "weekly_rep_ramp":
        target = state.get("target_reps", program["rules"]["start_reps_per_rite"])
        defaults["target_reps"] = target
        defaults["reps_per_rite"] = {rite["id"]: target for rite in program["movements"]}
        if last:
            for log in last.get("movement_logs", []):
                defaults["reps_per_rite"] = dict(log.get("reps_per_rite", defaults["reps_per_rite"]))
                defaults["target_reps"] = log.get("target_reps", target)
                defaults["cycle_duration_sec"] = log.get("cycle_duration_sec")
        return defaults

    if program["progression_model"] == "parc_step":
        chain = program["chains"][0]
        chain_state = state.get(chain["id"], {})
        step = chain_state.get("current_step", 1)
        defaults["chain_key"] = chain["id"]
        defaults["step"] = step
        defaults["reps_per_set"] = [5, 5, 5]
        if last:
            log = last.get("movement_logs", [{}])[0]
            defaults["chain_key"] = log.get("chain_key", chain["id"])
            defaults["step"] = log.get("step", step)
            defaults["reps_per_set"] = list(log.get("reps_per_set", defaults["reps_per_set"]))
            defaults["height_cm"] = log.get("height_cm")
            defaults["session_rpe"] = last.get("session_rpe", 7)
        return defaults

    movement = program["movements"][0]
    movement_state = state.get(movement["id"], {})
    step = movement_state.get("current_step", 1)
    defaults["movement_key"] = movement["id"]
    defaults["step"] = step
    defaults["reps_per_set"] = [10, 10, 10]
    defaults["form_quality"] = 8
    if last:
        log = last.get("movement_logs", [{}])[0]
        defaults["movement_key"] = log.get("movement_key", movement["id"])
        defaults["step"] = log.get("step", step)
        defaults["reps_per_set"] = list(log.get("reps_per_set", defaults["reps_per_set"]))
        defaults["hold_seconds"] = log.get("hold_seconds")
        defaults["form_quality"] = log.get("form_quality", 8)
        defaults["session_rpe"] = last.get("session_rpe", 7)
        defaults["duration_min"] = last.get("duration_min", 20)
    return defaults


def metric_total(log: dict) -> float:
    reps = log.get("reps_per_set") or []
    if reps:
        return float(sum(reps))
    if log.get("hold_seconds") is not None:
        return float(log["hold_seconds"])
    if log.get("height_cm") is not None:
        return float(log["height_cm"])
    reps_per_rite = log.get("reps_per_rite") or {}
    if reps_per_rite:
        return float(sum(int(value) for value in reps_per_rite.values()))
    return 0.0


def classify_metric_trend(logs: list[dict], min_sessions: int = 3) -> str:
    if len(logs) < min_sessions:
        return "insufficient_data"
    values = [metric_total(log) for log in logs]
    if len(logs) >= 4:
        recent_mean = sum(values[-2:]) / 2
        baseline = sum(values[:-2]) / max(1, len(values) - 2)
        if baseline > 0 and recent_mean < baseline * 0.85:
            return "regressing"
    if len(logs) >= 5 and max(values[-4:]) - min(values[-4:]) < max(1.0, max(values) * 0.05):
        return "plateau"
    if len(values) >= 2 and values[-1] > values[0] * 1.05:
        return "improving"
    return "stable"


def cc_sessions_meeting_standard(logs: list[dict], program: dict, movement_key: str, step: int) -> list[dict]:
    from fitness.engine import evaluate_session_log, get_step_definition

    step_def = get_step_definition(program, movement_key, step)
    if not step_def:
        return []
    met: list[dict] = []
    for log in logs:
        if int(log.get("step", 1)) != step:
            continue
        evaluation = evaluate_session_log(
            {
                "movement_key": movement_key,
                "step": step,
                "reps_per_set": log.get("reps_per_set"),
                "hold_seconds": log.get("hold_seconds"),
                "form_quality": log.get("form_quality", 10),
            },
            program,
        )
        if evaluation.get("ready_to_advance"):
            met.append(log)
    return met


def tibetan_consecutive_success_days(sessions: list[dict], program: dict, target: int) -> int:
    rite_ids = [rite["id"] for rite in program["movements"]]
    success_dates: list[str] = []
    for session in sorted(sessions, key=lambda item: item["date"]):
        for log in session.get("movement_logs", []):
            session_target = int(log.get("target_reps", target))
            reps = log.get("reps_per_rite") or {}
            if reps and all(int(reps.get(rite_id, 0)) >= session_target for rite_id in rite_ids):
                success_dates.append(session["date"])
                break
    if not success_dates:
        return 0
    streak = 1
    best = 1
    for index in range(1, len(success_dates)):
        prev = datetime.strptime(success_dates[index - 1], "%Y-%m-%d").date()
        curr = datetime.strptime(success_dates[index], "%Y-%m-%d").date()
        if (curr - prev).days == 1:
            streak += 1
            best = max(best, streak)
        elif curr != prev:
            streak = 1
    today = datetime.now().date()
    last = datetime.strptime(success_dates[-1], "%Y-%m-%d").date()
    if (today - last).days > 1:
        return 0
    return streak if streak == best else best


def advancement_evidence(program: dict, logs_at_step: list[dict], settings: dict) -> list[str]:
    fitness_settings = get_fitness_settings(settings)
    evidence: list[str] = []
    model = program["progression_model"]

    if model == "step_ladder" and logs_at_step:
        movement_key = logs_at_step[-1].get("movement_key", "")
        step = int(logs_at_step[-1].get("step", 1))
        met = cc_sessions_meeting_standard(logs_at_step, program, movement_key, step)
        needed = fitness_settings["cc_sessions_for_advance"]
        evidence.append(f"{len(met)}/{needed} sessions met progression standard at step {step}")
        for log in met[-3:]:
            evidence.append(f"  {log.get('date')}: {log.get('reps_per_set') or log.get('hold_seconds')}")

    if model == "weekly_rep_ramp":
        target = program["rules"]["start_reps_per_rite"]
        if logs_at_step:
            target = int(logs_at_step[-1].get("target_reps", target))
        streak = tibetan_consecutive_success_days(
            [{"date": log["date"], "movement_logs": [log]} for log in logs_at_step],
            program,
            target,
        )
        needed = fitness_settings["tibetan_advance_consecutive_days"]
        evidence.append(f"{streak}/{needed} consecutive days all rites met target {target}")

    if model == "parc_step" and len(logs_at_step) >= 3:
        heights = [log.get("height_cm") for log in logs_at_step if log.get("height_cm")]
        if heights:
            evidence.append(f"Height trend: {heights[-3:]}")
        reps = [sum(log.get("reps_per_set") or []) for log in logs_at_step[-3:]]
        evidence.append(f"Recent volume: {reps}")

    return evidence


def next_suggested_action(program: dict, item_state: dict, settings: dict) -> str:
    trend = item_state.get("trend", "insufficient_data")
    if item_state.get("ready_to_advance"):
        return "Confirm step/rep advance — standards met."
    if trend == "plateau":
        return "Hold current level; focus form or deload one step."
    if trend == "regressing":
        return "Reduce volume; check recovery and sleep."
    if trend == "insufficient_data":
        return "Log 2–3 more sessions for trend data."
    sessions_at = item_state.get("sessions_at_step", 0)
    if sessions_at >= 5:
        return "Stuck at level — review official B/I/P standards."
    return "Continue current level; meet progression standard consistently."


def compute_development_scores(
    programs: dict[str, dict],
    sessions: list[dict],
    program_state: dict,
) -> dict[str, float]:
    """Normalized 0–100 score per program for radar chart."""
    scores: dict[str, float] = {}
    today = datetime.now().date()
    for program_id, program in programs.items():
        program_sessions = [session for session in sessions if session.get("program_id") == program_id]
        recent = []
        for session in program_sessions:
            try:
                day = datetime.strptime(session["date"], "%Y-%m-%d").date()
            except ValueError:
                continue
            if (today - day).days <= 28:
                recent.append(session)
        consistency = min(100.0, (len(recent) / 12.0) * 100.0)

        progression = 40.0
        state = program_state.get(program_id, {})
        if isinstance(state, dict):
            trends = [
                item.get("trend")
                for item in state.values()
                if isinstance(item, dict) and item.get("trend") == "improving"
            ]
            if trends:
                progression = 75.0
            if any(isinstance(item, dict) and item.get("ready_to_advance") for item in state.values()):
                progression = 90.0

        performance = 50.0
        if program_sessions:
            latest_logs = program_sessions[-1].get("movement_logs", [])
            if latest_logs and metric_total(latest_logs[0]) > 0:
                performance = 65.0

        scores[program_id] = round((consistency * 0.4) + (progression * 0.35) + (performance * 0.25), 1)
    return scores


def find_personal_records(sessions: list[dict], program_id: str) -> list[dict]:
    records: list[dict] = []
    best_by_key: dict[str, dict] = {}
    for session in sessions:
        if session.get("program_id") != program_id:
            continue
        for log in session.get("movement_logs", []):
            key = log.get("movement_key") or log.get("chain_key") or "session"
            total = metric_total(log)
            height = log.get("height_cm")
            metric = height if height else total
            label = f"{key} height" if height else key
            existing = best_by_key.get(label)
            if not existing or metric > existing["value"]:
                best_by_key[label] = {
                    "label": label,
                    "value": metric,
                    "date": session["date"],
                    "detail": log,
                }
    records.extend(best_by_key.values())
    return sorted(records, key=lambda item: item["date"], reverse=True)


def weekly_fitness_summary(sessions: list[dict], programs: dict[str, dict], week_dates: list[str]) -> str:
    lines = ["FITNESS", "-" * 40]
    week_sessions = [session for session in sessions if session.get("date") in week_dates]
    lines.append(f"Sessions this week: {len(week_sessions)}")
    touched = {session.get("program_id") for session in week_sessions}
    for program_id in sorted(touched):
        program = programs.get(program_id, {})
        lines.append(f"  {program.get('name', program_id)}")
    prs = []
    for program_id in touched:
        prs.extend(find_personal_records(week_sessions, program_id or ""))
    if prs:
        lines.append("Notable efforts:")
        for record in prs[:5]:
            lines.append(f"  {record['date']}: {record['label']} = {record['value']}")
    if not week_sessions:
        lines.append("  No fitness sessions logged this week.")
    lines.append("")
    return "\n".join(lines)
