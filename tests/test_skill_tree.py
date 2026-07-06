import ast

from fitness_ui import ensure_fitness_seeded
from progression.db import FitnessRepository
from progression.engine import record_performance
from skill_tree import STATUS_COLORS, build_skill_tree_model


def make_repo(tmp_path):
    return FitnessRepository(str(tmp_path / "fitness.db"))


def test_skill_tree_seeds_empty_db_and_builds_full_model(tmp_path):
    repo = make_repo(tmp_path)
    model = build_skill_tree_model(repo)

    assert len(model["nodes"]) == 91
    assert len(model["edges"]) > 50
    push_nodes = [n for n in model["nodes"] if "Wall Push-ups" in n["label"]]
    assert len(push_nodes) == 1


def test_skill_tree_filter_by_book(tmp_path):
    repo = make_repo(tmp_path)
    model = build_skill_tree_model(repo, source_book="SS")
    assert len(model["nodes"]) == 5
    assert all("Back Squat" in n["label"] or "Bench" in n["label"] or "Deadlift" in n["label"]
               or "Overhead" in n["label"] or "Power Clean" in n["label"] for n in model["nodes"])


def test_skill_tree_colors_mastered_and_available_nodes(tmp_path):
    repo = make_repo(tmp_path)
    ensure_fitness_seeded(repo)
    wall = next(ex for ex in repo.list_exercises() if ex.name == "Wall Push-ups")
    incline = next(ex for ex in repo.list_exercises() if ex.name == "Incline Push-ups")

    record_performance(repo, wall.id, {"sets": 3, "reps": 50})
    model = build_skill_tree_model(repo, source_book="CC1", family="push")
    nodes = {node["id"]: node for node in model["nodes"]}

    assert nodes[wall.id]["status"] == "mastered"
    assert nodes[wall.id]["color"] == STATUS_COLORS["mastered"]
    assert nodes[incline.id]["status"] == "available"
    assert nodes[incline.id]["color"] == STATUS_COLORS["available"]


def test_skill_tree_layout_groups_by_family_columns(tmp_path):
    repo = make_repo(tmp_path)
    model = build_skill_tree_model(repo, source_book="CC1")
    xs = sorted({node["x"] for node in model["nodes"]})
    assert len(xs) >= 5


def test_skill_tree_module_has_no_heavy_imports_at_module_import_time():
    with open("skill_tree.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert "matplotlib" not in imports
    assert "networkx" not in imports
    assert "graphviz" not in imports
    assert "tkinter" not in imports
