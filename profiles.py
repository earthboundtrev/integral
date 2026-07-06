import json
import os
import re
import shutil

APP_DIR_NAME = ".personal_dev_tracker"
PROFILES_DIR_NAME = "profiles"
CONFIG_FILE_NAME = "config.json"
DEFAULT_PROFILE_ID = "default"
DEFAULT_PROFILE_NAME = "Default"


def get_app_dir() -> str:
    return os.path.join(os.path.expanduser("~"), APP_DIR_NAME)


def get_profiles_root() -> str:
    return os.path.join(get_app_dir(), PROFILES_DIR_NAME)


def get_config_path() -> str:
    return os.path.join(get_app_dir(), CONFIG_FILE_NAME)


def slugify_profile_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "profile"


def default_config() -> dict:
    return {
        "active_profile_id": DEFAULT_PROFILE_ID,
        "profiles": [{"id": DEFAULT_PROFILE_ID, "name": DEFAULT_PROFILE_NAME}],
    }


def load_config() -> dict:
    ensure_app_structure()
    path = get_config_path()
    if not os.path.exists(path):
        config = default_config()
        save_config(config)
        return config
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)
    config.setdefault("active_profile_id", DEFAULT_PROFILE_ID)
    config.setdefault("profiles", default_config()["profiles"])
    return config


def save_config(config: dict) -> None:
    os.makedirs(get_app_dir(), exist_ok=True)
    with open(get_config_path(), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def list_profiles() -> list[dict]:
    return load_config()["profiles"]


def get_active_profile_id() -> str:
    return load_config()["active_profile_id"]


def get_active_profile() -> dict:
    config = load_config()
    active_id = config["active_profile_id"]
    for profile in config["profiles"]:
        if profile["id"] == active_id:
            return profile
    return config["profiles"][0]


def set_active_profile(profile_id: str) -> dict:
    config = load_config()
    if not any(p["id"] == profile_id for p in config["profiles"]):
        raise ValueError(f"Unknown profile: {profile_id}")
    config["active_profile_id"] = profile_id
    save_config(config)
    return get_profile(profile_id)


def get_profile(profile_id: str) -> dict:
    for profile in load_config()["profiles"]:
        if profile["id"] == profile_id:
            return profile
    raise ValueError(f"Unknown profile: {profile_id}")


def get_profile_dir(profile_id: str | None = None) -> str:
    pid = profile_id or get_active_profile_id()
    return os.path.join(get_profiles_root(), pid)


def create_profile(name: str, profile_id: str | None = None) -> dict:
    config = load_config()
    base_id = profile_id or slugify_profile_id(name)
    candidate = base_id
    suffix = 2
    existing_ids = {p["id"] for p in config["profiles"]}
    while candidate in existing_ids:
        candidate = f"{base_id}-{suffix}"
        suffix += 1

    profile = {"id": candidate, "name": name.strip()}
    config["profiles"].append(profile)
    save_config(config)
    os.makedirs(get_profile_dir(candidate), exist_ok=True)
    return profile


def ensure_app_structure() -> None:
    os.makedirs(get_profiles_root(), exist_ok=True)
    migrate_legacy_layout_if_needed()


def migrate_legacy_layout_if_needed() -> None:
    app_dir = get_app_dir()
    legacy_data = os.path.join(app_dir, "data.json")
    default_dir = get_profile_dir(DEFAULT_PROFILE_ID)
    default_data = os.path.join(default_dir, "data.json")

    os.makedirs(default_dir, exist_ok=True)

    if os.path.exists(legacy_data) and not os.path.exists(default_data):
        shutil.copy2(legacy_data, default_data)

    legacy_fitness = os.path.join(app_dir, "fitness.db")
    default_fitness = os.path.join(default_dir, "fitness.db")
    if os.path.exists(legacy_fitness) and not os.path.exists(default_fitness):
        shutil.copy2(legacy_fitness, default_fitness)

    if not os.path.exists(get_config_path()):
        save_config(default_config())
