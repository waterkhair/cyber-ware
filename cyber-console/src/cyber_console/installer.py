"""User-local installer for cyber-console."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


def main() -> int:
    home = Path.home()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    prefix = Path(os.environ.get("PREFIX", home / ".local"))
    source = Path(__file__).resolve().parents[2]
    app_dir = data_home / "cyber-console"
    config_file = config_home / "cyber-console/config.json"

    required = ("python3", "ghostty", "hyprctl")
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        print("Missing required dependencies: " + ", ".join(missing), file=sys.stderr)
        print("Install them with your distribution package manager first; cyber-console does not use sudo or install packages.", file=sys.stderr)
        return 1

    template_path = source / "config.example.json"
    if not template_path.is_file() or not (source / "src/cyber_console/cli.py").is_file():
        print("The cyber-console source files are incomplete.", file=sys.stderr)
        return 1
    template = json.loads(template_path.read_text(encoding="utf-8"))
    config = template
    if config_file.is_file():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
            if not isinstance(config, dict) or not isinstance(config.get("applications"), dict):
                raise ValueError("expected an applications object")
        except (OSError, json.JSONDecodeError, ValueError) as error:
            print(f"Cannot safely preserve existing configuration: {error}", file=sys.stderr)
            return 1

    optional_apps = config.get("applications", {})
    for name, app in optional_apps.items():
        command = app.get("command") if isinstance(app, dict) else None
        if not isinstance(app, dict) or not isinstance(app.get("class"), str) or not app.get("class") or not isinstance(app.get("title", name), str) or not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
            print(f"Invalid configuration for {name!r}; see the README configuration example.", file=sys.stderr)
            return 1
        executable = command[0]
        if shutil.which(executable) is None:
            print(f"Optional tool missing: {name} ({executable}); install it or remove it from the config.", file=sys.stderr)

    config_file.parent.mkdir(parents=True, exist_ok=True)
    if not config_file.exists():
        config_file.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
        config_file.chmod(0o600)

    if app_dir.exists():
        shutil.rmtree(app_dir)
    (app_dir / "src").mkdir(parents=True)
    shutil.copytree(source / "src/cyber_console", app_dir / "src/cyber_console")
    shutil.copy2(template_path, app_dir / "config.example.json")
    command_dir = prefix / "bin"
    command_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "bin/cyber-console", command_dir / "cyber-console")
    (command_dir / "cyber-console").chmod(0o755)

    print(f"Installed cyber-console in {command_dir} and {app_dir}.")
    print(f"Configuration: {config_file}")
    print("Check configured dependencies with: cyber-console --check")
    print("The installer does not edit Hyprland or Waybar configuration; see README for integration steps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
