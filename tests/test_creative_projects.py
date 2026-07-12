"""Tests for creative writing projects library (SPEC-302)."""

from __future__ import annotations

import os
from pathlib import Path

import creative_projects as cp


def test_normalize_creative_projects_none():
    store = cp.normalize_creative_projects(None)
    assert store == {"schema_version": 1, "projects": []}


def test_normalize_creative_projects_missing_key_shape():
    store = cp.normalize_creative_projects({})
    assert store["projects"] == []
    assert store["schema_version"] == 1


def test_create_project_persists_index_and_empty_files(tmp_path: Path):
    store = cp.empty_creative_projects()
    root = str(tmp_path)
    project = cp.create_project(store, root, title="  River Novel  ", status="drafting")
    assert project["title"] == "River Novel"
    assert project["status"] == "drafting"
    assert project["archived"] is False
    assert len(store["projects"]) == 1
    assert os.path.isfile(cp.document_path(root, project["id"], cp.DOC_INSPIRATION))
    assert os.path.isfile(cp.document_path(root, project["id"], cp.DOC_MANUSCRIPT))
    assert cp.read_document(root, project["id"], cp.DOC_INSPIRATION) == ""
    assert cp.read_document(root, project["id"], cp.DOC_MANUSCRIPT) == ""


def test_create_project_requires_title(tmp_path: Path):
    store = cp.empty_creative_projects()
    try:
        cp.create_project(store, str(tmp_path), title="   ")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_document_round_trip_large_text(tmp_path: Path):
    store = cp.empty_creative_projects()
    root = str(tmp_path)
    project = cp.create_project(store, root, title="Epic")
    blob = ("Once upon a time. " * 500) + "THE END"
    assert len(blob) > 5000
    cp.write_document(root, project["id"], cp.DOC_MANUSCRIPT, blob)
    cp.write_document(root, project["id"], cp.DOC_INSPIRATION, "Premise: " + ("x" * 2000))
    assert cp.read_document(root, project["id"], cp.DOC_MANUSCRIPT) == blob
    assert cp.read_document(root, project["id"], cp.DOC_INSPIRATION).startswith("Premise:")


def test_list_projects_hides_archived_by_default(tmp_path: Path):
    store = cp.empty_creative_projects()
    root = str(tmp_path)
    a = cp.create_project(store, root, title="Active")
    b = cp.create_project(store, root, title="Old Idea")
    cp.archive_project(store, b["id"], archived=True)
    active = cp.list_projects(store, include_archived=False)
    assert [p["id"] for p in active] == [a["id"]]
    all_projects = cp.list_projects(store, include_archived=True)
    assert {p["id"] for p in all_projects} == {a["id"], b["id"]}


def test_delete_project_removes_index_and_files(tmp_path: Path):
    store = cp.empty_creative_projects()
    root = str(tmp_path)
    project = cp.create_project(store, root, title="Gone")
    project_id = project["id"]
    directory = cp.project_dir(root, project_id)
    assert os.path.isdir(directory)
    cp.write_document(root, project_id, cp.DOC_MANUSCRIPT, "draft")
    cp.delete_project(store, root, project_id)
    assert store["projects"] == []
    assert not os.path.exists(directory)


def test_rename_and_status(tmp_path: Path):
    store = cp.empty_creative_projects()
    root = str(tmp_path)
    project = cp.create_project(store, root, title="Draft")
    cp.rename_project(store, project["id"], "Final Title")
    cp.set_project_status(store, project["id"], "revising")
    refreshed = cp.get_project(store, project["id"])
    assert refreshed["title"] == "Final Title"
    assert refreshed["status"] == "revising"
