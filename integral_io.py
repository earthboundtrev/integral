"""Export, import, and backup for Integral data."""

from __future__ import annotations

import csv
import json
import os
import shutil
from datetime import datetime
from typing import Any


def export_life_entries_csv(entries: dict, categories: dict, path: str) -> int:
    rows_written = 0
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["date", "category", "rating", "checklist_done", "checklist_total", "metrics", "notes"]
        )
        for date_str in sorted(entries.keys()):
            for category, entry in entries[date_str].items():
                checklist = entry.get("checklist", {})
                done = sum(1 for value in checklist.values() if value)
                total = len(checklist)
                metrics = json.dumps(entry.get("metrics", {}), ensure_ascii=False)
                writer.writerow(
                    [
                        date_str,
                        category,
                        entry.get("rating", ""),
                        done,
                        total,
                        metrics,
                        entry.get("notes", ""),
                    ]
                )
                rows_written += 1
    return rows_written


def export_fitness_sessions_csv(sessions: list[dict], programs: dict[str, dict], path: str) -> int:
    rows_written = 0
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "date",
                "program",
                "movement",
                "step",
                "reps_per_set",
                "hold_seconds",
                "height_cm",
                "form_quality",
                "target_reps",
                "reps_per_rite",
                "session_rpe",
                "duration_min",
                "session_notes",
                "log_notes",
            ]
        )
        for session in sorted(sessions, key=lambda item: item.get("date", "")):
            program = programs.get(session.get("program_id", ""), {})
            program_name = program.get("name", session.get("program_id", ""))
            for log in session.get("movement_logs", []):
                writer.writerow(
                    [
                        session.get("date", ""),
                        program_name,
                        log.get("movement_name") or log.get("chain_name") or log.get("movement_key", ""),
                        log.get("step", ""),
                        "/".join(str(value) for value in log.get("reps_per_set", [])),
                        log.get("hold_seconds", ""),
                        log.get("height_cm", ""),
                        log.get("form_quality", ""),
                        log.get("target_reps", ""),
                        json.dumps(log.get("reps_per_rite", {}), ensure_ascii=False),
                        session.get("session_rpe", ""),
                        session.get("duration_min", ""),
                        session.get("notes", ""),
                        log.get("notes", ""),
                    ]
                )
                rows_written += 1
    return rows_written


def export_milestones_csv(milestones: list[dict], path: str) -> int:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["year", "quarter", "title", "status", "notes", "completed_date"],
        )
        writer.writeheader()
        for item in milestones:
            writer.writerow(item)
    return len(milestones)


def export_journal_csv(journal: dict, path: str) -> int:
    from journal import export_rows

    rows = export_rows(journal)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["entry_date", "written_at", "prompt", "title", "body", "backdate_reason"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def backup_payload(payload: dict) -> dict:
    return {
        **payload,
        "backup_exported_at": datetime.now().isoformat(timespec="seconds"),
        "backup_app": "Integral",
    }


def write_backup(payload: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(backup_payload(payload), handle, indent=2, ensure_ascii=False)


def load_backup(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Backup file is not a valid JSON object.")
    return data


def restore_backup_to_path(backup: dict, target_path: str, *, make_copy: bool = True) -> None:
    if make_copy and os.path.exists(target_path):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(target_path, f"{target_path}.bak-{stamp}")
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    clean = {key: value for key, value in backup.items() if not str(key).startswith("backup_")}
    with open(target_path, "w", encoding="utf-8") as handle:
        json.dump(clean, handle, indent=2, ensure_ascii=False)
