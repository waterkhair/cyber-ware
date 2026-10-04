"""Synchronize cyber-wall's current choice to Hyprlock as a still image."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .config import state_dir

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".gif"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _background_blocks(lines: list[str]) -> list[tuple[int, int]]:
    blocks = []
    index = 0
    while index < len(lines):
        if not re.match(r"^\s*background\s*\{\s*$", lines[index]):
            index += 1
            continue
        depth = lines[index].count("{") - lines[index].count("}")
        end = index + 1
        while end < len(lines) and depth > 0:
            depth += lines[end].count("{") - lines[end].count("}")
            end += 1
        if depth != 0:
            raise RuntimeError("Hyprlock background block is not closed")
        blocks.append((index, end - 1))
        index = end
    return blocks


def _set_background_path(config: str, wallpaper: Path) -> str:
    lines = config.splitlines()
    blocks = _background_blocks(lines)
    path_line = f"    path = {wallpaper}"
    if not blocks:
        return "background {\n" + path_line + "\n}\n" + config
    for start, end in reversed(blocks):
        found = next((i for i in range(start + 1, end)
                      if re.match(r"^\s*path\s*=", lines[i])), None)
        if found is None:
            lines.insert(start + 1, path_line)
        else:
            indent = re.match(r"^\s*", lines[found]).group(0)
            lines[found] = f"{indent}path = {wallpaper}"
    return "\n".join(lines) + ("\n" if config.endswith("\n") or not config else "")


def _render_lock_image(source: Path, destination: Path) -> None:
    suffix = source.suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("syncing a video wallpaper needs ffmpeg to make a lock-screen still")
        fd, name = tempfile.mkstemp(prefix=".lock-wallpaper.", suffix=".jpg", dir=destination.parent)
        os.close(fd)
        temporary = Path(name)
        try:
            temporary.unlink()
            subprocess.run(
                [ffmpeg, "-nostdin", "-loglevel", "error", "-y", "-ss", "0.5", "-i",
                 str(source), "-frames:v", "1", "-q:v", "2", str(temporary)],
                check=True, capture_output=True, timeout=20,
            )
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise RuntimeError("ffmpeg did not produce a lock-screen image")
            temporary.chmod(0o600)
            os.replace(temporary, destination)
        except (OSError, subprocess.SubprocessError) as error:
            raise RuntimeError(f"could not create a still image from {source}: {error}") from error
        finally:
            temporary.unlink(missing_ok=True)
    elif suffix in IMAGE_EXTENSIONS:
        fd, name = tempfile.mkstemp(prefix=".lock-wallpaper.", suffix=suffix, dir=destination.parent)
        os.close(fd)
        temporary = Path(name)
        try:
            shutil.copyfile(source, temporary)
            temporary.chmod(0o600)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    else:
        raise RuntimeError(f"unsupported lock-screen wallpaper format: {suffix or '(no extension)'}")


def sync_lock_wallpaper(config_path: Path | None = None) -> Path:
    state = state_dir()
    source_path = state / "current"
    config_path = config_path or Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "hypr/hyprlock.conf"
    sync_dir = state / "lock-sync"
    metadata_path = sync_dir / "metadata.json"
    original_path = sync_dir / "original-hyprlock.conf"

    if not source_path.is_file():
        raise RuntimeError("no saved cyber-wall selection exists yet; set a wallpaper first")
    source = Path(source_path.read_text(encoding="utf-8").strip()).expanduser().resolve(strict=True)
    if config_path.is_symlink() or not config_path.is_file():
        raise RuntimeError(f"Hyprlock config is missing or unsafe: {config_path}")
    original = config_path.read_bytes()
    try:
        text = original.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RuntimeError(f"Hyprlock config is not UTF-8: {config_path}") from error

    sync_dir.mkdir(parents=True, exist_ok=True)
    if sync_dir.is_symlink() or metadata_path.is_symlink() or original_path.is_symlink():
        raise RuntimeError(f"Refusing symlinked lock-sync state: {sync_dir}")
    metadata: dict[str, object] = {}
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Cannot read lock-sync metadata: {error}") from error
        previous_hash = metadata.get("managed_config_sha256")
        if previous_hash and hashlib.sha256(original).hexdigest() != previous_hash:
            metadata["user_modified"] = True
    else:
        _atomic_write(original_path, original, config_path.stat().st_mode & 0o777)

    suffix = ".jpg" if source.suffix.lower() in VIDEO_EXTENSIONS else source.suffix.lower()
    wallpaper = sync_dir / f"wallpaper{suffix}"
    if wallpaper.is_symlink():
        raise RuntimeError(f"Refusing symlinked lock-screen image destination: {wallpaper}")
    _render_lock_image(source, wallpaper)
    updated = _set_background_path(text, wallpaper)
    updated_bytes = updated.encode("utf-8")
    _atomic_write(config_path, updated_bytes, config_path.stat().st_mode & 0o777)
    metadata.update({
        "config_path": str(config_path.resolve()),
        "managed_config_sha256": hashlib.sha256(updated_bytes).hexdigest(),
        "wallpaper_path": str(wallpaper),
    })
    _atomic_write(metadata_path, (json.dumps(metadata, indent=2) + "\n").encode())
    return wallpaper


def validate_purge() -> tuple[Path, bytes] | None:
    """Return the original Hyprlock config if safe to restore before purge."""
    metadata_path = state_dir() / "lock-sync/metadata.json"
    if not metadata_path.exists():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        config_path = Path(metadata["config_path"])
        original_path = metadata_path.parent / "original-hyprlock.conf"
        expected = metadata["managed_config_sha256"]
        current = config_path.read_bytes()
        original = original_path.read_bytes()
    except (KeyError, OSError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot safely purge lock-screen sync data: {error}") from error
    if metadata.get("user_modified") or hashlib.sha256(current).hexdigest() != expected:
        raise RuntimeError(
            f"Hyprlock config has changes since wallpaper sync; update or restore {config_path} before --purge"
        )
    return config_path, original
