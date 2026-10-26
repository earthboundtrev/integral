"""PyInstaller hiddenimports must include every app module imported from the entry graph."""

import subprocess
import sys

from tests.pyinstaller_import_audit import (
    REPO_ROOT,
    SPEC_PATH,
    collect_required_app_modules,
    missing_hiddenimports,
    parse_collect_all_packages_from_spec,
    parse_hiddenimports_from_spec,
    parse_static_datas_from_spec,
)


def test_spec_hiddenimports_cover_app_import_graph():
    missing = missing_hiddenimports(SPEC_PATH)
    assert missing == [], (
        "Add these modules to full-spectrum-development.spec hiddenimports: "
        + ", ".join(missing)
    )


def test_spec_file_exists_and_lists_hiddenimports():
    assert SPEC_PATH.is_file()
    hidden = parse_hiddenimports_from_spec(SPEC_PATH)
    assert hidden
    assert "paths" in hidden


def test_entry_graph_includes_recent_ui_modules():
    required = collect_required_app_modules()
    for name in (
        "sidebar_nav",
        "deferred_toplevel",
        "busy_indicator",
        "ui_accent",
    ):
        assert name in required


def test_import_from_submodule_style_is_resolved():
    """from pkg import submodule must resolve to pkg.submodule when that file exists."""
    import ast

    from tests.pyinstaller_import_audit import _import_from_targets

    node = ast.parse("from progression import recent_compare").body[0]
    targets = _import_from_targets(node, "progression.sessions")
    assert "progression.recent_compare" in targets


def test_onefile_static_datas_match_spec():
    datas = parse_static_datas_from_spec(SPEC_PATH)
    assert ("programs", "programs") in datas
    assert ("assets", "assets") in datas
    assert any(dest == "progression/seed/v1" for _src, dest in datas)


def test_onefile_collect_all_matches_spec_matplotlib():
    assert "matplotlib" in parse_collect_all_packages_from_spec(SPEC_PATH)


def test_print_onefile_script_emits_one_module_per_line():
    """build-onefile.ps1 reads hiddenimports as plain lines (PS 5.1-safe, no JSON)."""
    result = subprocess.run(
        [sys.executable, "scripts/print_onefile_from_spec.py", "hiddenimports"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) > 50
    assert "sidebar_nav" in lines
    assert all("|" not in line and not line.startswith("[") for line in lines)
    assert lines == sorted(lines)


def test_print_onefile_add_data_uses_pipe_delimiter():
    result = subprocess.run(
        [sys.executable, "scripts/print_onefile_from_spec.py", "add-data"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert any(line == "programs|programs" for line in lines)
    assert any(line.endswith("|progression/seed/v1") for line in lines)
