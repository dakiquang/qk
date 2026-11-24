#!/usr/bin/env python3
"""SessionStart hook for Claude Code and Codex: one reminder when runs wait for a decision or are still working.

Prints `{"systemMessage": ..., "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ...}}`
only when there is something to say, so a session with nothing pending costs no tokens. The hook's own input on
stdin is read and ignored. `$QK_BIN` names the qk command (default `qk`).
"""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import status_lines  # noqa: E402


def pending():
    command = shlex.split(os.environ.get("QK_BIN", "qk")) + ["brief", "--pending"]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def main():
    if not sys.stdin.isatty():
        sys.stdin.read()
    parts = [text for text in [pending(), *status_lines.lines()] if text]
    if not parts:
        return 0
    message = "; ".join(parts)
    hint = " Use the qk-morning skill to read the cards and record decisions." if parts[0].startswith(
        "qk: ") and "to decide" in parts[0] else ""
    print(json.dumps({"systemMessage": message,
                      "hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": message + "." + hint}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
