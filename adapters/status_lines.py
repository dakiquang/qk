#!/usr/bin/env python3
"""Status lines for a runtime's status bar: one line per item from every command listed in the status-commands file.

The file is `$QK_STATUS_COMMANDS`, else `$XDG_CONFIG_HOME/qk/status-commands`, else `~/.config/qk/status-commands`,
one shell command per line (`#` starts a comment). Without the file only `qk run status --line` runs. Each command
gets one second; a command that fails, times out or prints nothing adds nothing. Output is cached for
`$QK_STATUS_TTL` seconds (default 5), so a status bar redrawn many times a second runs the commands at most once.
"""

import hashlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

DEFAULT = ["qk run status --line"]
TIMEOUT = 1


def commands():
    path = os.environ.get("QK_STATUS_COMMANDS") or str(
        Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "qk" / "status-commands")
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return DEFAULT
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def run(command):
    """The command's non-empty lines, or none. It runs in its own process group, so a timeout stops the shell and
    everything it started."""
    try:
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                stdin=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return []
    try:
        output, _ = proc.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        proc.stdout.close()  # a child that left the group may still hold the pipe: do not wait for it
        proc.wait()
        return []
    return [line for line in output.splitlines() if line.strip()] if proc.returncode == 0 else []


def lines():
    listed = commands()
    # The commands and the settings that choose what they read: two sessions on different state directories
    # must not share a cache.
    scope = [*listed, *(f"{name}={os.environ.get(name, '')}" for name in sorted(os.environ)
                         if name.startswith("QK_") or name in ("XDG_STATE_HOME", "HOME"))]
    key = hashlib.sha256("\n".join(scope).encode("utf-8")).hexdigest()[:12]
    cache = Path(tempfile.gettempdir()) / f"qk-status-lines.{os.getuid()}.{key}"
    ttl = float(os.environ.get("QK_STATUS_TTL", "5"))
    try:
        if time.time() - cache.stat().st_mtime < ttl:
            return cache.read_text(encoding="utf-8").splitlines()
    except OSError:
        pass
    found = [line for command in listed for line in run(command)]
    try:
        temporary = cache.with_suffix(f".{os.getpid()}")
        temporary.write_text("".join(line + "\n" for line in found), encoding="utf-8")
        temporary.replace(cache)
    except OSError:
        pass
    return found


if __name__ == "__main__":
    output = lines()
    if output:
        print("\n".join(output))
    sys.exit(0)
