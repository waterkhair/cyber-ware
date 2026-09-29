"""User-local installer for cyber-panel; no root access or package writes."""

from __future__ import annotations

import json
import os
import shutil
import sys
import hashlib
from pathlib import Path


def main() -> int:
    home = Path.home()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    state_home = Path(os.environ.get("XDG_STATE_HOME", home / ".local/state"))
    prefix = Path(os.environ.get("PREFIX", home / ".local"))
    source = Path(__file__).resolve().parents[2]
    app_dir = data_home / "cyber-panel"
    waybar_dir = config_home / "waybar"
    state_dir = state_home / "cyber-panel"
    backup_dir = state_dir / "backups"
    state_file = state_dir / "install.json"

    missing = [name for name in ("waybar", "hyprctl", "python3") if shutil.which(name) is None]
    if missing:
        print("Missing required dependencies: " + ", ".join(missing), file=sys.stderr)
        print("Install them with your distribution package manager; cyber-panel does not install system packages.", file=sys.stderr)
        return 1

    for name, package in (("playerctl", "playerctl"), ("cyber-console", "the optional floating-tool component")):
        if shutil.which(name) is None:
            print(f"Optional command missing: {name} ({package}); its click action will not work until configured.", file=sys.stderr)

    if not (source / "config.jsonc").is_file() or not (source / "themes/synthwave.css").is_file():
        print("The cyber-panel source files are incomplete.", file=sys.stderr)
        return 1
    waybar_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    state = {"version": 1, "originals": {}, "installed_hashes": {}}
    if state_file.exists():
        try:
            old_state = json.loads(state_file.read_text(encoding="utf-8"))
            if old_state.get("version") != 1:
                raise ValueError("unsupported state version")
            state = old_state
        except (OSError, json.JSONDecodeError, ValueError) as error:
            print(f"Cannot safely reuse existing install state: {error}", file=sys.stderr)
            return 1
    state["command_path"] = str(prefix / "bin/cyber-panel")

    settings_file = config_home / "cyber-panel/config.json"
    settings = {"theme": "synthwave"}
    if settings_file.is_file():
        try:
            previous_settings = json.loads(settings_file.read_text(encoding="utf-8"))
            if not isinstance(previous_settings, dict):
                raise ValueError("expected a JSON object")
            settings.update(previous_settings)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            print(f"Cannot safely preserve existing cyber-panel settings: {error}", file=sys.stderr)
            return 1
    theme = settings.get("theme", "synthwave")
    shared_theme_file = config_home / "cyber-ware/theme"
    if shared_theme_file.is_file():
        try:
            shared_theme = shared_theme_file.read_text(encoding="utf-8").splitlines()[0].strip()
        except (OSError, IndexError):
            shared_theme = ""
        if shared_theme in ("synthwave", "greenline"):
            theme = shared_theme
            settings["theme"] = theme
        elif shared_theme:
            print(f"Ignoring invalid shared cyber-ware theme in {shared_theme_file}.", file=sys.stderr)
    if theme not in ("synthwave", "greenline"):
        print(f"Unknown saved theme {theme!r}; using synthwave.", file=sys.stderr)
        theme = "synthwave"
        settings["theme"] = theme

    # Keep the pre-install copies across upgrades; they are what uninstall restores.
    for name in ("config.jsonc", "style.css"):
        target = waybar_dir / name
        backup = backup_dir / name
        if name not in state["originals"]:
            state["originals"][name] = target.is_file()
            if target.is_file():
                shutil.copy2(target, backup)

    if app_dir.exists():
        shutil.rmtree(app_dir)
    (app_dir / "src").mkdir(parents=True)
    shutil.copytree(source / "src/cyber_panel", app_dir / "src/cyber_panel")
    shutil.copytree(source / "themes", app_dir / "themes")
    shutil.copy2(source / "config.jsonc", app_dir / "config.jsonc")

    config_bytes = (source / "config.jsonc").read_bytes()
    config_target = waybar_dir / "config.jsonc"
    config_target.write_bytes(config_bytes)
    config_target.chmod(0o644)

    style_bytes = (source / "themes" / f"{theme}.css").read_bytes()
    style_target = waybar_dir / "style.css"
    style_target.write_bytes(style_bytes)
    style_target.chmod(0o644)

    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    settings_file.chmod(0o600)

    for name, content in (("config.jsonc", config_bytes), ("style.css", style_bytes)):
        state["installed_hashes"][name] = hashlib.sha256(content).hexdigest()
    state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    state_file.chmod(0o600)

    command_dir = prefix / "bin"
    command_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "bin/cyber-panel", command_dir / "cyber-panel")
    (command_dir / "cyber-panel").chmod(0o755)
    print(f"Installed cyber-panel command in {command_dir}.")
    print(f"Waybar configuration: {config_target}")
    print(f"Theme: {theme} (switch with cyber-panel --theme greenline|synthwave)")
    print(f"Original Waybar files are preserved in {backup_dir}; uninstall with cyber-panel --uninstall.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
