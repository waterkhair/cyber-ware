"""Paths and theme selection for cyber-deck."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

THEMES = ("synthwave", "greenline")


def config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "cyber-deck"


def data_dir() -> Path:
    return Path(os.environ.get("CYBER_DECK_HOME", Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "cyber-deck"))


def theme_path() -> Path:
    return config_dir() / "theme"


def current_theme() -> str:
    path = theme_path()
    if not path.exists():
        return "synthwave"
    try:
        theme = path.read_text(encoding="utf-8").splitlines()[0].strip()
    except (OSError, IndexError) as error:
        raise RuntimeError(f"Cannot read theme selection at {path}: {error}") from error
    if theme not in THEMES:
        raise RuntimeError(f"Unknown theme in {path}; choose one of: {', '.join(THEMES)}")
    return theme


def set_theme(theme: str) -> None:
    if theme not in THEMES:
        raise ValueError(f"theme must be one of: {', '.join(THEMES)}")
    path = theme_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="theme.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(theme + "\n")
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def fuzzel_config(theme: str | None = None) -> Path:
    selected = theme or current_theme()
    if selected not in THEMES:
        raise ValueError(f"theme must be one of: {', '.join(THEMES)}")
    path = config_dir() / "themes" / f"{selected}.ini"
    if not path.is_file():
        raise RuntimeError(f"Theme config is missing: {path}; reinstall cyber-deck to restore it")
    return path
