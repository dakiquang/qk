#!/bin/sh
# Claude Code status line: run the status line command you already use (its words follow this script's path),
# with the same JSON on stdin, then add qk's status lines below it.
# settings.json: "statusLine": {"type": "command", "refreshInterval": 10,
#                "command": "/bin/sh <qk>/adapters/claude/statusline.sh <your existing command and its arguments>"}
input=$(cat)
if [ "$#" -gt 0 ]; then
  printf '%s' "$input" | "$@"
fi
exec python3 "$(dirname "$0")/../status_lines.py"
