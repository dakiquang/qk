#!/usr/bin/env python3
"""Grade the waf-bundle-review case: `python3 -I check.py <workdir> <final-text-file>` prints a JSON list.

The diff is the real waf-upgrade-check pull request that added the AWS MCP bundle mode (about 1,200 added lines in
10 files), with the eight defects that the real review needed several rounds to find put back. A place counts as
caught when a blocker or important finding names its file and its claim or fix names the field and what is wrong
with it. Like the runner, the grader does not require the cited line to be exact: reviewers often cite diff lines.
"""
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parent
BUNDLE = "src/waf_upgrade_check/bundle.py"
COLLECT = "src/waf_upgrade_check/collect.py"
SKILL = "skills/waf-upgrade-check/SKILL.md"
# name: (file, first line anchor, end anchor or None for the end of the file, field words, defect words).
# A finding must contain one field word and one defect word in its claim or fix.
PLACES = {
    "pagination-empty-page": (COLLECT, "    while True:", "    names = []", ("marker", "page", "paginat"),
                              ("empty", "stop", "break", "skip", "miss", "drop", "omit", "lost")),
    "rules-not-list": (BUNDLE, "def _check_rules(", "def _catalog(", ("rules",),
                       ("list", "null", "none", "type", "iterable")),
    "priority-type": (BUNDLE, "def _check_rules(", "def _catalog(", ("priority",),
                      ("int", "integer", "type", "string", "number", "compar")),
    "nested-statement": (BUNDLE, "def _check_rules(", "def _catalog(", ("statement",),
                         ("null", "none", "nested", "missing", "object", "dict", "shape", "label")),
    "capacity-type": (BUNDLE, "def _catalog(", "def load_bundle(", ("capacity",),
                      ("int", "integer", "type", "string", "number", "compar")),
    "label-name-type": (BUNDLE, "def _catalog(", "def load_bundle(", ("label",),
                        ("str", "string", "type", "startswith", "non-string")),
    "listed-version-name": (BUNDLE, "def _catalog(", "def load_bundle(", ("name",),
                            ("str", "string", "type", "null", "none", "join")),
    "caller-account-check": (SKILL, None, None, ("account",),
                             ("compare", "mismatch", "confirm", "differ", "match", "verify")),
}
SERIOUS = ("blocker", "important")
RESULT_RE = re.compile(r"```qk-result\s*\n(.*?)\n```", re.S)


def criterion(name, passed, detail=""):
    return {"name": name, "passed": bool(passed), "detail": detail}


def span(workdir, path, start, end):
    """Inclusive 1-based line range of a place in the applied file; the whole file when no anchors."""
    lines = (Path(workdir) / path).read_text(encoding="utf-8").splitlines()
    if start is None:
        return 1, len(lines)
    first = next(i for i, line in enumerate(lines, 1) if line.startswith(start))
    last = next((i - 1 for i, line in enumerate(lines, 1) if i > first and line.startswith(end)), len(lines))
    return first, last


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
    done = result is not None and result.get("status") == "done"
    criteria = [criterion("result", done, problem or ("" if done else f"status {result.get('status')!r}"))]
    findings = [f for f in (result or {}).get("findings") or [] if isinstance(f, dict)]
    serious = [(repo_path(f.get("file"), workdir), line_number(f.get("line")),
                f"{f.get('claim', '')} {f.get('fix', '')}".lower())
               for f in findings if str(f.get("severity", "")).lower() in SERIOUS]
    for name, (path, start, end, field, defect) in PLACES.items():
        first, last = span(workdir, path, start, end)
        hits = [line for file, line, words in serious
                if file == path and any(w in words for w in field) and any(w in words for w in defect)]
        criteria.append(criterion(name, hits, f"lines {hits}" if hits else
                                  f"no blocker/important finding on {path} (the place is lines {first}-{last})"))
    inside = diff_files()
    outside = sorted({f"{file}:{line}" for file, line, _ in serious if file not in inside})
    criteria.append(criterion("no-outside-important", not outside,
                              f"outside the diff: {', '.join(outside)}" if outside else ""))
    print(json.dumps(criteria, indent=2))


if __name__ == "__main__":
    main()
