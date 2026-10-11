#!/usr/bin/env python3
"""Install upstream Monochrome SDDM files and select the theme by default."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import sys
import tempfile


SYSTEM_THEMES = Path("/usr/share/sddm/themes")
SDDM_CONFIG = Path("/etc/sddm.conf")
MANAGED_MARKER = "# cyber-ware-managed-sddm-theme"
WALLPAPER_MARKER = "# cyber-ware-managed-sddm-wallpaper"


def set_theme(contents: str) -> str:
    """Set [Theme] Current while preserving unrelated SDDM configuration."""
    lines = contents.splitlines(keepends=True)
    output: list[str] = []
    in_theme = False
    found_theme = False
    wrote_current = False

    for line in lines:
        stripped = line.strip()
        section = re.fullmatch(r"\[([^]]+)\]", stripped)
        if section:
            if in_theme and not wrote_current:
                output.extend((MANAGED_MARKER + "\n", "Current=monochrome\n"))
                wrote_current = True
            in_theme = section.group(1).strip().casefold() == "theme"
            found_theme = found_theme or in_theme
            output.append(line)
            continue

        current = re.match(r"^(\s*)Current\s*=\s*(.*?)\s*$", line, re.IGNORECASE)
        if in_theme and current:
            if not wrote_current:
                indent, value = current.groups()
                if value.casefold() == "monochrome":
                    output.append(line)
                else:
                    output.extend((indent + MANAGED_MARKER + "\n",
                                   indent + "Current=monochrome\n"))
                wrote_current = True
            continue
        output.append(line)

    if in_theme and not wrote_current:
        output.extend((MANAGED_MARKER + "\n", "Current=monochrome\n"))
        wrote_current = True
    if not found_theme:
        if output and not output[-1].endswith("\n"):
            output[-1] += "\n"
        if output and output[-1].strip():
            output.append("\n")
        output.extend(("[Theme]\n", MANAGED_MARKER + "\n", "Current=monochrome\n"))
    return "".join(output)


def install_theme(source: Path, target: Path) -> bool:
    if not source.is_dir() or source.is_symlink():
        raise RuntimeError(f"Theme source is missing or unsafe: {source}")
    if target.is_symlink():
        raise RuntimeError(f"Refusing symlinked SDDM theme destination: {target}")
    if target.exists():
        metadata = target / "metadata.desktop"
        if not metadata.is_file() or "Theme-Id=monochrome" not in metadata.read_text(encoding="utf-8"):
            raise RuntimeError(f"Existing theme directory is not the upstream Monochrome theme: {target}")
        print(f"Preserving existing theme directory: {target}")
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        if item.is_symlink():
            raise RuntimeError(f"Refusing symlink in downloaded theme: {item}")
    staging = Path(tempfile.mkdtemp(prefix=".cyber-ware-monochrome-", dir=target.parent))
    staged_theme = staging / "monochrome"
    try:
        shutil.copytree(source, staged_theme)
        try:
            os.rename(staged_theme, target)
        except OSError:
            if target.is_dir() and not target.is_symlink():
                print(f"Preserving theme directory created concurrently: {target}")
                return False
            raise
        return True
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def set_custom_background(contents: str) -> str:
    """Enable the theme's custom image and point it to wallpaper.png."""
    lines = contents.splitlines(keepends=True)
    output: list[str] = []
    in_general = False
    found_general = False
    written: set[str] = set()
    marker_present = WALLPAPER_MARKER in contents
    desired = {"custombackground": 'CustomBackground="true"\n',
               "background": 'Background="wallpaper.png"\n'}

    for line in lines:
        section = re.fullmatch(r"\s*\[([^]]+)\]\s*", line)
        if section:
            if in_general:
                for key, value in desired.items():
                    if key not in written:
                        output.append(value)
            in_general = section.group(1).strip().casefold() == "general"
            found_general = found_general or in_general
            output.append(line)
            if in_general:
                written = set()
                if not marker_present:
                    output.append(WALLPAPER_MARKER + "\n")
                    marker_present = True
            continue

        key_match = re.match(r"^\s*([A-Za-z][A-Za-z0-9]*)\s*=", line)
        key = key_match.group(1).casefold() if key_match else ""
        if in_general and key in desired:
            if key not in written:
                indent = re.match(r"^\s*", line).group(0)
                output.append(indent + desired[key])
                written.add(key)
            continue
        output.append(line)

    if in_general:
        for key, value in desired.items():
            if key not in written:
                output.append(value)
    if not found_general:
        if output and not output[-1].endswith("\n"):
            output[-1] += "\n"
        if output and output[-1].strip():
            output.append("\n")
        output.extend(("[General]\n", WALLPAPER_MARKER + "\n", *desired.values()))
    return "".join(output)


