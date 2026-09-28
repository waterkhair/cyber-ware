"""Toggle the picker process without affecting other Python applications."""

from __future__ import annotations

import os
import shutil
import signal
import sys
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


def main() -> int:
    if sys.argv[1:] == ["--stop"]:
        for pid in _picker_pids():
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                continue
        return 0
    if sys.argv[1:]:
        print("usage: cyber-wall-toggle [--stop]", file=sys.stderr)
        return 2

    for pid in _picker_pids():
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        return 0

    launcher = shutil.which("cyber-wall")
    if launcher is None:
        launcher = str(Path(sys.argv[0]).resolve().parents[2] / "bin" / "cyber-wall")
    os.execv(launcher, [launcher])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
