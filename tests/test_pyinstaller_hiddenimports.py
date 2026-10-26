"""PyInstaller hiddenimports must include every app module imported from the entry graph."""

from tests.pyinstaller_import_audit import (
    SPEC_PATH,
    collect_required_app_modules,
    missing_hiddenimports,
    parse_hiddenimports_from_spec,
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
