"""Network, Arch update, and disk-space checks."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import notify
from .config import load_config, read_state, write_state


@dataclass(frozen=True)
class Result:
    title: str
    body: str
    urgency: str = "normal"


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def network_status() -> tuple[str, str]:
    """Return a concise connectivity state and a user-facing description."""
    if not shutil.which("nmcli"):
        raise RuntimeError("nmcli is missing; network monitoring requires NetworkManager")
    state = _run(["nmcli", "-t", "-f", "STATE,CONNECTIVITY", "general"])
    if state.returncode != 0:
        raise RuntimeError(state.stderr.strip() or "nmcli could not read network state")
    fields = state.stdout.strip().split(":", 1)
    manager_state = fields[0].strip().lower() if fields else "unknown"
    connectivity = fields[1].strip().lower() if len(fields) > 1 else "unknown"
    if manager_state != "connected" or connectivity != "full":
        return "offline", "No internet connection detected."

    active = _run(["nmcli", "-t", "-f", "TYPE,NAME", "connection", "show", "--active"])
    link = "network"
    if active.returncode == 0:
        for row in active.stdout.splitlines():
            kind, _, name = row.partition(":")
            if kind in ("802-11-wireless", "wifi"):
                link = f"Wi-Fi · {name or 'connected'}"
                break
            if kind == "802-3-ethernet":
                link = f"Ethernet · {name or 'connected'}"
    return "online", f"Internet connection restored ({link})."


def check_network(*, baseline: bool = False, always: bool = False) -> Result | None:
    config = load_config()
    if not config["checks"].get("network", True):
        return None
    current, description = network_status()
    previous = read_state("network.json")
    write_state("network.json", current)
    if baseline or previous is None or previous == current:
        return None
    return Result("Connection lost" if current == "offline" else "Connection restored",
                  description,
                  "critical" if current == "offline" else "normal")


def updates_result() -> Result | None:
    if not shutil.which("checkupdates"):
        raise RuntimeError("checkupdates is missing; install pacman-contrib to check Arch updates")
    result = _run(["checkupdates"])
    # pacman-contrib: exit 2 means there are no updates; 0 means updates found.
    if result.returncode == 2 or not result.stdout.strip():
        return None
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "checkupdates failed")
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    fingerprint = "\n".join(lines)
    previous = read_state("updates.json")
    write_state("updates.json", fingerprint)
    if previous == fingerprint:
        return None
    limit = load_config()["update_detail_limit"]
    summary = lines[:limit]
    if len(lines) > limit:
        summary.append(f"… and {len(lines) - limit} more")
    return Result(f"{len(lines)} package update{'s' if len(lines) != 1 else ''} available",
                  "\n".join(summary))


def check_updates(*, baseline: bool = False, always: bool = False) -> Result | None:
    if not load_config()["checks"].get("updates", True):
        return None
    if baseline:
        if not shutil.which("checkupdates"):
            raise RuntimeError("checkupdates is missing; install pacman-contrib to check Arch updates")
        result = _run(["checkupdates"])
        if result.returncode not in (0, 2):
            raise RuntimeError(result.stderr.strip() or "checkupdates failed")
        write_state("updates.json", result.stdout.strip())
        return None
    return updates_result()


def disk_status(mount: str) -> int | None:
    path = Path(mount)
    if not path.exists():
        return None
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    if usage.total <= 0:
        return None
    # Use free space available to the user, including reserved filesystem blocks.
    return round((usage.total - usage.free) * 100 / usage.total)


def check_disk(*, baseline: bool = False, always: bool = False) -> Result | None:
    config = load_config()
    if not config["checks"].get("disk", True):
        return None
    levels: dict[str, int] = {}
    alerts: list[tuple[str, int, str]] = []
    warning = config["disk_warning_percent"]
    critical = config["disk_critical_percent"]
    for mount in config["disk_mounts"]:
        used = disk_status(mount)
        if used is None:
            continue
        level = 2 if used >= critical else 1 if used >= warning else 0
        levels[mount] = level
        if level:
            alerts.append((mount, used, "critical" if level == 2 else "warning"))
    previous = read_state("disk.json", {})
    write_state("disk.json", levels)
    if baseline:
        return None
    transitions = [(mount, used, urgency) for mount, used, urgency in alerts
                   if always or previous.get(mount, 0) < (2 if urgency == "critical" else 1)]
    if not transitions:
        return None
    details = [f"{mount}: {used}% used ({urgency})" for mount, used, urgency in transitions]
    urgency = "critical" if any(level == "critical" for _, _, level in transitions) else "normal"
    return Result("Disk space running low", "\n".join(details), urgency)


CHECKS = {"network": check_network, "updates": check_updates, "disk": check_disk}


def run_check(name: str, *, baseline: bool = False, always: bool = False) -> bool:
    result = CHECKS[name](baseline=baseline, always=always)
    if result is None:
        return False
    notify.send(result.title, result.body, result.urgency)
    return True
