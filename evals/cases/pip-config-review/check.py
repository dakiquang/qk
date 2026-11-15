#!/usr/bin/env python3
"""Grade pip-config-review with applied-file ranges and substantive review findings.

Usage: python3 -I check.py <workdir> <final-text-file>. Prints a JSON list.
Each defect needs a blocker/important finding whose claim OR fix names both
the affected field and the failure (not merely unrelated text at those lines).
"""
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parent
CONFIGURATION = "src/pip/_internal/configuration.py"
# Inclusive lines AFTER applying review.diff; SOURCE.txt documents these ranges.
PLACES = {"null-device": (400, 413), "parser-reuse": (400, 405), "env-unset": (194, 224)}
# Every group must match within the same claim or fix; alternatives allow paraphrases.
SUBSTANCE = {
    "null-device": (
        r"devnull|/dev/null|null[ -]device|windows.{0,20}\bnul\b|\bnul\b.{0,20}windows",
        r"discard|silently.{0,40}(?:writ|drop|set|los)|drops? (?:the |a |all )?(?:value|write|change|data)|lost|loses? |"
        r"success|exits? (?:with )?(?:0|zero)|no[ -]op|reject|refuse|guard|prevent.{0,30}writ|"
        r"rais\w*.{0,30}(?:error|configurationerror)",
    ),
    "parser-reuse": (
        r"parser",
        r"wrong (?:container|scope|bucket|list|variant)|"
        r"(?:instead of|rather than).{0,40}(?:load_only|kind\.env|scope|container|bucket)|"
        r"load_only.{0,30}(?:not|instead of|rather than).{0,30}(?:kind\.env|\benv\b)|"
        r"re[ -]?use|re[ -]?entran|recreat|"
        r"(?:lost|loses?|overwrit|discard).{0,40}(?:pending|earlier|unsaved|write|change|set|value)|"
        r"(?:pending|earlier|unsaved).{0,40}(?:lost|loses?|overwrit|discard)",
    ),
    "env-unset": (
        r"unset|remov",
        r"environment|pip_config_file|kind\.env|_use_env|\benv\b|wrong (?:scope|variant|bucket)",
        r"no such key|missing key|key.{0,30}(?:absent|missing|not found)|"
        r"(?:absent|missing).{0,30}key|cannot find|can't find|"
        r"(?:lookup|look\w* (?:up|in)|read\w*|check\w*|delet\w*|remov\w*).{0,60}"
        r"(?:wrong|load_only|user scope)|(?:wrong|load_only).{0,60}(?:lookup|read|check|delet)|"
        r"(?:track|select|use)\w*.{0,30}(?:env|environment).{0,20}(?:scope|variant|bucket)",
    ),
}
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


def names_defect(name, finding):
    for field in ("claim", "fix"):
        words = " ".join(str(finding.get(field, "")).lower().split())
        if all(re.search(pattern, words) for pattern in SUBSTANCE[name]):
            return True
    return False


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
    if not isinstance(result, dict):
        result, problem = None, problem or "qk-result is not an object"
    done = result is not None and result.get("status") == "done"
    criteria = [criterion("result", done,
                          problem or ("" if done else f"status {result.get('status')!r}"))]
    findings = (result or {}).get("findings") or []
    findings = findings if isinstance(findings, list) else []
    serious = [(repo_path(f.get("file"), workdir), line_number(f.get("line")), f)
               for f in findings if isinstance(f, dict) and str(f.get("severity", "")).lower() in SERIOUS]
    for name, (first, last) in PLACES.items():
        hits = [line for file, line, f in serious
                if file == CONFIGURATION and line is not None and first <= line <= last and names_defect(name, f)]
        criteria.append(criterion(name, hits, f"lines {hits}" if hits else
                                  f"no blocker/important finding naming the defect in {CONFIGURATION}:{first}-{last}"))
    inside = diff_files()
    outside = sorted({f"{file}:{line}" for file, line, _ in serious if file not in inside})
    criteria.append(criterion("no-outside-important", not outside,
                              f"outside the diff: {', '.join(outside)}" if outside else ""))
    print(json.dumps(criteria, indent=2))


if __name__ == "__main__":
    main()
