#!/usr/bin/env python3
"""Grade the csv-export case: `python3 -I check.py <workdir> <final-text-file>` prints a JSON list of criteria."""
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parent
MODULE = "tasklist/csv_export.py"
ALLOWED = {MODULE, "tests/test_csv_export.py"}
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


def git(workdir, *args):
    return subprocess.run(["git", *args], cwd=str(workdir), capture_output=True, text=True, check=True).stdout


def changed_files(workdir):
    """Files that differ from the case's base commit, including uncommitted and untracked ones."""
    base = git(workdir, "rev-list", "--max-parents=0", "HEAD").split()[0]
    git(workdir, "add", "-A")
    try:
        return set(git(workdir, "diff", "--cached", "--name-only", base).splitlines())
    finally:
        git(workdir, "reset", "-q")


def report(text):
    missing = [label for label in LABELS
               if not re.search(rf"(?m)^\s*(\*\*)?{re.escape(label)}(\*\*)?\s*:", text)]
    return criterion("report", not missing, f"missing labels: {', '.join(missing)}" if missing else "")


def uses_csv_module(workdir):
    """The task requires the standard-library csv writer; a hand-written serializer does not pass."""
    path = workdir / MODULE
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError) as exc:
        return criterion("csv-module", False, f"cannot parse {MODULE}: {exc}")
    imported = any((isinstance(node, ast.Import) and any(a.name == "csv" for a in node.names))
                   or (isinstance(node, ast.ImportFrom) and node.module == "csv") for node in ast.walk(tree))
    writes = any(isinstance(node, ast.Attribute) and node.attr in ("writer", "DictWriter")
                 or isinstance(node, ast.Name) and node.id in ("writer", "DictWriter") for node in ast.walk(tree))
    passed = imported and writes
    return criterion("csv-module", passed, "" if passed else "csv.writer or csv.DictWriter is not used")


def main():
    workdir, final = Path(sys.argv[1]), Path(sys.argv[2])
    text = final.read_text(encoding="utf-8") if final.is_file() else ""
    names = changed_files(workdir)
    outside = sorted(names - ALLOWED)
    if outside:
        scope = criterion("scope", False, f"changed outside scope: {', '.join(outside)}")
    else:
        scope = criterion("scope", MODULE in names, "" if MODULE in names else f"{MODULE} was not added")
    hidden = CASE / "hidden"
    print(json.dumps([
        criterion("hidden-tests", *python(["-m", "unittest", "discover", "-s", str(hidden), "-t", str(hidden)], workdir)),
        criterion("repo-tests", *python(["-m", "unittest"], workdir)),
        scope,
        uses_csv_module(workdir),
        report(text),
    ], indent=2))


if __name__ == "__main__":
    main()
