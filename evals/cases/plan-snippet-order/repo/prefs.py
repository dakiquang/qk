#!/usr/bin/env python3
"""A preference hook: reads one JSON prompt on stdin and says whether it asks to remember a preference."""
import json
import sys


def run_hook(stdin_text):
    data = json.loads(stdin_text or "{}")
    prompt = str(data.get("prompt", "")) if isinstance(data, dict) else ""
    return "remember" if prompt.lower().startswith("from now on") else ""


def main(argv):
    if argv[1:2] == ["hook"]:
        run_hook(sys.stdin.read())
        return 0
    print("usage: prefs.py hook", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
