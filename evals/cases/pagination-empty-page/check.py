#!/usr/bin/env python3
"""Grade the pagination-empty-page case: `python3 -I check.py <workdir> <final-text-file>` prints a JSON list of criteria."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CASE = Path(__file__).resolve().parent
BUGGY = "collector/collect.py"
REFERENCE = CASE / "hidden" / "reference_collect.txt"  # a correct collect.py, kept outside repo/ and not a test module
LABELS = ("Done", "Evidence", "Not verified", "Needs your decision")


def criterion(name, passed, detail=""):
    return {"name": name, "passed": bool(passed), "detail": detail}


def python(args, cwd, timeout=120):
    """(passed, output tail) of `python <args>` in `cwd` with `cwd` importable and no bytecode written."""
    env = dict(os.environ, PYTHONPATH=str(cwd), PYTHONDONTWRITEBYTECODE="1")
    try:
        proc = subprocess.run([sys.executable, *args], cwd=str(cwd), env=env, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    return proc.returncode == 0, (proc.stderr or proc.stdout).strip()[-800:]


def tests_against(workdir, module):
    """(passed, output) of the workdir's own tests with `collector/collect.py` replaced by `module`."""
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "repo"
        shutil.copytree(workdir, copy, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        shutil.copy2(module, copy / BUGGY)
        return python(["-m", "unittest"], copy)


def catches_bug(workdir):
    """The workdir's tests must fail with the original module and pass with a correct one.

    The second half rejects tests that fail for an unrelated reason, such as asserting on the source text."""
    old_passed, old_output = tests_against(workdir, CASE / "repo" / BUGGY)
    if old_passed:
        return criterion("test-catches-bug", False, "the repository's tests still pass with the original module")
    good_passed, good_output = tests_against(workdir, REFERENCE)
    if not good_passed:
        return criterion("test-catches-bug", False, f"the tests also fail with a correct module: {good_output}")
    return criterion("test-catches-bug", True, old_output)


def git(workdir, *args):
    return subprocess.run(["git", *args], cwd=str(workdir), capture_output=True, text=True, check=True).stdout


def scope(workdir):
    """Only the collector module and test files may change, and the module must change."""
    base = git(workdir, "rev-list", "--max-parents=0", "HEAD").split()[0]
    git(workdir, "add", "-A")
    try:
        names = set(git(workdir, "diff", "--cached", "--name-only", base).splitlines())
    finally:
        git(workdir, "reset", "-q")
    outside = sorted(n for n in names if n != BUGGY and not (n.startswith("tests/") and n.endswith(".py")))
    if outside:
        return criterion("scope", False, f"changed outside scope: {', '.join(outside)}")
    return criterion("scope", BUGGY in names, "" if BUGGY in names else f"{BUGGY} was not changed")


def report(text):
    missing = [label for label in LABELS
               if not re.search(rf"(?m)^\s*(\*\*)?{re.escape(label)}(\*\*)?\s*:", text)]
    return criterion("report", not missing, f"missing labels: {', '.join(missing)}" if missing else "")


def main():
    workdir, final = Path(sys.argv[1]), Path(sys.argv[2])
    text = final.read_text(encoding="utf-8") if final.is_file() else ""
    hidden = CASE / "hidden"
    print(json.dumps([
        criterion("hidden-regression",
                  *python(["-m", "unittest", "discover", "-s", str(hidden), "-t", str(hidden)], workdir)),
        criterion("repo-tests", *python(["-m", "unittest"], workdir)),
        catches_bug(workdir),
        scope(workdir),
        report(text),
    ], indent=2))


if __name__ == "__main__":
    main()
