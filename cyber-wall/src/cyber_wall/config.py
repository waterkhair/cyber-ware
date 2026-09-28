"""Small shared configuration and XDG path helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


AVAILABLE_THEMES = ("synthwave",)


DEFAULTS: dict[str, Any] = {
    "directories": ["~/Pictures/Wallpapers", "~/Videos/Wallpapers"],
    "output": "auto",
    "default_wallpaper": None,
    "theme": "synthwave",
    "mpvpaper_options": [
        "no-audio",
        "--quiet",
        "--msg-level=all=warn",
        "--loop-file=inf",
        "--image-display-duration=inf",
        "--keep-open=yes",
        "--hwdec=auto",
    ],
    "preview_seek_seconds": 0.5,
    "preview_timeout_seconds": 8,
}


def config_path() -> Path:
    explicit = os.environ.get("CYBER_WALL_CONFIG")
    if explicit:
        return Path(explicit).expanduser()
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "cyber-wall" / "config.json"


def state_dir() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return root / "cyber-wall"


def cache_dir() -> Path:
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "cyber-wall"


def runtime_dir() -> Path:
    root = os.environ.get("XDG_RUNTIME_DIR")
    if root:
        return Path(root) / "cyber-wall"
    return state_dir() / "runtime"


def expand_path(value: str | os.PathLike[str]) -> Path:
    return Path(os.path.expandvars(os.fspath(value))).expanduser()


def load_config() -> dict[str, Any]:
    """Return defaults merged with the optional user JSON configuration."""
    path = config_path()
    result = dict(DEFAULTS)
    result["mpvpaper_options"] = list(DEFAULTS["mpvpaper_options"])

    if path.exists():
        try:
            user = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Cannot read {path}: {error}") from error
        if not isinstance(user, dict):
            raise ValueError(f"Expected a JSON object in {path}")
        result.update(user)

    if not isinstance(result.get("directories"), list) or not all(
        isinstance(item, str) for item in result["directories"]
    ):
        raise ValueError("config 'directories' must be an array of path strings")
    if not isinstance(result.get("mpvpaper_options"), list) or not all(
        isinstance(item, str) for item in result["mpvpaper_options"]
    ):
        raise ValueError("config 'mpvpaper_options' must be an array of strings")
    theme = result.get("theme")
    if not isinstance(theme, str) or theme not in AVAILABLE_THEMES:
        themes = ", ".join(AVAILABLE_THEMES)
        raise ValueError(f"config 'theme' must be one of: {themes}")
    return result
