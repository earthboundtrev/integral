"""Fitness program engine — load programs, compute state, evaluate advancement."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from typing import Any

from paths import programs_dir

PROGRAMS_DIR = programs_dir()

try:
    from fitness.intelligence import (
        advancement_evidence,
        cc_sessions_meeting_standard,
        classify_metric_trend,
        get_fitness_settings,
        next_suggested_action,
        tibetan_consecutive_success_days,
    )
except ImportError:
    from intelligence import (  # type: ignore
        advancement_evidence,
        cc_sessions_meeting_standard,
        classify_metric_trend,
        get_fitness_settings,
        next_suggested_action,
        tibetan_consecutive_success_days,
    )

SETS_REPS_RE = re.compile(r"^(\d+)x(\d+)$")
HOLD_RE = re.compile(r"^(\d+)s$")


def load_program_definitions() -> dict[str, dict]:
    programs: dict[str, dict] = {}
    if not os.path.isdir(PROGRAMS_DIR):
        return programs
    for filename in sorted(os.listdir(PROGRAMS_DIR)):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(PROGRAMS_DIR, filename)
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        programs[data["id"]] = data
    return programs


def parse_standard(value: str) -> dict[str, Any]:
    value = value.strip()
    hold = HOLD_RE.match(value)
    if hold:
        return {"type": "hold_seconds", "seconds": int(hold.group(1))}
    sets_reps = SETS_REPS_RE.match(value)
    if sets_reps:
        return {
            "type": "sets_reps",
            "sets": int(sets_reps.group(1)),
            "reps": int(sets_reps.group(2)),
        }
    return {"type": "unknown", "raw": value}


def iter_movements(program: dict) -> list[dict[str, Any]]:
    if program["progression_model"] == "parc_step":
        movements: list[dict[str, Any]] = []
        for chain in program.get("chains", []):
            for step in chain.get("steps", []):
                movements.append(
                    {
                        "movement_id": f"{chain['id']}-step-{step['step']}",
                        "chain_id": chain["id"],
                        "chain_name": chain["name"],
                        "program_id": program["id"],
                        "step": step["step"],
                        "name": step["name"],
                        "master": step.get("master", False),
                        "standards": {
                            "beginner": parse_standard(step["beginner"]),
                            "intermediate": parse_standard(step["intermediate"]),
                            "progression": parse_standard(step["progression"]),
                        },
                        "primary_metric": chain.get("primary_metric", "reps"),
                        "track_height": step.get("track_height", False),
                    }
                )
        return movements

    movements = []
    for movement in program.get("movements", []):
        for step in movement.get("steps", []):
            movements.append(
                {
                    "movement_id": f"{movement['id']}-step-{step['step']}",
                    "parent_movement_id": movement["id"],
                    "parent_movement_name": movement["name"],
                    "program_id": program["id"],
                    "step": step["step"],
                    "name": step["name"],
                    "master": step.get("master", False),
                    "standards": {
                        "beginner": parse_standard(step["beginner"]),
                        "intermediate": parse_standard(step["intermediate"]),
                        "progression": parse_standard(step["progression"]),
                    },
                }
            )
    return movements


def get_step_definition(program: dict, movement_key: str, step: int) -> dict | None:
    if program["progression_model"] == "weekly_rep_ramp":
        return next((item for item in program.get("movements", []) if item["id"] == movement_key), None)
    if program["progression_model"] == "parc_step":
        for chain in program.get("chains", []):
            if chain["id"] == movement_key:
                return next((item for item in chain["steps"] if item["step"] == step), None)
    for movement in program.get("movements", []):
        if movement["id"] == movement_key:
            return next((item for item in movement["steps"] if item["step"] == step), None)
    return None


def meets_sets_reps_standard(reps_per_set: list[int], standard: dict) -> bool:
    if standard.get("type") != "sets_reps":
        return False
    needed_sets = standard["sets"]
    needed_reps = standard["reps"]
    if len(reps_per_set) < needed_sets:
        return False
    return all(rep >= needed_reps for rep in reps_per_set[:needed_sets])


def meets_hold_standard(hold_seconds: float, standard: dict) -> bool:
    return standard.get("type") == "hold_seconds" and hold_seconds >= standard["seconds"]


def evaluate_session_log(log: dict, program: dict) -> dict[str, Any]:
    """Return advancement hints for a single movement log entry."""
    model = program["progression_model"]
    result: dict[str, Any] = {"ready_to_advance": False, "trend": "logged", "messages": []}

    if model == "step_ladder":
        step_def = get_step_definition(program, log["movement_key"], log["step"])
        if not step_def:
            return result
        standard = parse_standard(step_def["progression"])
        reps = log.get("reps_per_set") or []
        hold_seconds = log.get("hold_seconds")
        if hold_seconds is not None:
            if meets_hold_standard(float(hold_seconds), standard):
                result["ready_to_advance"] = True
                result["messages"].append(f"Met progression hold: {step_def['progression']}")
        elif reps and meets_sets_reps_standard(reps, standard):
            result["ready_to_advance"] = True
            result["messages"].append(f"Met progression standard: {step_def['progression']}")
        form = log.get("form_quality")
        if form is not None and form < 7:
            result["ready_to_advance"] = False
            result["messages"].append("Form quality below 7 — confirm before advancing.")
        return result

    if model == "weekly_rep_ramp":
        target = log.get("target_reps")
        performed = log.get("reps_per_rite") or {}
        if not target or not performed:
            return result
        all_met = all(performed.get(rite, 0) >= target for rite in performed)
        result["ready_to_advance"] = all_met
        if all_met:
            result["messages"].append(f"All rites met target {target} reps — eligible for +2 next week.")
        return result

    if model == "parc_step":
        step_def = get_step_definition(program, log["chain_key"], log["step"])
        if not step_def:
            return result
        standard = parse_standard(step_def["progression"])
        reps = log.get("reps_per_set") or []
        if reps and meets_sets_reps_standard(reps, standard):
            result["ready_to_advance"] = True
            result["messages"].append(f"Met PARC progression: {step_def['progression']}")
        height = log.get("height_cm")
        if height and step_def.get("track_height"):
            result["messages"].append(f"Vertical leap height logged: {height} cm")
        return result

    return result


def compute_program_state(
    programs: dict[str, dict],
    sessions: list[dict],
    settings: dict | None = None,
) -> dict[str, Any]:
    """Derive current step/rep level and trends from session history."""
    settings = settings or {}
    state: dict[str, Any] = {}

    for program_id, program in programs.items():
        program_sessions = [session for session in sessions if session.get("program_id") == program_id]
        if program["progression_model"] == "weekly_rep_ramp":
            state[program_id] = compute_tibetan_state(program, program_sessions, settings)
            continue
        if program["progression_model"] == "parc_step":
            state[program_id] = compute_parc_state(program, program_sessions, settings)
            continue
        state[program_id] = compute_cc_state(program, program_sessions, settings)

    return state


def compute_cc_state(program: dict, sessions: list[dict], settings: dict | None = None) -> dict[str, Any]:
    settings = settings or {}
    fitness_settings = get_fitness_settings(settings)
    by_movement: dict[str, Any] = {}
    for movement in program.get("movements", []):
        key = movement["id"]
        logs = []
        for session in sessions:
            for entry in session.get("movement_logs", []):
                if entry.get("movement_key") == key:
                    logs.append({**entry, "date": session["date"]})
        if not logs:
            by_movement[key] = {
                "current_step": 1,
                "step_name": movement["steps"][0]["name"],
                "sessions_at_step": 0,
                "trend": "insufficient_data",
                "ready_to_advance": False,
            }
            continue

        latest = sorted(logs, key=lambda item: item["date"])[-1]
        current_step = int(latest.get("step", 1))
        step_name = latest.get("step_name") or movement["steps"][current_step - 1]["name"]
        at_step = [log for log in logs if int(log.get("step", 1)) == current_step]
        evaluation = evaluate_session_log(
            {
                "movement_key": key,
                "step": current_step,
                "reps_per_set": latest.get("reps_per_set"),
                "hold_seconds": latest.get("hold_seconds"),
                "form_quality": latest.get("form_quality"),
            },
            program,
        )
        met_sessions = cc_sessions_meeting_standard(at_step, program, key, current_step)
        ready = len(met_sessions) >= fitness_settings["cc_sessions_for_advance"] and evaluation["ready_to_advance"]
        item_state = {
            "current_step": current_step,
            "step_name": step_name,
            "sessions_at_step": len(at_step),
            "sessions_meeting_standard": len(met_sessions),
            "last_date": latest["date"],
            "trend": classify_metric_trend(at_step),
            "ready_to_advance": ready,
            "messages": evaluation["messages"],
            "evidence": advancement_evidence(program, at_step, settings),
            "next_action": "",
        }
        item_state["next_action"] = next_suggested_action(program, item_state, settings)
        by_movement[key] = item_state
    return by_movement


def compute_parc_state(program: dict, sessions: list[dict], settings: dict | None = None) -> dict[str, Any]:
    settings = settings or {}
    by_chain: dict[str, Any] = {}
    for chain in program.get("chains", []):
        key = chain["id"]
        logs = []
        for session in sessions:
            for entry in session.get("movement_logs", []):
                if entry.get("chain_key") == key:
                    logs.append({**entry, "date": session["date"]})
        if not logs:
            by_chain[key] = {
                "current_step": 1,
                "step_name": chain["steps"][0]["name"],
                "sessions_at_step": 0,
                "trend": "insufficient_data",
                "ready_to_advance": False,
            }
            continue
        latest = sorted(logs, key=lambda item: item["date"])[-1]
        current_step = int(latest.get("step", 1))
        step_name = latest.get("step_name") or chain["steps"][current_step - 1]["name"]
        at_step = [log for log in logs if int(log.get("step", 1)) == current_step]
        evaluation = evaluate_session_log(
            {
                "chain_key": key,
                "step": current_step,
                "reps_per_set": latest.get("reps_per_set"),
                "height_cm": latest.get("height_cm"),
            },
            program,
        )
        item_state = {
            "current_step": current_step,
            "step_name": step_name,
            "sessions_at_step": len(at_step),
            "last_date": latest["date"],
            "trend": classify_metric_trend(at_step),
            "ready_to_advance": evaluation["ready_to_advance"],
            "messages": evaluation["messages"],
            "evidence": advancement_evidence(program, at_step, settings),
            "next_action": "",
        }
        item_state["next_action"] = next_suggested_action(program, item_state, settings)
        by_chain[key] = item_state
    return by_chain


def compute_tibetan_state(program: dict, sessions: list[dict], settings: dict | None = None) -> dict[str, Any]:
    settings = settings or {}
    fitness_settings = get_fitness_settings(settings)
    if not sessions:
        return {
            "current_week": 1,
            "target_reps": program["rules"]["start_reps_per_rite"],
            "trend": "insufficient_data",
            "ready_to_advance": False,
        }
    latest = sorted(sessions, key=lambda item: item["date"])[-1]
    target = int(latest.get("target_reps", program["rules"]["start_reps_per_rite"]))
    week = 1
    for entry in program.get("weekly_schedule", []):
        if entry["reps_per_rite"] == target:
            week = entry["week"]
            break
    reps = latest.get("reps_per_rite") or {}
    all_met = reps and all(int(reps.get(rite["id"], 0)) >= target for rite in program["movements"])
    streak = tibetan_consecutive_success_days(sessions, program, target)
    needed = fitness_settings["tibetan_advance_consecutive_days"]
    ready = streak >= needed and all_met and target < program["rules"]["target_reps_per_rite"]
    logs = []
    for session in sessions:
        for entry in session.get("movement_logs", []):
            logs.append({**entry, "date": session["date"]})
    item_state = {
        "current_week": week,
        "target_reps": target,
        "consecutive_days": streak,
        "last_date": latest["date"],
        "trend": classify_metric_trend(logs) if logs else "insufficient_data",
        "ready_to_advance": ready,
        "messages": [
            f"Week {week} target: {target} reps per rite",
            f"Consecutive success days: {streak}/{needed}",
        ],
        "evidence": advancement_evidence(program, logs, settings),
        "next_action": "",
    }
    item_state["next_action"] = next_suggested_action(program, item_state, settings)
    return item_state


def classify_trend(logs_at_step: list[dict]) -> str:
    if len(logs_at_step) < 3:
        return "insufficient_data"
    if len(logs_at_step) >= 5:
        return "plateau"
    totals = []
    for log in logs_at_step[-4:]:
        reps = log.get("reps_per_set") or []
        totals.append(sum(reps) if reps else float(log.get("hold_seconds") or 0))
    if len(totals) >= 2 and totals[-1] > totals[0]:
        return "improving"
    return "stable"


def default_fitness_payload() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "sessions": [],
        "program_state": {},
        "user_levels": {},
    }


def migrate_data(payload: dict[str, Any], programs: dict[str, dict]) -> dict[str, Any]:
    if payload.get("schema_version", 1) >= 2:
        payload.setdefault("sessions", [])
        payload.setdefault("milestones", [])
        payload.setdefault("journal", {"prompts": [], "entries": []})
        payload.setdefault("settings", {})
        payload["settings"].setdefault("fitness", get_fitness_settings(payload["settings"]))
        payload["settings"].setdefault("onboarding_complete", False)
        payload["settings"].setdefault("encryption_enabled", False)
        payload["program_state"] = compute_program_state(
            programs, payload["sessions"], payload.get("settings", {})
        )
        return payload

    migrated = {
        "schema_version": 2,
        "categories": payload.get("categories", {}),
        "entries": payload.get("entries", {}),
        "settings": {
            **{"dark_mode": False, "onboarding_complete": False, "encryption_enabled": False},
            **payload.get("settings", {}),
        },
        "sessions": payload.get("sessions", []),
        "milestones": payload.get("milestones", []),
        "program_state": {},
        "user_levels": payload.get("user_levels", {}),
    }
    migrated["settings"]["fitness"] = get_fitness_settings(migrated["settings"])
    migrated["program_state"] = compute_program_state(programs, migrated["sessions"], migrated["settings"])
    return migrated
