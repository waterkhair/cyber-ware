"""Stage, validate, and publish a user-local cyber-deck installation."""

from __future__ import annotations

from contextlib import ExitStack
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile

from .config import THEMES, config_dir, data_dir


def install(source: Path) -> None:
    app = data_dir().absolute()
    config = config_dir().absolute()
    command = (Path(os.environ.get("PREFIX", Path.home() / ".local")) / "bin/cyber-deck").absolute()
    targets = (app, config, command)
    for target in targets:
        if target.is_symlink():
            raise RuntimeError(f"Refusing a symlinked destination: {target}")
    if app.exists() and not (app / ".cyber-deck-managed").is_file():
        raise RuntimeError(f"Refusing an unowned application directory: {app}")
    if command.exists() and (not command.is_file() or
                             "# cyber-deck-managed-command" not in command.read_text()):
        raise RuntimeError(f"Refusing an unowned command: {command}")
    # Do not traverse user-controlled symlinks while copying or validating themes.
    if config.exists():
        if not config.is_dir():
            raise RuntimeError(f"Not a configuration directory: {config}")
        if any(path.is_symlink() for path in config.rglob("*")):
            raise RuntimeError(f"Refusing symlinks inside configuration directory: {config}")

    with ExitStack() as stack:
        preserve_stages = False

        def cleanup_stage(path):
            if not preserve_stages:
                shutil.rmtree(path)

        stages = []
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix=".cyber-deck-stage-", dir=target.parent))
            stack.callback(cleanup_stage, stage)
            stages.append(stage)
        new_app, new_config, new_command = (stage / "new" for stage in stages)
        shutil.copytree(source / "src", new_app / "src")
        for module in (new_app / "src/cyber_deck").glob("*.py"):
            compile(module.read_text(), str(module), "exec")
        (new_app / ".cyber-deck-managed").touch()
        (new_app / "install.json").write_text(json.dumps({"command": str(command)}) + "\n")
        if config.exists():
            shutil.copytree(config, new_config)
        else:
            new_config.mkdir()
        (new_config / "themes").mkdir(exist_ok=True)
        for theme in THEMES:
            destination = new_config / "themes" / f"{theme}.ini"
            if not destination.exists():
                shutil.copy2(source / "themes" / f"{theme}.ini", destination)
            subprocess.run(["fuzzel", "--config", str(destination), "--check-config"], check=True)

        selection = new_config / "theme"
        if selection.exists():
            theme = selection.read_text().strip()
            if theme not in THEMES:
                raise RuntimeError(f"Invalid existing theme selection: {selection}")
        else:
            shared = config.parent / "cyber-ware/theme"
            theme = shared.read_text().strip() if shared.is_file() else "synthwave"
            if theme not in THEMES:
                theme = "synthwave"
            selection.write_text(theme + "\n")
            selection.chmod(0o600)

        launcher = (source / "bin/cyber-deck").read_text()
        launcher = launcher.replace(
            'app_home=${CYBER_DECK_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/cyber-deck}',
            'app_home=${CYBER_DECK_HOME:-}\n[ -n "$app_home" ] || app_home=' + shlex.quote(str(app)))
        new_command.write_text(launcher)
        new_command.chmod(0o755)
        published = []
        try:
            for target, stage in zip(targets, stages):
                old = stage / "old"
                existed = target.exists()
                if existed:
                    os.replace(target, old)
                published.append((target, old, existed))
                os.replace(stage / "new", target)
        except BaseException:
            try:
                for target, old, existed in reversed(published):
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink(missing_ok=True)
                    if existed:
                        os.replace(old, target)
            except BaseException as error:
                preserve_stages = True
                raise RuntimeError(f"Rollback failed; originals retained in {stages}: {error}") from error
            raise
    print(f"Installed cyber-deck in {app}")
    print(f"Command: {command}")
    print(f"Fuzzel themes: {config / 'themes'}")
    print("Start with: cyber-deck; set the theme with cyber-deck --theme greenline|synthwave.")
    print("Super+Space requires a Hyprland binding to this command; reload Hyprland after updating it.")


if __name__ == "__main__":
    def interrupted(signum, _frame):
        raise SystemExit(128 + signum)

    for sig in (signal.SIGHUP, signal.SIGTERM):
        signal.signal(sig, interrupted)
    try:
        install(Path(sys.argv[1]))
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"cyber-deck: installation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
