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


def _wallpaper_include(wallpaper: Path) -> bytes:
    return f"$CYBER_WALLPAPER = {wallpaper}\n".encode("utf-8")


def _enable_wallpaper_include(config: bytes, include_path: Path) -> bytes:
    try:
        text = config.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RuntimeError("old Hyprlock config is not UTF-8; review it before syncing") from error
    lines = text.splitlines()
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
            raise RuntimeError("old Hyprlock background block is not closed; review it before syncing")
        blocks.append((index, end - 1))
        index = end
    if not blocks:
        raise RuntimeError("old Hyprlock config has no background block; update cyber-jackout before syncing")
    for start, end in reversed(blocks):
        found = next((i for i in range(start + 1, end) if re.match(r"^\s*path\s*=", lines[i])), None)
        if found is None:
            lines.insert(start + 1, "    path = $CYBER_WALLPAPER")
        else:
            indent = re.match(r"^\s*", lines[found]).group(0)
            lines[found] = f"{indent}path = $CYBER_WALLPAPER"
    include_line = next((i for i, line in enumerate(lines) if re.match(r"^\s*source\s*=.*hyprlock-wallpaper\.conf\s*$", line)), None)
    if include_line is None:
        lines.insert(0, f"source = {include_path}")
    else:
        lines[include_line] = f"source = {include_path}"
    return ("\n".join(lines) + "\n").encode("utf-8")


def _publish(updates: dict[Path, bytes]) -> None:
    """Publish prepared files, restoring all completed writes on failure."""
    previous = {}
    for path in updates:
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise RuntimeError(f"Refusing unsafe lock-sync destination: {path}")
        previous[path] = (path.read_bytes(), path.stat().st_mode & 0o777) if path.exists() else (None, 0o600)
    written = []
    try:
        for path, data in updates.items():
            _atomic_write(path, data, previous[path][1])
            written.append(path)
    except Exception:
        for path in reversed(written):
            data, mode = previous[path]
            if data is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, data, mode)
        raise


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
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    config_path = config_path or config_home / "hypr/hyprlock.conf"
    include_path = config_home / "hypr/hyprlock-wallpaper.conf"
    sync_dir = state / "lock-sync"
    metadata_path = sync_dir / "metadata.json"
    original_path = sync_dir / "original-wallpaper-include.conf"
    migration: dict[Path, bytes] = {}
    backups: dict[Path, bytes] = {}
    for path in (include_path, sync_dir):
        if any(char in str(path) for char in ('\n', '\r', '#', '$')):
            raise RuntimeError(f"Path contains unsupported Hyprlock syntax: {path}")
    if include_path.is_symlink() or (include_path.exists() and not include_path.is_file()):
        raise RuntimeError(f"Refusing unsafe Hyprlock wallpaper include: {include_path}")

    if not source_path.is_file():
        raise RuntimeError("no saved cyber-wall selection exists yet; set a wallpaper first")
    source = Path(source_path.read_text(encoding="utf-8").strip()).expanduser().resolve(strict=True)
    if config_path.is_symlink() or not config_path.is_file():
        raise RuntimeError(f"Hyprlock config is missing or unsafe: {config_path}")
    sync_dir.mkdir(parents=True, exist_ok=True)
    if sync_dir.is_symlink() or metadata_path.is_symlink() or original_path.is_symlink():
        raise RuntimeError(f"Refusing symlinked lock-sync state: {sync_dir}")
    metadata: dict[str, object] = {}
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Cannot read lock-sync metadata: {error}") from error
        # Migrate old releases that patched hyprlock.conf directly. Restore
        # that file only when it still exactly matches our last managed copy.
        if metadata.get("config_path") and not metadata.get("include_path"):
            legacy_config = Path(str(metadata["config_path"]))
            if legacy_config != config_path or legacy_config.is_symlink():
                raise RuntimeError("legacy wallpaper metadata refers to a different or unsafe Hyprlock config")
            legacy_backup = sync_dir / "original-hyprlock.conf"
            try:
                legacy_current = legacy_config.read_bytes()
                legacy_original = legacy_backup.read_bytes()
            except OSError as error:
                raise RuntimeError(f"cannot safely migrate old lock wallpaper sync: {error}") from error
            if metadata.get("user_modified") or hashlib.sha256(legacy_current).hexdigest() != metadata.get("managed_config_sha256"):
                raise RuntimeError(f"{legacy_config} has changes since the old wallpaper sync; restore or review it before syncing again")
            migrated_config = _enable_wallpaper_include(legacy_original, include_path)
            migration[legacy_config] = migrated_config
            # Keep cyber-jackout's managed-file check valid when the old base
            # config was still untouched before cyber-wall patched it.
            jackout_hash = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "cyber-jackout/hyprlock.sha256"
            if jackout_hash.is_file() and jackout_hash.read_text(encoding="ascii").strip() == hashlib.sha256(legacy_original).hexdigest():
                migration[jackout_hash] = (hashlib.sha256(migrated_config).hexdigest() + "\n").encode("ascii")
            metadata = {}
        previous_hash = metadata.get("include_sha256")
        if previous_hash and include_path.exists() and hashlib.sha256(include_path.read_bytes()).hexdigest() != previous_hash:
            metadata["user_modified"] = True
    else:
        if include_path.is_symlink():
            raise RuntimeError(f"Refusing symlinked Hyprlock wallpaper include: {include_path}")
        existed = include_path.exists()
        backups[original_path] = include_path.read_bytes() if existed else b""
        metadata["include_existed"] = existed

    if "include_existed" not in metadata:
        if include_path.is_symlink():
            raise RuntimeError(f"Refusing symlinked Hyprlock wallpaper include: {include_path}")
        existed = include_path.exists()
        backups[original_path] = include_path.read_bytes() if existed else b""
        metadata["include_existed"] = existed

    suffix = ".jpg" if source.suffix.lower() in VIDEO_EXTENSIONS else source.suffix.lower()
    if not migration:
        text = config_path.read_text(encoding="utf-8")
        sources = re.findall(r"^\s*source\s*=\s*(.*?)\s*$", text, re.MULTILINE)
        if not any(Path(os.path.expandvars(value)).expanduser() == include_path for value in sources) or not re.search(r"^\s*path\s*=\s*\$CYBER_WALLPAPER\s*$", text, re.MULTILINE):
            raise RuntimeError("Hyprlock does not use the wallpaper include; update cyber-jackout and reapply its lock theme, or configure the include manually")
    wallpaper = sync_dir / f"wallpaper{suffix}"
    if wallpaper.is_symlink():
        raise RuntimeError(f"Refusing symlinked lock-screen image destination: {wallpaper}")
    # Rendering must complete before any active configuration or state changes.
    with tempfile.TemporaryDirectory(prefix=".lock-stage-", dir=sync_dir) as stage:
        rendered = Path(stage) / wallpaper.name
        _render_lock_image(source, rendered)
        image_bytes = rendered.read_bytes()
    if include_path.is_symlink():
        raise RuntimeError(f"Refusing symlinked Hyprlock wallpaper include: {include_path}")
    include_bytes = _wallpaper_include(wallpaper)
    metadata.update({
        "include_path": str(include_path.resolve()),
        "include_sha256": hashlib.sha256(include_bytes).hexdigest(),
        "wallpaper_path": str(wallpaper),
    })
    _publish({wallpaper: image_bytes, include_path: include_bytes, **migration,
              **backups, metadata_path: (json.dumps(metadata, indent=2) + "\n").encode()})
    return wallpaper


