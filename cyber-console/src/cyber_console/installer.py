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
    command_dir = prefix / "bin"
    command_path = command_dir / "cyber-console"

    if command_dir.is_symlink() or data_home.is_symlink():
        print("Refusing a symlinked command or data directory.", file=sys.stderr)
        return 1
    if app_dir.is_symlink() or (app_dir.exists() and not (app_dir / ".cyber-console-managed").is_file()):
        print(f"Refusing to replace unowned or symlinked application directory: {app_dir}", file=sys.stderr)
        return 1
    if any(path.is_symlink() for path in (app_dir / ".cyber-console-managed", app_dir / "src", app_dir / "src/cyber_console", app_dir / "config.example.json", app_dir / "themes")):
        print(f"Refusing symlinked cyber-console program files: {app_dir}", file=sys.stderr)
        return 1
    if (app_dir / "themes").is_dir() and any(path.is_symlink() for path in (app_dir / "themes").rglob("*")):
        print(f"Refusing symlinks inside cyber-console themes: {app_dir / 'themes'}", file=sys.stderr)
        return 1
    if command_path.is_symlink() or (command_path.exists() and
            (not command_path.is_file() or "# cyber-console-managed-command" not in command_path.read_text(encoding="utf-8", errors="replace"))):
        print(f"Refusing to replace an unowned command or symlink: {command_path}", file=sys.stderr)
        return 1
    theme_file = config_file.parent / "theme"
    if config_file.parent.is_symlink() or config_file.is_symlink() or (config_file.exists() and not config_file.is_file()) or theme_file.is_symlink() or (theme_file.exists() and not theme_file.is_file()):
        print(f"Refusing unsafe configuration destination: {config_file}", file=sys.stderr)
        return 1

    required = ("python3", "ghostty", "hyprctl")
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        print("Missing required dependencies: " + ", ".join(missing), file=sys.stderr)
        print("Install them with your distribution package manager first; cyber-console does not use sudo or install packages.", file=sys.stderr)
        return 1

    template_path = source / "config.example.json"
    if not template_path.is_file() or not (source / "src/cyber_console/cli.py").is_file() or not (source / "themes").is_dir():
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
    if not theme_file.exists():
        shared_theme = config_file.parent.parent / "cyber-ware/theme"
        try:
            selected = shared_theme.read_text(encoding="utf-8").splitlines()[0].strip()
        except (OSError, IndexError):
            selected = "synthwave"
        if selected not in ("synthwave", "greenline", "husky"):
            selected = "synthwave"
        theme_file.write_text(selected + "\n", encoding="utf-8")
        theme_file.chmod(0o600)

    stage = app_dir.with_name(f".{app_dir.name}.stage-{os.getpid()}")
    if stage.exists() or stage.is_symlink():
        print(f"Refusing to reuse an existing staging path: {stage}", file=sys.stderr)
        return 1
    try:
        (stage / "src").mkdir(parents=True)
        shutil.copytree(source / "src/cyber_console", stage / "src/cyber_console")
        shutil.copy2(template_path, stage / "config.example.json")
        shutil.copytree(source / "themes", stage / "themes")
        (stage / ".cyber-console-managed").write_text("managed by cyber-console installer\n", encoding="utf-8")
        if app_dir.exists():
            app_src = app_dir / "src"
            app_src.mkdir(parents=True, exist_ok=True)
            target = app_src / "cyber_console"
            previous = stage / "previous-cyber_console"
            if target.exists():
                target.replace(previous)
            try:
                (stage / "src/cyber_console").replace(target)
            except OSError:
                if previous.exists():
                    previous.replace(target)
                raise
            if not (app_dir / "config.example.json").exists():
                (stage / "config.example.json").replace(app_dir / "config.example.json")
            shutil.copytree(stage / "themes", app_dir / "themes", dirs_exist_ok=True)
            if not (app_dir / ".cyber-console-managed").exists():
                (stage / ".cyber-console-managed").replace(app_dir / ".cyber-console-managed")
            if previous.exists():
                shutil.rmtree(previous)
        else:
            stage.replace(app_dir)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    command_dir.mkdir(parents=True, exist_ok=True)
    command_tmp = command_dir / f".cyber-console-{os.getpid()}"
    try:
        command_tmp.write_text((source / "bin/cyber-console").read_text(encoding="utf-8"), encoding="utf-8")
        command_tmp.chmod(0o755)
        command_tmp.replace(command_path)
    finally:
        command_tmp.unlink(missing_ok=True)

    print(f"Installed cyber-console in {command_dir} and {app_dir}.")
    print(f"Configuration: {config_file}")
    print("Check configured dependencies with: cyber-console --check")
    print("The installer does not edit Hyprland or Waybar configuration; see README for integration steps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
