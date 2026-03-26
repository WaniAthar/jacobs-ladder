"""Process scanning and Claude Code instance detection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import psutil


@dataclass
class Instance:
    """A discovered Claude Code instance."""

    name: str
    pid: int
    cwd: str


def _is_claude_process(proc: psutil.Process) -> bool:
    """Check if a process is a Claude Code instance."""
    try:
        cmdline = proc.cmdline()
        return any("claude" == arg for arg in cmdline)
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return False


def _get_cwd(proc: psutil.Process) -> str | None:
    """Get the working directory of a process, or None if inaccessible."""
    try:
        return proc.cwd()
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return None


def _deduplicate_names(instances: list[Instance]) -> list[Instance]:
    """Append numeric suffixes to duplicate instance names."""
    seen: dict[str, int] = {}
    result: list[Instance] = []

    for inst in instances:
        base_name = inst.name
        if base_name in seen:
            seen[base_name] += 1
            inst.name = f"{base_name}-{seen[base_name]}"
        else:
            seen[base_name] = 1
        result.append(inst)

    return result


def discover_instances(current_cwd: str | None = None) -> list[Instance]:
    """Find all running Claude Code instances, excluding the current one.

    Args:
        current_cwd: Working directory of the calling instance. If provided,
                     processes with this cwd are excluded from results.

    Returns:
        List of discovered Instance objects.
    """
    if current_cwd is None:
        current_cwd = str(Path.cwd())

    current_cwd = str(Path(current_cwd).resolve())
    raw_instances: list[Instance] = []

    for proc in psutil.process_iter():
        if not _is_claude_process(proc):
            continue

        cwd = _get_cwd(proc)
        if cwd is None:
            continue

        resolved_cwd = str(Path(cwd).resolve())
        if resolved_cwd == current_cwd:
            continue

        name = Path(cwd).name
        raw_instances.append(Instance(name=name, pid=proc.pid, cwd=cwd))

    return _deduplicate_names(raw_instances)
