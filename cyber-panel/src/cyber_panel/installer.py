"""User-local installer for cyber-panel; no root access or package writes."""

from __future__ import annotations

import json
import os
import shutil
import sys
import hashlib
import shlex
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
    command_dir = prefix / "bin"
    command_path = command_dir / "cyber-panel"

    for directory in (waybar_dir, state_dir, command_dir):
        if directory.is_symlink():
            print(f"Refusing symlinked destination directory: {directory}", file=sys.stderr)
            return 1
    if (config_home / "cyber-panel").is_symlink():
        print(f"Refusing symlinked settings directory: {config_home / 'cyber-panel'}", file=sys.stderr)
        return 1
    for target in (state_file, config_home / "cyber-panel/config.json"):
        if target.is_symlink() or (target.exists() and not target.is_file()):
            print(f"Refusing unsafe state/config destination: {target}", file=sys.stderr)
            return 1
    if app_dir.is_symlink() or (app_dir.exists() and not (app_dir / ".cyber-panel-managed").is_file()):
        print(f"Refusing to replace unowned or symlinked application directory: {app_dir}", file=sys.stderr)
        return 1
    if any(path.is_symlink() for path in (app_dir / ".cyber-panel-managed", app_dir / "src", app_dir / "src/cyber_panel", app_dir / "themes", app_dir / "config.jsonc")):
        print(f"Refusing symlinked cyber-panel program files: {app_dir}", file=sys.stderr)
        return 1
    if command_path.is_symlink() or (command_path.exists() and
            (not command_path.is_file() or "# cyber-panel-managed-command" not in command_path.read_text(encoding="utf-8", errors="replace"))):
        print(f"Refusing to replace an unowned command or symlink: {command_path}", file=sys.stderr)
        return 1

    missing = [name for name in ("waybar", "hyprctl", "python3") if shutil.which(name) is None]
    if missing:
        print("Missing required dependencies: " + ", ".join(missing), file=sys.stderr)
        print("Install them with your distribution package manager; cyber-panel does not install system packages.", file=sys.stderr)
        return 1

    for name, package in (("playerctl", "playerctl"), ("cyber-console", "the optional floating-tool component")):
        if shutil.which(name) is None:
            print(f"Optional command missing: {name} ({package}); its click action will not work until configured.", file=sys.stderr)

    if not (source / "config.jsonc").is_file() or not all((source / "themes" / f"{name}.css").is_file() for name in ("synthwave", "greenline", "husky")):
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
        if shared_theme in ("synthwave", "greenline", "husky"):
            theme = shared_theme
            settings["theme"] = theme
        elif shared_theme:
            print(f"Ignoring invalid shared cyber-ware theme in {shared_theme_file}.", file=sys.stderr)
    if theme not in ("synthwave", "greenline", "husky"):
        print(f"Unknown saved theme {theme!r}; using synthwave.", file=sys.stderr)
        theme = "synthwave"
        settings["theme"] = theme

    # Keep the pre-install copies across upgrades; they are what uninstall restores.
    for name in ("config.jsonc", "style.css"):
        target = waybar_dir / name
        backup = backup_dir / name
        if target.is_symlink() or (target.exists() and not target.is_file()):
            print(f"Refusing unsafe Waybar destination: {target}", file=sys.stderr)
            return 1
        if name not in state["originals"]:
            state["originals"][name] = target.is_file()
            if target.is_file():
                shutil.copy2(target, backup)
        elif target.is_file() and name in state.get("installed_hashes", {}):
            current_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            if current_hash != state["installed_hashes"][name]:
                before_update = state_dir / "before-update" / name
                before_update.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, before_update)
                print(f"Preserved edited Waybar file at {before_update} before updating it.")

    stage = app_dir.with_name(f".{app_dir.name}.stage-{os.getpid()}")
    if stage.exists() or stage.is_symlink():
        print(f"Refusing existing staging path: {stage}", file=sys.stderr)
        return 1
    try:
        (stage / "src").mkdir(parents=True)
        shutil.copytree(source / "src/cyber_panel", stage / "src/cyber_panel")
        shutil.copytree(source / "themes", stage / "themes")
        shutil.copy2(source / "config.jsonc", stage / "config.jsonc")
        (stage / ".cyber-panel-managed").write_text("managed by cyber-panel installer\n", encoding="utf-8")
        if app_dir.exists():
            for relative in (Path("src/cyber_panel"), Path("themes"), Path("config.jsonc")):
                target = app_dir / relative
                staged = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                old = stage / ("previous-" + relative.name)
                if target.exists():
                    target.replace(old)
                try:
                    staged.replace(target)
                except OSError:
                    if old.exists():
                        old.replace(target)
                    raise
                if old.is_dir():
                    shutil.rmtree(old)
                elif old.exists():
                    old.unlink()
            if not (app_dir / ".cyber-panel-managed").exists():
                (stage / ".cyber-panel-managed").replace(app_dir / ".cyber-panel-managed")
        else:
            stage.replace(app_dir)
    finally:
        if stage.exists():
            shutil.rmtree(stage)

    config_text = (source / "config.jsonc").read_text(encoding="utf-8")
    console = shlex.quote(str(prefix / "bin/cyber-console"))
    config_text = config_text.replace('"cyber-console wiremix"', json.dumps(f"{console} wiremix"))
    config_text = config_text.replace('"cyber-console impala"', json.dumps(f"{console} impala"))
    config_bytes = config_text.encode("utf-8")
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

    command_dir.mkdir(parents=True, exist_ok=True)
    command_tmp = command_dir / f".cyber-panel-{os.getpid()}"
    try:
        command_tmp.write_text((source / "bin/cyber-panel").read_text(encoding="utf-8"), encoding="utf-8")
        command_tmp.chmod(0o755)
        command_tmp.replace(command_path)
    finally:
        command_tmp.unlink(missing_ok=True)
    print(f"Installed cyber-panel command in {command_dir}.")
    print(f"Waybar configuration: {config_target}")
    print(f"Theme: {theme} (switch with cyber-panel --theme greenline|synthwave|husky)")
    print(f"Original Waybar files are preserved in {backup_dir}; uninstall with cyber-panel --uninstall.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
