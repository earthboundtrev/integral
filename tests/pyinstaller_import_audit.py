"""Discover app modules reachable from the entry script vs PyInstaller hiddenimports."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "full-spectrum-development.spec"
ENTRY_MODULE = "personal_dev_tracker"
ENTRY_SCRIPT = REPO_ROOT / "personal_dev_tracker.py"

_EXCLUDE_DIRS = frozenset(
    {"tests", "scripts", ".git", ".cursor", "build", "dist", "__pycache__"}
)


def _top_level_py_modules() -> set[str]:
    return {p.stem for p in REPO_ROOT.glob("*.py")}


def _app_packages() -> set[str]:
    pkgs: set[str] = set()
    for child in REPO_ROOT.iterdir():
        if (
            child.is_dir()
            and (child / "__init__.py").is_file()
            and child.name not in _EXCLUDE_DIRS
        ):
            pkgs.add(child.name)
    return pkgs


def _is_app_module(module_name: str) -> bool:
    top = module_name.split(".", 1)[0]
    return top in _top_level_py_modules() or top in _app_packages()


def _path_for_module(module_name: str) -> Path | None:
    parts = module_name.split(".")
    top = parts[0]
    if top in _top_level_py_modules() and len(parts) == 1:
        path = REPO_ROOT / f"{top}.py"
        return path if path.is_file() else None
    if top in _app_packages():
        if len(parts) == 1:
            return REPO_ROOT / top / "__init__.py"
        rel_parts = parts[1:]
        module_py = REPO_ROOT / top / Path(*rel_parts).with_suffix(".py")
        if module_py.is_file():
            return module_py
        pkg_init = REPO_ROOT / top / Path(*rel_parts) / "__init__.py"
        if pkg_init.is_file():
            return pkg_init
    return None


def _import_from_targets(node: ast.ImportFrom, package_module: str) -> set[str]:
    """Resolve ImportFrom to absolute module names (including submodule imports)."""
    base = node.module
    if node.level:
        pkg_parts = package_module.split(".")
        if node.level > len(pkg_parts):
            return set()
        anchor = pkg_parts[: len(pkg_parts) - node.level]
        if base:
            anchor = anchor + base.split(".")
        base = ".".join(anchor) if anchor else None

    targets: set[str] = set()
    for alias in node.names:
        if alias.name == "*":
            if base:
                targets.add(base)
            continue
        if base is None:
            continue
        submodule = f"{base}.{alias.name}"
        if _path_for_module(submodule) is not None:
            targets.add(submodule)
        else:
            targets.add(base)
    return targets


def _imports_in_file(path: Path, package_module: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            found.update(_import_from_targets(node, package_module))
    return found


def collect_required_app_modules(
    entry_module: str = ENTRY_MODULE,
    entry_script: Path = ENTRY_SCRIPT,
) -> set[str]:
    """All app package modules imported (any depth) from the entry script graph."""
    required: set[str] = set()
    seen: set[str] = set()
    queue = [entry_module]

    while queue:
        module_name = queue.pop(0)
        if module_name in seen:
            continue
        seen.add(module_name)

        if module_name == entry_module:
            path = entry_script
        else:
            path = _path_for_module(module_name)
        if path is None:
            continue

        required.add(module_name)
        for imported in _imports_in_file(path, module_name):
            if not _is_app_module(imported):
                continue
            if imported not in seen:
                queue.append(imported)
            required.add(imported)

    return required


def parse_hiddenimports_from_spec(spec_path: Path = SPEC_PATH) -> set[str]:
    tree = ast.parse(spec_path.read_text(encoding="utf-8"), filename=str(spec_path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "Analysis"):
            continue
        for keyword in node.keywords:
            if keyword.arg != "hiddenimports" or not isinstance(keyword.value, ast.List):
                continue
            hidden: set[str] = set()
            for element in keyword.value.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    hidden.add(element.value)
            return hidden
    raise ValueError(f"Analysis(hiddenimports=[...]) not found in {spec_path}")


def missing_hiddenimports(
    spec_path: Path = SPEC_PATH,
) -> list[str]:
    required = collect_required_app_modules() - {ENTRY_MODULE}
    hidden = parse_hiddenimports_from_spec(spec_path)
    return sorted(required - hidden)
