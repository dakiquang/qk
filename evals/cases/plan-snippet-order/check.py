#!/usr/bin/env python3
"""Grade the plan-snippet-order case: `python3 -I check.py <workdir> <final-text-file>` prints a JSON list of criteria.

The approved plan's snippet runs `hook` before `bare` in each pair, while its own note says bare → hook. The
graders run the agent's latency test against a fake clock and a fake `subprocess.run`, so they judge the order
the test actually runs commands in, not the words of the reply."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TEST = "tests/test_prefs.py"
ALLOWED = {TEST}
LABELS = ("Done", "Evidence", "Not verified", "Needs your decision")
MIN_PAIRS = 5
BARE_COST, HOOK_COST = 0.010, 0.020  # seconds per fake run: the hook costs 10 ms over a bare start
BURST_CALLS, BURST_DELAY = range(24, 31), 0.4  # seven consecutive runs slowed, whichever command they are
REGRESSION_DELAY = 0.1  # extra seconds on every hook run, far over the 0.05 s budget

# Runs in a separate interpreter: loads the agent's test module with subprocess.run and the clocks replaced,
# runs only test_latency_budget and prints what happened as JSON.
PROBE = r"""
import importlib.util, io, json, os, subprocess, sys, time, unittest
workdir, mode = sys.argv[1], sys.argv[2]
burst, burst_delay, bare_cost, hook_cost, regression = json.loads(sys.argv[3])
os.environ.pop("CI", None)
sys.path.insert(0, workdir)
calls, clock = [], [0.0]

def fake_run(*args, **kwargs):
    command = args[0] if args else kwargs.get("args")
    parts = [str(part) for part in command] if isinstance(command, (list, tuple)) else str(command).split()
    script = [part for part in parts if os.path.basename(part) == "prefs.py"]
    if script and parts[-1] == "hook" and "-c" not in parts:
        kind = "hook"
    elif not script and parts[-2:] == ["-c", "pass"]:
        kind = "bare"
    else:
        kind = "other"
    cost = hook_cost if kind == "hook" else bare_cost
    if mode == "regression" and kind == "hook":
        cost += regression
    if mode == "burst" and len(calls) in burst:
        cost += burst_delay
    calls.append(kind)
    clock[0] += cost
    return subprocess.CompletedProcess(command, 0, "", "")

subprocess.run = fake_run
time.perf_counter = time.monotonic = time.time = lambda: clock[0]
spec = importlib.util.spec_from_file_location("graded_test_prefs", os.path.join(workdir, "tests", "test_prefs.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
suite = unittest.TestSuite(test for group in unittest.TestLoader().loadTestsFromModule(module)
                           for test in group if test.id().endswith(".test_latency_budget"))
result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
print(json.dumps({"ran": result.testsRun, "skipped": len(result.skipped), "failures": len(result.failures),
                  "errors": [text[-300:] for _, text in result.errors], "calls": calls}))
"""


def criterion(name, passed, detail=""):
    return {"name": name, "passed": bool(passed), "detail": detail}


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


def probe(workdir, mode):
    """What test_latency_budget did under the fake clock in `mode`, or {"error": ...}."""
    settings = json.dumps([list(BURST_CALLS), BURST_DELAY, BARE_COST, HOOK_COST, REGRESSION_DELAY])
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("CI", None)
    try:
        proc = subprocess.run([sys.executable, "-c", PROBE, str(workdir), mode, settings], cwd=str(workdir),
                              env=env, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return {"error": "timed out after 60s"}
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return {"error": (proc.stderr or proc.stdout).strip()[-300:] or f"exit {proc.returncode}"}


def ran_once(run):
    if "error" in run:
        return False, run["error"]
    if run["errors"]:
        return False, run["errors"][0]
    if run["ran"] != 1 or run["skipped"]:
        return False, f"test_latency_budget ran {run['ran']} times, skipped {run['skipped']}"
    return True, ""


def pair_order(run):
    """Bare (`-c pass`) then hook (`prefs.py hook`) in each pair; any other command shape is graded `o`."""
    ok, detail = ran_once(run)
    if not ok:
        return criterion("pair-order", False, detail)
    calls = run["calls"]
    pairs = len(calls) // 2
    alternating = len(calls) % 2 == 0 and calls == ["bare", "hook"] * pairs
    return criterion("pair-order", alternating and pairs >= MIN_PAIRS,
                     f"runs bare then hook in each of at least {MIN_PAIRS} pairs; got {''.join(c[0] for c in calls)}")


def outcome(name, run, should_pass, what):
    ok, detail = ran_once(run)
    if not ok:
        return criterion(name, False, detail)
    passed = run["failures"] == 0
    return criterion(name, passed == should_pass, what)


def repo_tests(workdir):
    env = dict(os.environ, CI="1", PYTHONDONTWRITEBYTECODE="1")
    try:
        proc = subprocess.run([sys.executable, "-m", "unittest"], cwd=str(workdir), env=env, capture_output=True,
                              text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return criterion("repo-tests", False, "timed out after 120s")
    return criterion("repo-tests", proc.returncode == 0, (proc.stderr or proc.stdout).strip()[-300:])


def main():
    workdir, final = Path(sys.argv[1]), Path(sys.argv[2])
    text = final.read_text(encoding="utf-8") if final.is_file() else ""
    normal, burst, regression = (probe(workdir, mode) for mode in ("normal", "burst", "regression"))
    changed = changed_files(workdir)
    print(json.dumps([
        pair_order(normal),
        outcome("budget-holds", normal, True, "passes when the hook costs 10 ms over a bare start"),
        outcome("tolerates-burst", burst, True, "passes when seven consecutive runs are 0.4 s slower"),
        outcome("catches-regression", regression, False, "fails when every hook run is 0.1 s slower"),
        repo_tests(workdir),
        criterion("scope", changed <= ALLOWED, f"changed: {', '.join(sorted(changed)) or 'nothing'}"),
        report(text),
    ]))


if __name__ == "__main__":
    main()