def validate_purge() -> tuple[Path, bytes | None] | None:
    """Return the prior wallpaper include if safe to restore before purge."""
    metadata_path = state_dir() / "lock-sync/metadata.json"
    if not metadata_path.exists():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("config_path") and not metadata.get("include_path"):
            include_path = Path(metadata["config_path"])
            original_path = metadata_path.parent / "original-hyprlock.conf"
            expected = metadata["managed_config_sha256"]
            current = include_path.read_bytes()
            original = original_path.read_bytes()
            if metadata.get("user_modified") or hashlib.sha256(current).hexdigest() != expected:
                raise RuntimeError(
                    f"Hyprlock config has changes since wallpaper sync; review {include_path} before --purge"
                )
            return include_path, original
        include_path = Path(metadata["include_path"])
        original_path = metadata_path.parent / "original-wallpaper-include.conf"
        expected = metadata["include_sha256"]
        current = include_path.read_bytes()
        original = original_path.read_bytes()
    except (KeyError, OSError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot safely purge lock-screen sync data: {error}") from error
    if metadata.get("user_modified") or hashlib.sha256(current).hexdigest() != expected:
        raise RuntimeError(
            f"Hyprlock wallpaper include has changes since wallpaper sync; review {include_path} before --purge"
        )
    return include_path, original if metadata.get("include_existed") else b"$CYBER_WALLPAPER = /dev/null\n"
