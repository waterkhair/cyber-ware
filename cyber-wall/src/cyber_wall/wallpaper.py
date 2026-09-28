"""Apply and restore a wallpaper through mpvpaper's IPC socket."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .config import expand_path, load_config, runtime_dir, state_dir


def _read_json_line(connection: socket.socket, request_id: int) -> dict[str, Any] | None:
    reader = connection.makefile("r", encoding="utf-8")
    while True:
        line = reader.readline()
        if not line:
            return None
        try:
            response = json.loads(line)
        except json.JSONDecodeError:
            continue
        if response.get("request_id") == request_id:
            return response


def _socket_command(path: Path, command: list[str | int], request_id: int) -> dict[str, Any] | None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(1.5)
            connection.connect(str(path))
            payload = {"command": command, "request_id": request_id}
            connection.sendall((json.dumps(payload) + "\n").encode())
            return _read_json_line(connection, request_id)
    except (OSError, TimeoutError):
        return None


def _resolve_output(config: dict[str, Any]) -> str:
    selected = os.environ.get("WALLPAPER_OUTPUT", str(config.get("output", "auto"))).strip()
    if selected.lower() != "auto":
        if not selected:
            raise RuntimeError("config 'output' cannot be empty")
        return selected

    try:
        result = subprocess.run(
            ["hyprctl", "monitors", "-j"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
        monitors = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        raise RuntimeError("could not detect a Hyprland monitor; set 'output' in config") from error

    if not isinstance(monitors, list) or not monitors:
        raise RuntimeError("Hyprland reported no active monitors")
    focused = next((item for item in monitors if item.get("focused")), monitors[0])
    name = focused.get("name")
    if not isinstance(name, str) or not name:
        raise RuntimeError("could not determine the focused monitor name")
    return name


def _managed_pid(pid_file: Path, socket_file: Path) -> int | None:
    try:
        pid = int(pid_file.read_text(encoding="ascii").strip())
        command = Path(f"/proc/{pid}/cmdline").read_bytes()
    except (OSError, ValueError):
        return None
    if str(socket_file).encode() not in command:
        return None
    return pid


def _stop_managed(pid_file: Path, socket_file: Path) -> None:
    pid = _managed_pid(pid_file, socket_file)
    if pid is not None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
    pid_file.unlink(missing_ok=True)
    # Only remove a stale socket after the managed process is stopped; a live
    # socket not owned by our PID file is left alone.
    if pid is not None or _socket_command(socket_file, ["get_property", "path"], 99) is None:
        socket_file.unlink(missing_ok=True)


def _rotate_log(log_file: Path) -> None:
    try:
        if log_file.stat().st_size > 1024 * 1024:
            old = log_file.with_name("mpvpaper.previous.log")
            old.unlink(missing_ok=True)
            os.replace(log_file, old)
    except OSError:
        pass


def apply_wallpaper(wallpaper: Path, config: dict[str, Any]) -> None:
    wallpaper = wallpaper.expanduser().resolve(strict=True)
    if not wallpaper.is_file():
        raise RuntimeError(f"not a file: {wallpaper}")
    output = _resolve_output(config)
    state = state_dir()
    runtime = runtime_dir()
    state.mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    socket_file = runtime / "mpvpaper.sock"
    pid_file = state / "mpvpaper.pid"
    state_file = state / "current"
    log_file = state / "mpvpaper.log"

    if socket_file.is_socket():
        result = _socket_command(socket_file, ["loadfile", str(wallpaper), "replace"], 1)
        if result and result.get("error") == "success":
            temporary_state = state / f"current.tmp.{os.getpid()}"
            temporary_state.write_text(f"{wallpaper}\n", encoding="utf-8")
            os.replace(temporary_state, state_file)
            return

    _stop_managed(pid_file, socket_file)
    _rotate_log(log_file)
    mpvpaper = shutil.which("mpvpaper")
    if mpvpaper is None:
        raise RuntimeError("mpvpaper is not installed or not in PATH")
    options = list(config["mpvpaper_options"])
    options.append(f"--input-ipc-server={socket_file}")
    option_string = " ".join(shlex.quote(option) for option in options)
    with log_file.open("ab") as output_log:
        process = subprocess.Popen(
            [mpvpaper, "-l", "background", "-o", option_string, output, str(wallpaper)],
            stdin=subprocess.DEVNULL,
            stdout=output_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    pid_file.write_text(f"{process.pid}\n", encoding="ascii")

    deadline = time.monotonic() + 4
    loaded = False
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        result = _socket_command(socket_file, ["get_property", "path"], 2)
        if result and result.get("error") == "success":
            current = result.get("data")
            if isinstance(current, str) and Path(current).resolve() == wallpaper:
                loaded = True
                break
        time.sleep(0.1)

    if not loaded:
        _stop_managed(pid_file, socket_file)
        raise RuntimeError(f"mpvpaper did not confirm loading {wallpaper}")

    temporary_state = state / f"current.tmp.{os.getpid()}"
    temporary_state.write_text(f"{wallpaper}\n", encoding="utf-8")
    os.replace(temporary_state, state_file)


def stop_wallpaper() -> None:
    """Stop only the mpvpaper process recorded and verified as cyber-wall-owned."""
    state = state_dir()
    runtime = runtime_dir()
    pid_file = state / "mpvpaper.pid"
    socket_file = runtime / "mpvpaper.sock"
    pid = _managed_pid(pid_file, socket_file)
    if pid is None:
        pid_file.unlink(missing_ok=True)
        if _socket_command(socket_file, ["get_property", "path"], 99) is None:
            socket_file.unlink(missing_ok=True)
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        pid_file.unlink(missing_ok=True)
        socket_file.unlink(missing_ok=True)
        return
    raise RuntimeError(f"managed mpvpaper process {pid} did not stop; leaving its state files intact")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Set or restore an mpvpaper wallpaper")
    parser.add_argument("wallpaper", nargs="?", help="image or video file to apply")
    parser.add_argument("--restore", action="store_true", help="restore the previous choice")
    args = parser.parse_args(argv)

    try:
        config = load_config()
        target: str | None = args.wallpaper
        if args.restore:
            saved = state_dir() / "current"
            target = saved.read_text(encoding="utf-8").strip() if saved.is_file() else None
            if not target and config.get("default_wallpaper"):
                target = str(config["default_wallpaper"])
            if not target:
                return 0
        if not target:
            parser.error("provide a wallpaper path or use --restore")
        apply_wallpaper(expand_path(target), config)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"cyber-wall: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
