"""Creative writing projects — library index + on-disk documents."""

from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime
from typing import Any

SCHEMA_VERSION = 1

STATUSES = ("idea", "drafting", "revising", "done")

DOC_INSPIRATION = "inspiration"
DOC_MANUSCRIPT = "manuscript"
DOC_ROLES = (DOC_INSPIRATION, DOC_MANUSCRIPT)

_DOC_FILENAMES = {
    DOC_INSPIRATION: "inspiration.txt",
    DOC_MANUSCRIPT: "manuscript.txt",
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_project_id() -> str:
    return uuid.uuid4().hex[:12]


def empty_creative_projects() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "projects": []}


def normalize_creative_projects(stored: dict[str, Any] | None) -> dict[str, Any]:
    base = empty_creative_projects()
    if not stored or not isinstance(stored, dict):
        return base

    projects: list[dict[str, Any]] = []
    for raw in stored.get("projects") or []:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        status = str(raw.get("status") or "idea").strip().lower()
        if status not in STATUSES:
            status = "idea"
        tags_raw = raw.get("tags") or []
        tags = [str(t).strip() for t in tags_raw if str(t).strip()] if isinstance(tags_raw, list) else []
        projects.append(
            {
                "id": str(raw.get("id") or new_project_id()),
                "title": title,
                "status": status,
                "tags": tags,
                "notes": str(raw.get("notes") or "").strip(),
                "created_at": str(raw.get("created_at") or _now_iso()),
                "updated_at": str(raw.get("updated_at") or _now_iso()),
                "archived": bool(raw.get("archived", False)),
            }
        )

    base["schema_version"] = int(stored.get("schema_version") or SCHEMA_VERSION)
    base["projects"] = projects
    return base


def list_projects(store: dict[str, Any], *, include_archived: bool = False) -> list[dict[str, Any]]:
    projects = list(store.get("projects") or [])
    if include_archived:
        return projects
    return [p for p in projects if not p.get("archived")]


def get_project(store: dict[str, Any], project_id: str) -> dict[str, Any] | None:
    for project in store.get("projects") or []:
        if project.get("id") == project_id:
            return project
    return None


def project_dir(root: str, project_id: str) -> str:
    return os.path.join(root, project_id)


def document_path(root: str, project_id: str, role: str) -> str:
    if role not in _DOC_FILENAMES:
        raise ValueError(f"Unknown document role: {role}")
    return os.path.join(project_dir(root, project_id), _DOC_FILENAMES[role])


def ensure_project_documents(root: str, project_id: str) -> None:
    directory = project_dir(root, project_id)
    os.makedirs(directory, exist_ok=True)
    for role in DOC_ROLES:
        path = document_path(root, project_id, role)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("")


def read_document(root: str, project_id: str, role: str) -> str:
    path = document_path(root, project_id, role)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def write_document(root: str, project_id: str, role: str, text: str) -> None:
    ensure_project_documents(root, project_id)
    path = document_path(root, project_id, role)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text if text is not None else "")


def create_project(
    store: dict[str, Any],
    root: str,
    *,
    title: str,
    status: str = "idea",
    tags: list[str] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    cleaned = title.strip()
    if not cleaned:
        raise ValueError("Project title is required.")
    status_key = status.strip().lower() if status else "idea"
    if status_key not in STATUSES:
        status_key = "idea"
    now = _now_iso()
    project = {
        "id": new_project_id(),
        "title": cleaned,
        "status": status_key,
        "tags": [t.strip() for t in (tags or []) if t and str(t).strip()],
        "notes": (notes or "").strip(),
        "created_at": now,
        "updated_at": now,
        "archived": False,
    }
    store.setdefault("projects", []).append(project)
    store["schema_version"] = SCHEMA_VERSION
    ensure_project_documents(root, project["id"])
    return project


def rename_project(store: dict[str, Any], project_id: str, title: str) -> dict[str, Any]:
    project = get_project(store, project_id)
    if project is None:
        raise KeyError(f"Unknown project: {project_id}")
    cleaned = title.strip()
    if not cleaned:
        raise ValueError("Project title is required.")
    project["title"] = cleaned
    project["updated_at"] = _now_iso()
    return project


def set_project_status(store: dict[str, Any], project_id: str, status: str) -> dict[str, Any]:
    project = get_project(store, project_id)
    if project is None:
        raise KeyError(f"Unknown project: {project_id}")
    status_key = status.strip().lower()
    if status_key not in STATUSES:
        raise ValueError(f"Invalid status: {status}")
    project["status"] = status_key
    project["updated_at"] = _now_iso()
    return project


def archive_project(store: dict[str, Any], project_id: str, archived: bool = True) -> dict[str, Any]:
    project = get_project(store, project_id)
    if project is None:
        raise KeyError(f"Unknown project: {project_id}")
    project["archived"] = bool(archived)
    project["updated_at"] = _now_iso()
    return project


def touch_project(store: dict[str, Any], project_id: str) -> dict[str, Any]:
    project = get_project(store, project_id)
    if project is None:
        raise KeyError(f"Unknown project: {project_id}")
    project["updated_at"] = _now_iso()
    return project


def delete_project(store: dict[str, Any], root: str, project_id: str) -> None:
    projects = store.get("projects") or []
    remaining = [p for p in projects if p.get("id") != project_id]
    if len(remaining) == len(projects):
        raise KeyError(f"Unknown project: {project_id}")
    store["projects"] = remaining
    directory = project_dir(root, project_id)
    if os.path.isdir(directory):
        shutil.rmtree(directory)
