"""Configuration and paths for cyber-wave."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

THEMES = ("synthwave", "greenline", "husky")
DEFAULT = {
    "theme": "synthwave",
    "stations": [{
        "name": "Esoterica Radio S3",
        "url": "https://esoterica.servemp3.com:444/listen/darkbasshouse_cyberpunk_hybridtrap/radio.mp3",
    }],
}


def paths() -> dict[str, Path]:
    home = Path.home()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    prefix = Path(os.environ.get("PREFIX", home / ".local"))
    return {
        "config": config_home / "cyber-wave/config.json",
        "theme": config_home / "cyber-wave/theme",
        "shared_theme": config_home / "cyber-ware/theme",
        "data": data_home / "cyber-wave",
        "runtime": runtime / "cyber-wave",
        "prefix": prefix,
        "command": Path(os.environ.get("CYBER_WAVE_COMMAND", prefix / "bin/cyber-wave")),
    }


def current_theme() -> str:
    p = paths()
    for path in (p["theme"], p["shared_theme"]):
        try:
            value = path.read_text(encoding="utf-8").splitlines()[0].strip()
        except (OSError, IndexError):
            continue
        if value in THEMES:
            return value
    try:
        config = json.loads(p["config"].read_text(encoding="utf-8"))
        value = config.get("theme") if isinstance(config, dict) else None
    except (OSError, json.JSONDecodeError):
        value = None
    return value if value in THEMES else "synthwave"


def load_config() -> dict:
    path = paths()["config"]
    if path.is_symlink():
        raise ValueError(f"Refusing a symlinked configuration file: {path}")
    if path.is_file():
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Cannot read {path}: {error}") from error
    else:
        config = json.loads(json.dumps(DEFAULT))
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object.")
    theme = config.get("theme", current_theme())
    if theme not in THEMES:
        raise ValueError(f"theme must be one of: {', '.join(THEMES)}")
    config["stations"] = normalize_stations(config.get("stations"))
    config["theme"] = theme
    return config


def validate_station(station: dict) -> dict:
    if not isinstance(station, dict):
        raise ValueError("A station must have a name and URL")
    name, url = station.get("name"), station.get("url")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        raise ValueError("Name must contain 1–120 characters")
    if not isinstance(url, str) or any(c in url for c in "\r\n\0"):
        raise ValueError("URL must be a valid HTTP(S) stream address")
    parsed = urlsplit(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("URL must be a valid HTTP(S) stream address")
    return {"name": name.strip(), "url": url.strip()}


def normalize_stations(stations: object) -> list[dict]:
    if not isinstance(stations, list):
        raise ValueError("stations must be an array of {name, url} objects")
    normalized = []
    seen = set()
    for station in stations:
        normalized_station = validate_station(station)
        if normalized_station["url"] in seen:
            continue
        seen.add(normalized_station["url"])
        normalized.append(normalized_station)
    return normalized


def save_config(config: dict) -> None:
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object")
    theme = config.get("theme", current_theme())
    if theme not in THEMES:
        raise ValueError(f"theme must be one of: {', '.join(THEMES)}")
    path = paths()["config"]
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError(f"Refusing a symlinked configuration path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(config)
    data["theme"] = theme
    data["stations"] = normalize_stations(config.get("stations"))
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if temp.is_symlink():
        raise ValueError(f"Refusing a symlinked temporary configuration path: {temp}")
    try:
        temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp.chmod(0o600)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def set_theme(theme: str) -> None:
    if theme not in THEMES:
        raise ValueError(f"theme must be one of: {', '.join(THEMES)}")
    path = paths()["theme"]
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f"Refusing an unsafe theme selection path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temp.write_text(theme + "\n", encoding="utf-8")
        temp.chmod(0o600)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