def write_managed_file(
    path: Path, updated: str, backup_suffix: str, managed_marker: str = MANAGED_MARKER
) -> bool:
    if path.is_symlink():
        raise RuntimeError(f"Refusing symlinked SDDM file: {path}")
    if path.exists() and not path.is_file():
        raise RuntimeError(f"Refusing non-file SDDM path: {path}")
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    if updated == original:
        return False
    backup = path.with_name(path.name + backup_suffix)
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
        print(f"Original {path.name} backed up to {backup}")
    elif path.exists() and backup.exists() and managed_marker not in original:
        raise RuntimeError(f"Refusing to change {path}; backup path already exists: {backup}")

    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.cyber-ware.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return True


def configure_wallpaper(theme: Path, wallpaper: Path | None) -> bool:
    if wallpaper is None:
        print("No local wallpaper was supplied; keeping the upstream theme background defaults.")
        return False
    if wallpaper.is_symlink() or not wallpaper.is_file():
        raise RuntimeError(f"Wallpaper must be a regular, non-symlink file: {wallpaper}")

    target = theme / "wallpaper.png"
    if target.is_symlink():
        raise RuntimeError(f"Refusing symlinked theme wallpaper: {target}")
    if not (target.is_file() and target.read_bytes() == wallpaper.read_bytes()):
        backup = target.with_name(target.name + ".cyber-ware-backup")
        if target.exists() and not backup.exists():
            shutil.copy2(target, backup)
        elif target.exists() and backup.exists() and target.read_bytes() != wallpaper.read_bytes():
            raise RuntimeError(f"Refusing to overwrite a different wallpaper because backup already exists: {backup}")
        shutil.copy2(wallpaper, target)

    config = theme / "theme.conf"
    if config.is_symlink() or not config.is_file():
        raise RuntimeError(f"Theme configuration is missing or unsafe: {config}")
    updated = set_custom_background(config.read_text(encoding="utf-8"))
    if write_managed_file(config, updated, ".cyber-ware-backup", WALLPAPER_MARKER):
        print("Enabled Monochrome's custom wallpaper and selected wallpaper.png.")
    return True


def configure_default(config: Path) -> bool:
    if config.is_symlink():
        raise RuntimeError(f"Refusing symlinked SDDM configuration: {config}")
    if config.exists() and not config.is_file():
        raise RuntimeError(f"Refusing non-file SDDM configuration: {config}")

    original = config.read_text(encoding="utf-8") if config.exists() else ""
    updated = set_theme(original)
    if updated == original:
        print("Monochrome is already the configured SDDM theme.")
        return False
    write_managed_file(config, updated, ".cyber-ware-backup")
    print("Configured Monochrome as the default SDDM theme; display-server settings were left unchanged.")
    return True


def main() -> int:
    if os.geteuid() != 0:
        print("Run this helper through sudo; it installs system SDDM files.")
        return 1
    if len(sys.argv) != 3:
        print("Usage: install.py THEME_SOURCE WALLPAPER_SOURCE_OR_EMPTY")
        return 2
    theme_source = Path(sys.argv[1])
    wallpaper_source = Path(sys.argv[2]) if sys.argv[2] else None
    try:
        copied = install_theme(theme_source, SYSTEM_THEMES / "monochrome")
        theme = SYSTEM_THEMES / "monochrome"
        wallpaper_configured = configure_wallpaper(theme, wallpaper_source)
        configured = configure_default(SDDM_CONFIG)
    except (OSError, RuntimeError) as error:
        print(f"SDDM setup failed: {error}")
        return 1
    if copied:
        print(f"Installed Monochrome theme in {SYSTEM_THEMES / 'monochrome'}")
    if wallpaper_configured:
        print(f"Custom background file: {SYSTEM_THEMES / 'monochrome' / 'wallpaper.png'}")
    if not copied and not configured:
        print("SDDM is already set up for cyber-ware's Monochrome theme.")
    print("SDDM was not enabled or restarted. The theme will be used when SDDM next starts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
