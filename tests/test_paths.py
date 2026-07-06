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


def test_user_data_dir_unchanged_when_frozen(monkeypatch):
    import profiles

    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    app_dir = profiles.get_app_dir()
    assert str(app_dir).endswith(".personal_dev_tracker")
    assert "MEIPASS" not in str(app_dir)
    assert "dist" not in str(app_dir)
