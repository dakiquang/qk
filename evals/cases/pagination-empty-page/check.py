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


def catches_bug(workdir):
    """The workdir's own tests must fail once the original buggy module is put back."""
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "repo"
        shutil.copytree(workdir, copy, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        shutil.copy2(CASE / "repo" / BUGGY, copy / BUGGY)
        env = dict(os.environ, PYTHONPATH=str(copy), PYTHONDONTWRITEBYTECODE="1")
        try:
            proc = subprocess.run([sys.executable, "-m", "unittest"], cwd=str(copy), env=env, capture_output=True,
                                  text=True, timeout=120)
        except subprocess.TimeoutExpired:
            return criterion("test-catches-bug", False, "tests timed out against the original module")
    if proc.returncode == 0:
        return criterion("test-catches-bug", False, "the repository's tests still pass with the original module")
    return criterion("test-catches-bug", True, (proc.stderr or proc.stdout).strip()[-800:])


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
        report(text),
    ], indent=2))


if __name__ == "__main__":
    main()
