import os
import sys
from pathlib import Path

import paths
from progression.seed_loader import SEED_DIR, load_seed_file


def test_dev_bundle_root_is_project_root():
    assert not paths.is_frozen()
    assert paths.bundle_root() == Path(__file__).resolve().parent.parent


def test_app_resource_resolves_seed_in_dev():
    seed_path = paths.app_resource("progression", "seed", "v1", "cc1_push.json")
    assert seed_path.exists()


def test_seed_loader_uses_app_resource(monkeypatch, tmp_path):
    fake_root = tmp_path / "bundle"
    seed_dir = fake_root / "progression" / "seed" / "v1"
    seed_dir.mkdir(parents=True)
    payload = {
        "source_book": "CC1",
        "family": "push",
        "version": "v1",
        "exercises": [],
        "edges": [],
    }
    import json

    with open(seed_dir / "cc1_push.json", "w", encoding="utf-8") as f:
        json.dump(payload, f)

    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(paths, "bundle_root", lambda: fake_root)

    import progression.seed_loader as loader

    monkeypatch.setattr(loader, "SEED_DIR", paths.app_resource("progression", "seed", "v1"))
    data = loader.load_seed_file("cc1_push.json")
    assert data["source_book"] == "CC1"


def test_dev_data_file_uses_canonical_user_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "is_frozen", lambda: False)
    monkeypatch.delenv(paths.INTEGRAL_DATA_DIR_ENV, raising=False)
    monkeypatch.delenv(paths.INTEGRAL_TEST_BUILD_ENV, raising=False)
    monkeypatch.setattr(paths, "ci_test_build_bundled", lambda: False)
    if sys.platform == "win32":
        appdata = tmp_path / "AppData" / "Roaming"
        appdata.mkdir(parents=True)
        monkeypatch.setenv("APPDATA", str(appdata))
        expected = os.path.join(str(appdata), "Integral", "data.json")
    else:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        expected = os.path.join(str(home), ".integral", "data.json")
    assert paths.data_file() == expected


def test_user_data_dir_unchanged_when_frozen(monkeypatch):
    import profiles
    import sys

    monkeypatch.delenv(paths.INTEGRAL_DATA_DIR_ENV, raising=False)
    monkeypatch.delenv(paths.INTEGRAL_TEST_BUILD_ENV, raising=False)
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(paths, "ci_test_build_bundled", lambda: False)
    app_dir = profiles.get_app_dir()
    if sys.platform == "win32":
        assert app_dir.endswith(os.path.join("AppData", "Roaming", "Integral")) or app_dir.endswith(
            "Integral"
        )
        assert not app_dir.endswith("Integral-test")
    else:
        assert str(app_dir).endswith(".integral")
        assert not str(app_dir).endswith(".integral-test")
    assert "MEIPASS" not in str(app_dir)
    assert "dist" not in str(app_dir)


def test_integral_data_dir_override(monkeypatch, tmp_path):
    custom = tmp_path / "custom-root"
    custom.mkdir()
    monkeypatch.setenv(paths.INTEGRAL_DATA_DIR_ENV, str(custom))
    monkeypatch.setattr(paths, "is_frozen", lambda: False)
    assert paths.user_data_dir() == str(custom)
    assert paths.data_file() == os.path.join(str(custom), "data.json")
    assert paths.show_test_build_window_marker()


def test_test_build_env_uses_integral_test_slug(monkeypatch):
    monkeypatch.delenv(paths.INTEGRAL_DATA_DIR_ENV, raising=False)
    monkeypatch.setenv(paths.INTEGRAL_TEST_BUILD_ENV, "1")
    monkeypatch.setattr(paths, "is_frozen", lambda: False)
    monkeypatch.setattr(paths, "ci_test_build_bundled", lambda: False)
    if sys.platform == "win32":
        appdata = os.path.join("C:", "Users", "Tester", "AppData", "Roaming")
        monkeypatch.setenv("APPDATA", appdata)
        assert paths.user_data_dir() == os.path.join(appdata, "Integral-test")
    else:
        monkeypatch.setenv("HOME", "/home/tester")
        assert paths.user_data_dir() == "/home/tester/.integral-test"
    assert paths.show_test_build_window_marker()


def test_ci_marker_selects_test_slug_on_windows(monkeypatch):
    monkeypatch.delenv(paths.INTEGRAL_DATA_DIR_ENV, raising=False)
    monkeypatch.delenv(paths.INTEGRAL_TEST_BUILD_ENV, raising=False)
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(paths, "ci_test_build_bundled", lambda: True)
    monkeypatch.setattr(
        paths,
        "bundle_dir",
        lambda: os.path.join("C:", "fake", "_MEI123"),
    )
    if sys.platform == "win32":
        appdata = os.path.join("C:", "Users", "Tester", "AppData", "Roaming")
        monkeypatch.setenv("APPDATA", appdata)
        assert paths.user_data_dir() == os.path.join(appdata, "Integral-test")
    else:
        monkeypatch.setenv("HOME", "/home/tester")
        assert paths.user_data_dir() == "/home/tester/.integral-test"
