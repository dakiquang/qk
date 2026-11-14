#!/usr/bin/env python3
"""Grade the bundle-malformed review case: `python3 -I check.py <workdir> <final-text-file>` prints a JSON list.

A place counts as caught when a blocker or important finding names its file with a line inside its range."""
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parent
# Inclusive line ranges in bundle/loader.py as applied from review.diff.
PLACES = {"capacity": ("bundle/loader.py", 14, 18),
          "nested-statement": ("bundle/loader.py", 33, 38),
          "list-name": ("bundle/loader.py", 51, 58)}
SERIOUS = ("blocker", "important")
RESULT_RE = re.compile(r"```qk-result\s*\n(.*?)\n```", re.S)


def criterion(name, passed, detail=""):
    return {"name": name, "passed": bool(passed), "detail": detail}


def diff_files():
    text = (CASE / "review.diff").read_text(encoding="utf-8")
    return set(re.findall(r"(?m)^\+\+\+ b/(.+)$", text))


def repo_path(path, workdir):
    text = str(path or "").strip()
    for root in (str(workdir), str(Path(workdir).resolve())):
        if text.startswith(root + "/"):
            text = text[len(root) + 1:]
    while text.startswith("./"):
        text = text[2:]
    return text


def line_number(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def main():
    workdir, final = Path(sys.argv[1]), Path(sys.argv[2])
    text = final.read_text(encoding="utf-8") if final.is_file() else ""
    blocks = RESULT_RE.findall(text)
    result, problem = None, ""
    if not blocks:
        problem = "no qk-result block"
    else:
        try:
            result = json.loads(blocks[-1])
        except ValueError as error:
            problem = f"qk-result is not valid JSON: {error}"
    if result is not None and not isinstance(result, dict):
        result, problem = None, "qk-result is not an object"
    criteria = [criterion("result", result is not None and result.get("status") == "done",
                          problem or ("" if result.get("status") == "done" else f"status {result.get('status')!r}"))]
    findings = [f for f in (result or {}).get("findings") or [] if isinstance(f, dict)]
    serious = [(repo_path(f.get("file"), workdir), line_number(f.get("line")))
               for f in findings if str(f.get("severity", "")).lower() in SERIOUS]
    for name, (path, first, last) in PLACES.items():
        hits = [line for file, line in serious if file == path and line is not None and first <= line <= last]
        criteria.append(criterion(name, hits, f"lines {hits}" if hits else f"no blocker/important finding in {path}:{first}-{last}"))
    inside = diff_files()
    outside = sorted({f"{file}:{line}" for file, line in serious if file not in inside})
    criteria.append(criterion("no-outside-important", not outside, f"outside the diff: {', '.join(outside)}" if outside else ""))
    print(json.dumps(criteria, indent=2))


if __name__ == "__main__":
    main()
