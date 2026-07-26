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
            fieldnames=[
                "year",
                "quarter",
                "title",
                "status",
                "notes",
                "completed_date",
                "domain",
                "progress",
            ],
            extrasaction="ignore",
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


FULL_BACKUP_KIND = "integral_full"
FULL_BACKUP_VERSION = 1


def _iter_creative_files(creative_root: str) -> list[tuple[str, str]]:
    """Return (absolute_path, arcname) pairs under creative_root."""
    if not creative_root or not os.path.isdir(creative_root):
        return []
    pairs: list[tuple[str, str]] = []
    for dirpath, _dirnames, filenames in os.walk(creative_root):
        for name in filenames:
            abs_path = os.path.join(dirpath, name)
            rel = os.path.relpath(abs_path, creative_root).replace("\\", "/")
            pairs.append((abs_path, f"creative/{rel}"))
    return pairs


def export_creative_documents_zip(creative_root: str, path: str) -> int:
    """Zip inspiration/manuscript files for CSV Export. Returns file count."""
    import zipfile

    pairs = _iter_creative_files(creative_root)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for abs_path, arcname in pairs:
            zf.write(abs_path, arcname)
        zf.writestr(
            "README.txt",
            "Integral creative writing documents.\n"
            "For a full restore (index + files + life data), use Backup → Export Backup (zip).\n",
        )
    return len(pairs)


def write_full_backup(
    payload: dict,
    path: str,
    *,
    creative_root: str | None = None,
    fitness_db_path: str | None = None,
) -> dict[str, Any]:
    """Write a full-fidelity zip: data.json + creative/ + optional fitness.db."""
    import zipfile

    from paths import creative_projects_dir

    creative_root = creative_root if creative_root is not None else creative_projects_dir()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    creative_files = _iter_creative_files(creative_root)
    has_fitness = bool(fitness_db_path and os.path.isfile(fitness_db_path))
    manifest = {
        "backup_kind": FULL_BACKUP_KIND,
        "backup_version": FULL_BACKUP_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "backup_app": "Integral",
        "has_creative": bool(creative_files),
        "has_fitness": has_fitness,
        "creative_file_count": len(creative_files),
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "data.json",
            json.dumps(backup_payload(payload), indent=2, ensure_ascii=False),
        )
        for abs_path, arcname in creative_files:
            zf.write(abs_path, arcname)
        if has_fitness:
            zf.write(fitness_db_path, "fitness.db")
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def is_full_backup_zip(path: str) -> bool:
    import zipfile

    if not path.lower().endswith(".zip"):
        return False
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = set(zf.namelist())
            if "manifest.json" in names and "data.json" in names:
                manifest = json.loads(zf.read("manifest.json"))
                return manifest.get("backup_kind") == FULL_BACKUP_KIND
            # Accept zip that simply has data.json + creative/ (forward-compatible).
            return "data.json" in names
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError):
        return False


def restore_full_backup(
    path: str,
    target_data_path: str,
    *,
    creative_root: str | None = None,
    fitness_db_path: str | None = None,
    make_copy: bool = True,
) -> dict[str, Any]:
    """Restore a full zip backup (data.json + creative/ + optional fitness.db)."""
    import zipfile

    from paths import creative_projects_dir

    creative_root = creative_root if creative_root is not None else creative_projects_dir()
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        if "data.json" not in names:
            raise ValueError("Full backup missing data.json")
        payload = json.loads(zf.read("data.json"))
        if not isinstance(payload, dict):
            raise ValueError("Backup data.json is not a valid object.")
        restore_backup_to_path(payload, target_data_path, make_copy=make_copy)

        os.makedirs(creative_root, exist_ok=True)
        restored_docs = 0
        for name in names:
            if not name.startswith("creative/") or name.endswith("/"):
                continue
            rel = name[len("creative/") :]
            if not rel or ".." in rel.split("/"):
                continue
            dest = os.path.join(creative_root, *rel.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(name) as src, open(dest, "wb") as dst:
                dst.write(src.read())
            restored_docs += 1

        fitness_restored = False
        if fitness_db_path and "fitness.db" in names:
            os.makedirs(os.path.dirname(fitness_db_path) or ".", exist_ok=True)
            if make_copy and os.path.exists(fitness_db_path):
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                shutil.copy2(fitness_db_path, f"{fitness_db_path}.bak-{stamp}")
            with zf.open("fitness.db") as src, open(fitness_db_path, "wb") as dst:
                dst.write(src.read())
            fitness_restored = True

        manifest: dict[str, Any] = {}
        if "manifest.json" in names:
            try:
                manifest = json.loads(zf.read("manifest.json"))
            except json.JSONDecodeError:
                manifest = {}
        manifest["restored_creative_files"] = restored_docs
        manifest["restored_fitness"] = fitness_restored
        return manifest


def restore_backup_file(
    path: str,
    target_data_path: str,
    *,
    creative_root: str | None = None,
    fitness_db_path: str | None = None,
    make_copy: bool = True,
) -> dict[str, Any]:
    """Restore from full zip or legacy JSON. Returns a small result dict."""
    if is_full_backup_zip(path):
        return restore_full_backup(
            path,
            target_data_path,
            creative_root=creative_root,
            fitness_db_path=fitness_db_path,
            make_copy=make_copy,
        )
    backup = load_backup(path)
    restore_backup_to_path(backup, target_data_path, make_copy=make_copy)
    return {
        "backup_kind": "legacy_json",
        "restored_creative_files": 0,
        "restored_fitness": False,
        "warning": (
            "JSON backup restores the library index only — writing documents under "
            "creative/ are not included. Prefer a full .zip backup next time."
        ),
    }
