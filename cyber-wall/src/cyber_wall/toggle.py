"""Toggle the picker process without affecting other Python applications."""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path


def _picker_pids() -> list[int]:
    own_uid = os.getuid()
    current_pid = os.getpid()
    matches: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == current_pid:
            continue
        try:
            if entry.stat().st_uid != own_uid:
                continue
            arguments = entry.joinpath("cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if b"cyber_wall.picker" in arguments or any(
            argument.endswith(b"/cyber_wall/picker.py") for argument in arguments
        ):
            matches.append(pid)
    return matches


def stop_picker() -> None:
    pids = _picker_pids()
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if not any(Path(f"/proc/{pid}").exists() for pid in pids):
            return
        time.sleep(0.05)
    if any(Path(f"/proc/{pid}").exists() for pid in pids):
        raise RuntimeError("the picker did not exit within three seconds")


def toggle() -> int:
    if _picker_pids():
        stop_picker()
        return 0
    os.execv(sys.executable, [sys.executable, "-m", "cyber_wall.picker"])
    return 0
