"""Detached mpv playback controlled over a private local IPC socket."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
from pathlib import Path

from .config import paths


def _socket_path() -> Path:
    runtime = paths()["runtime"]
    if runtime.is_symlink():
        raise RuntimeError(f"Refusing symlinked runtime directory: {runtime}")
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    runtime.chmod(0o700)
    result = runtime / "mpv.sock"
    if result.is_symlink():
        raise RuntimeError(f"Refusing symlinked mpv socket: {result}")
    return result


def _mpris_script() -> Path | None:
    """Find mpv-mpris, which some package builds do not auto-load reliably."""
    candidates = (
        Path("/etc/mpv/scripts/mpris.so"),
        Path.home() / ".config/mpv/scripts/mpris.so",
        Path("/usr/lib/mpv-mpris/mpris.so"),
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _request(command: list, wait: float = 0.2):
    path = _socket_path()
    deadline = time.monotonic() + wait
    while True:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(0.4)
                client.connect(str(path))
                client.sendall((json.dumps({"command": command}) + "\n").encode())
                response = client.makefile("rb").readline()
                return json.loads(response) if response else {}
        except (OSError, json.JSONDecodeError):
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.05)


def _start() -> None:
    mpv = shutil.which("mpv")
    if not mpv:
        raise RuntimeError("mpv is missing; install it with your distribution package manager")
    path = _socket_path()
    path.unlink(missing_ok=True)
    args = [mpv, "--no-video", "--force-window=no", "--terminal=no", "--idle=yes",
            f"--input-ipc-server={path}"]
    script = _mpris_script()
    if script:
        args.append(f"--script={script}")
    subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True,
    )
    if _request(["get_property", "idle-active"], wait=3) is None:
        raise RuntimeError("mpv started but its local control socket did not become ready")


def status() -> dict:
    response = _request(["get_property", "path"])
    path = response.get("data") if isinstance(response, dict) and response.get("error") == "success" else None
    paused_response = _request(["get_property", "pause"])
    paused = paused_response.get("data") if isinstance(paused_response, dict) and paused_response.get("error") == "success" else False
    return {"url": path if isinstance(path, str) else None, "paused": bool(paused)}


def play(station: dict) -> None:
    state = status()
    if state["url"] == station["url"]:
        if state["paused"]:
            _request(["set_property", "pause", False])
        return
    if _request(["loadfile", station["url"], "replace"]) is None:
        _start()
        if _request(["loadfile", station["url"], "replace"], wait=3) is None:
            raise RuntimeError("Could not send the station to mpv")


def toggle_selected(station: dict) -> None:
    state = status()
    if state["url"] != station["url"]:
        play(station)
    elif state["paused"]:
        _request(["set_property", "pause", False])
    elif _request(["stop"]) is None:
        play(station)
