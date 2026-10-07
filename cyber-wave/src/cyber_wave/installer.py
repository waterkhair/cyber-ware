"""Install cyber-wave without taking ownership of existing user files."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from .config import DEFAULT, THEMES, paths


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m cyber_wave.installer SOURCE_DIR", file=sys.stderr)
        return 2
    source = Path(sys.argv[1]).resolve()
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk  # noqa: F401
    except (ImportError, ValueError):
        print(
            "Missing required dependency: GTK 4 Python bindings. Install gtk4 and python-gobject first.",
            file=sys.stderr,
        )
        return 1
    p = paths()
    app, config, command = p["data"], p["config"].parent, p["command"]
    for path in (p["data"].parent, config.parent, command.parent):
        if path.is_symlink():
            print(f"Refusing symlinked install parent: {path}", file=sys.stderr)
            return 1
    if app.is_symlink() or (app.exists() and not (app / ".cyber-wave-managed").is_file()):
        print(f"Refusing unowned application directory: {app}", file=sys.stderr)
        return 1
    if config.is_symlink() or (config.exists() and not config.is_dir()):
        print(f"Refusing unsafe configuration directory: {config}", file=sys.stderr)
        return 1
    if command.is_symlink() or (command.exists() and "# cyber-wave-managed-command" not in command.read_text(encoding="utf-8", errors="replace")):
        print(f"Refusing unowned command or symlink: {command}", file=sys.stderr)
        return 1
    for target in (app / "src", app / "src/cyber_wave", app / "src/cyber_wave/themes", app / "themes", app / "install.json", config / "config.json", config / "theme"):
        if target.is_symlink():
            print(f"Refusing symlinked destination: {target}", file=sys.stderr)
            return 1
    for target in (app / "src", app / "src/cyber_wave", app / "src/cyber_wave/themes", app / "themes"):
        if target.exists() and not target.is_dir():
            print(f"Refusing non-directory program destination: {target}", file=sys.stderr)
            return 1
    for relative in ("bin/cyber-wave", "config.example.json", "themes/synthwave.css", "themes/greenline.css", "themes/husky.css"):
        if not (source / relative).is_file():
            print(f"Missing source file: {relative}", file=sys.stderr)
            return 1
    if config.joinpath("config.json").is_file():
        try:
            existing = json.loads(config.joinpath("config.json").read_text(encoding="utf-8"))
            if not isinstance(existing, dict) or not isinstance(existing.get("stations"), list):
                raise ValueError("stations must be an array")
        except (OSError, json.JSONDecodeError, ValueError) as error:
            print(f"Cannot preserve station configuration: {error}", file=sys.stderr)
            return 1

    config.mkdir(parents=True, exist_ok=True)
    if not (config / "config.json").exists():
        (config / "config.json").write_text(json.dumps(DEFAULT, indent=2) + "\n", encoding="utf-8")
        (config / "config.json").chmod(0o600)
    theme_path = config / "theme"
    if not theme_path.exists():
        shared = p["shared_theme"]
        try:
            selected = shared.read_text(encoding="utf-8").splitlines()[0].strip()
        except (OSError, IndexError):
            try:
                saved = json.loads((config / "config.json").read_text(encoding="utf-8")).get("theme", "synthwave")
                selected = saved if saved in THEMES else "synthwave"
            except (OSError, json.JSONDecodeError):
                selected = "synthwave"
        if selected not in THEMES:
            selected = "synthwave"
        theme_path.write_text(selected + "\n", encoding="utf-8")
        theme_path.chmod(0o600)

    stage = app.with_name(f".{app.name}.stage-{os.getpid()}")
    if stage.exists() or stage.is_symlink():
        print(f"Refusing to reuse staging path: {stage}", file=sys.stderr)
        return 1
    stage.mkdir(parents=True)
    try:
        shutil.copytree(source / "src/cyber_wave", stage / "src/cyber_wave")
        shutil.copytree(source / "themes", stage / "src/cyber_wave/themes")
        (stage / ".cyber-wave-managed").write_text("managed by cyber-wave installer\n", encoding="utf-8")
        (stage / "install.json").write_text(json.dumps({"command": str(command)}, indent=2) + "\n", encoding="utf-8")
        if app.exists():
            shutil.copytree(stage / "src/cyber_wave", app / "src/cyber_wave", dirs_exist_ok=True)
            shutil.copy2(stage / ".cyber-wave-managed", app / ".cyber-wave-managed")
            shutil.copy2(stage / "install.json", app / "install.json")
        else:
            stage.replace(app)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    command.parent.mkdir(parents=True, exist_ok=True)
    temporary = command.with_name(f".cyber-wave-{os.getpid()}")
    try:
        temporary.write_text((source / "bin/cyber-wave").read_text(encoding="utf-8"), encoding="utf-8")
        temporary.chmod(0o755)
        temporary.replace(command)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Installed cyber-wave command: {command}")
    print(f"Station list: {config / 'config.json'}")
    print("Use Ctrl+Super+R in the cyber-ware Hyprland config, or run cyber-wave.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
