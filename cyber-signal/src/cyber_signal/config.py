"""Configuration and XDG paths for cyber-signal."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_NAME = "cyber-signal"
THEMES = ("synthwave", "greenline", "husky")
DEFAULTS: dict[str, Any] = {
    "theme": "synthwave",
    "network_poll_seconds": 10,
    "disk_warning_percent": 90,
    "disk_critical_percent": 95,
    "disk_mounts": ["/", "/home"],
    "update_detail_limit": 8,
    "checks": {"network": True, "updates": True, "disk": True},
}


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def state_home() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))


def config_dir() -> Path:
    return config_home() / APP_NAME


def state_dir() -> Path:
    return state_home() / APP_NAME


def app_dir() -> Path:
    override = os.environ.get("CYBER_SIGNAL_HOME")
    return Path(override) if override else data_home() / APP_NAME


def install_manifest() -> Path:
    return app_dir() / "install.json"


def load_config() -> dict[str, Any]:
    path = config_dir() / "config.json"
    config = json.loads(json.dumps(DEFAULTS))
    if path.exists():
        with path.open(encoding="utf-8") as stream:
            user_config = json.load(stream)
        if not isinstance(user_config, dict):
            raise ValueError(f"{path} must contain a JSON object")
        config.update(user_config)
        checks = user_config.get("checks", {})
        if not isinstance(checks, dict):
            raise ValueError("checks must be an object with network, updates, and disk booleans")
        config["checks"] = {**DEFAULTS["checks"], **checks}
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    if config.get("theme") not in THEMES:
        raise ValueError(f"theme must be one of: {', '.join(THEMES)}")
    interval = config.get("network_poll_seconds")
    if not isinstance(interval, int) or not 2 <= interval <= 3600:
        raise ValueError("network_poll_seconds must be an integer from 2 to 3600")
    warning = config.get("disk_warning_percent")
    critical = config.get("disk_critical_percent")
    if not (isinstance(warning, int) and isinstance(critical, int)
            and 1 <= warning < critical <= 100):
        raise ValueError("disk thresholds must satisfy 1 <= warning < critical <= 100")
    mounts = config.get("disk_mounts")
    if not isinstance(mounts, list) or not all(isinstance(mount, str) for mount in mounts):
        raise ValueError("disk_mounts must be a list of mount-point strings")
    detail_limit = config.get("update_detail_limit")
    if not isinstance(detail_limit, int) or not 1 <= detail_limit <= 50:
        raise ValueError("update_detail_limit must be an integer from 1 to 50")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_state(name: str, default: Any = None) -> Any:
    path = state_dir() / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_state(name: str, value: Any) -> None:
    atomic_json(state_dir() / name, value)
