"""Desktop notification delivery."""

from __future__ import annotations

import shutil
import subprocess


def send(title: str, body: str, urgency: str = "normal", timeout_ms: int = 8000) -> None:
    notify_send = shutil.which("notify-send")
    if not notify_send:
        raise RuntimeError("notify-send is missing; install libnotify")
    subprocess.run(
        [notify_send, "--app-name=cyber-signal", f"--urgency={urgency}",
         f"--expire-time={timeout_ms}", title, body],
        check=True,
    )
