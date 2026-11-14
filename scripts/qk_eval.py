#!/usr/bin/env python3
"""qk-eval: run fixed eval cases on one runtime, grade them by code and compare them with the baseline.

Each case is one real agent turn in a throwaway git repository, graded by the case's check.py. A criterion
that passed in the baseline and fails now, or tokens more than 10% above the baseline, is a regression.
"""
import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qk_run  # noqa: E402

CASES = qk_run.QK_ROOT / "evals" / "cases"
BASELINE = qk_run.QK_ROOT / "evals" / "baseline.json"
REVIEW = "runner-review"
CHECK_TIMEOUT = 300
TOKEN_LIMIT_PERCENT = 110
GIT_IDENTITY = ("-c", "user.name=qk-eval", "-c", "user.email=qk-eval@example.invalid", "-c", "commit.gpgsign=false")


def state_root():
    xdg = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(xdg) / "qk-eval"


def load_case(directory):
    """Case config from `<case>/case.json`: which skill (or the runner's review) runs it, and with write access?"""
    config = json.loads((directory / "case.json").read_text(encoding="utf-8"))
    skill = config.get("skill")
    if not isinstance(skill, str) or not skill or (skill != REVIEW and not qk_run.skill(skill).is_file()):
        raise SystemExit(f"qk-eval: {directory.name}: unknown skill {skill!r}")
    if not isinstance(config.get("write"), bool):
        raise SystemExit(f"qk-eval: {directory.name}: case.json needs \"write\": true or false")
    return {"name": directory.name, "dir": directory, "skill": skill, "write": config["write"]}


def all_cases():
    if not CASES.is_dir():
        return []
    return [load_case(path) for path in sorted(CASES.iterdir()) if (path / "case.json").is_file()]


def select(args):
    """Cases picked by --case, --skill or --all, or an error message."""
    if args.case:
        directory = CASES / args.case
        if "/" in args.case or not (directory / "case.json").is_file():
            return None, f"unknown case {args.case!r}"
        return [load_case(directory)], None
    cases = all_cases()
    if args.skill:
        cases = [case for case in cases if case["skill"] == args.skill]
    if not cases:
        return None, f"no cases for {'skill ' + repr(args.skill) if args.skill else 'any skill'} in {CASES}"
    return cases, None


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def prepare(case, root):
    """Fresh git repository with the case's base committed; the review case's change is applied uncommitted."""
    workdir = root / "repo"
    shutil.copytree(case["dir"] / "repo", workdir, ignore=shutil.ignore_patterns("__pycache__"))
    if case["skill"] != REVIEW:
        shutil.copy2(case["dir"] / "task.md", workdir / "task.md")
    git(workdir, "init", "-q", "-b", "main")
    git(workdir, "add", "-A")
    git(workdir, *GIT_IDENTITY, "commit", "-qm", "base")
    if case["skill"] == REVIEW:
        git(workdir, "apply", str(case["dir"] / "review.diff"))
    return workdir


def failed_check(detail):
    return [{"name": "check.py", "passed": False, "detail": detail}]


def grade(case, workdir, final):
    """Criteria printed by the case's check.py; any failure of check.py itself is one failed criterion."""
    try:
        proc = subprocess.run([sys.executable, "-I", str(case["dir"] / "check.py"), str(workdir), str(final)],
                              cwd=str(workdir), capture_output=True, text=True, timeout=CHECK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return failed_check(f"timed out after {CHECK_TIMEOUT}s")
    if proc.returncode != 0:
        return failed_check(f"exited {proc.returncode}: {(proc.stderr or proc.stdout).strip()[-800:]}")
    try:
        criteria = json.loads(proc.stdout)
    except ValueError:
        return failed_check(f"output is not JSON: {proc.stdout.strip()[-800:]}")
    # The whole contract at once: a non-empty list of {name: str, passed: bool, detail: str}, names unique.
    if not isinstance(criteria, list) or not criteria or not all(
            isinstance(c, dict) and isinstance(c.get("name"), str) and c["name"]
            and isinstance(c.get("passed"), bool) and isinstance(c.get("detail"), str)
            for c in criteria):
        return failed_check("output is not a non-empty list of {name, passed, detail}")
    names = [c["name"] for c in criteria]
    if len(set(names)) != len(names):
        return failed_check(f"criterion names repeat: {', '.join(sorted({n for n in names if names.count(n) > 1}))}")
    return criteria


def run_case(case, spec, timeout, out_dir, scratch):
    """One agent turn on a fresh copy of the case, graded; artifacts go to `out_dir`."""
    out_dir.mkdir(parents=True)
    events = out_dir / "events.jsonl"
    events.touch()
    with tempfile.TemporaryDirectory(prefix="qk-eval-") as tmp:
        workdir = prepare(case, Path(tmp))
        if case["skill"] == REVIEW:
            plan, diff = out_dir / "plan.md", out_dir / "review.diff"
            shutil.copy2(case["dir"] / "plan.md", plan)
            shutil.copy2(case["dir"] / "review.diff", diff)
            prompt, write = qk_run.review_prompt(workdir, plan, diff), False
        else:
            prompt = (f"Read {qk_run.skill(case['skill'])} and follow it for the task in task.md in {workdir}. "
                      f"Work only inside {workdir}.\n{qk_run.NO_GIT}")
            write = case["write"]
        text, usage, error = "", None, None
        start = time.monotonic()
        try:
            text, usage = qk_run.call_agent(
                spec, prompt, workdir, write, timeout, [scratch], events=events,
                progress=lambda message: print(f"[{case['name']}] {message}", file=sys.stderr, flush=True))
        except qk_run.Blocked as exc:
            error, usage = str(exc), getattr(exc, "usage", None)
        seconds = time.monotonic() - start
        final = out_dir / "final.md"
        final.write_text(text or "", encoding="utf-8")
        criteria = grade(case, workdir, final)
    (out_dir / "check.json").write_text(json.dumps(criteria, indent=2) + "\n", encoding="utf-8")
    tokens = usage["input"] + usage["output"] if usage else None
    return {"criteria": criteria, "usage": usage, "tokens": tokens, "seconds": seconds, "error": error}


def passing(criteria):
    return {c["name"] for c in criteria if c["passed"]}


def percent(now, before):
    if now is None or not before:
        return None
    return round((now - before) * 100 / before, 1)


def compare(result, base):
    """Lost criteria, flip, token/time change and regression of a result against its baseline entry."""
    before = {name for name, ok in base.get("criteria", {}).items() if ok}
    now = passing(result["criteria"])
    lost = sorted(before - now)
    base_tokens = base.get("tokens")
    tokens_over = (result["tokens"] is not None and base_tokens is not None
                   and result["tokens"] * 100 > base_tokens * TOKEN_LIMIT_PERCENT)
    return {"lost": lost, "flipped": now != before, "tokens_pct": percent(result["tokens"], base_tokens),
            "seconds_pct": percent(result["seconds"], base.get("seconds")), "tokens_over": tokens_over,
            "regression": bool(lost) or tokens_over}


def signed(value):
    return "n/a" if value is None else f"{value:+.1f}%"  # one decimal, so +10.4% never reads as a rounded +10%


def duration(seconds):
    whole = int(round(seconds))
    return f"{whole // 60}m{whole % 60:02d}s" if whole >= 60 else f"{whole}s"


def status(result):
    if result["error"]:
        return "ERROR"
    failures = len(result["criteria"]) - len(passing(result["criteria"]))
    return f"FAIL({failures})" if failures else "PASS"


def row(case, criteria, result, tokens, time_text):
    return f"{case:<22} {criteria:<42} {result:<9} {tokens:<9} {time_text}".rstrip()


def report(spec, results, entries):
    """Table, per-case comparison lines and the verdict; returns (lines, reasons, regression)."""
    lines = [row("case", "criteria", "result", "tokens", "time")]
    for name, result in results.items():
        tokens = "n/a" if result["tokens"] is None else f"{result['tokens']:,}"
        criteria = ", ".join(c["name"] if c["passed"] else f"{c['name']}=FAIL" for c in result["criteria"])
        lines.append(row(name, criteria, status(result), tokens,
                         duration(result["seconds"])))
    reasons = []
    if not entries:
        lines.append(f"no baseline for {spec}")
    for name, result in results.items():
        if result["error"]:
            reasons.append(f"agent error: {name}")
        base = entries.get(name)
        if base is None:
            if entries:
                lines.append(f"no baseline for {spec} / {name}")
            continue
        diff = compare(result, base)
        total_before, total_now = len(base.get("criteria", {})), len(result["criteria"])
        passed_before = sum(1 for ok in base.get("criteria", {}).values() if ok)
        lost = f", lost: {', '.join(diff['lost'])}" if diff["lost"] else ""
        lines.append(f"vs baseline {name} ({base.get('date', '?')}): {passed_before}/{total_before} → "
                     f"{len(passing(result['criteria']))}/{total_now}{lost}; tokens {signed(diff['tokens_pct'])}; "
                     f"time {signed(diff['seconds_pct'])}; rerun: {'yes' if result['runs'] > 1 else 'no'}")
        reasons += [f"criterion lost: {name}/{criterion}" for criterion in diff["lost"]]
        if diff["tokens_over"]:
            reasons.append(f"tokens {signed(diff['tokens_pct'])} > 10%: {name}")
    regression = any(not reason.startswith("agent error") for reason in reasons)
    verdict = "regression" if regression else "error" if reasons else "ok"
    lines.append(f"verdict: {verdict}" + (f" ({'; '.join(reasons)})" if reasons else ""))
    return lines, reasons, regression


def load_baseline():
    if not BASELINE.is_file():
        return {}
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    except ValueError as error:
        raise SystemExit(f"qk-eval: {BASELINE} is not valid JSON: {error}")


def update_baseline(baseline, spec, results):
    """Merge every result without an agent error into baseline[spec]; return the names left out."""
    recorded = {name: {"date": time.strftime("%Y-%m-%d"),
                       "criteria": {c["name"]: c["passed"] for c in result["criteria"]},
                       "tokens": result["tokens"], "seconds": int(round(result["seconds"]))}
                for name, result in results.items() if not result["error"]}
    if recorded:
        baseline.setdefault(spec, {}).update(recorded)
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [name for name, result in results.items() if result["error"]]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="qk-eval", description=__doc__.splitlines()[0])
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--skill", help="run every case of this skill (or runner-review)")
    which.add_argument("--case", help="run one case by name")
    which.add_argument("--all", action="store_true", help="run every case")
    parser.add_argument("--runtime", required=True, help="runtime:model, e.g. codex: or claude:opus")
    parser.add_argument("--update-baseline", action="store_true",
                        help="after the comparison, record these results as the baseline for this runtime")
    parser.add_argument("--timeout", type=int, default=qk_run.DEFAULT_TIMEOUT, help="seconds per agent turn")
    args = parser.parse_args(argv)
    qk_run.parse_spec(args.runtime)
    cases, problem = select(args)
    if problem:
        print(f"qk-eval: {problem}", file=sys.stderr)
        return 2
    baseline = load_baseline()
    entries = baseline.get(args.runtime, {})
    started = time.strftime("%Y%m%d-%H%M%S")
    root = state_root() / f"{started}-{secrets.token_hex(2)}"
    root.mkdir(parents=True)
    results = {}
    for case in cases:
        result = run_case(case, args.runtime, args.timeout, root / case["name"] / "run-1", root)
        result["runs"] = 1
        base = entries.get(case["name"])
        if base is not None and compare(result, base)["flipped"]:
            result = run_case(case, args.runtime, args.timeout, root / case["name"] / "run-2", root)
            result["runs"] = 2
        results[case["name"]] = result
    lines, reasons, regression = report(args.runtime, results, entries)
    print("\n".join(lines))
    print(f"results: {root}")
    (root / "results.json").write_text(json.dumps(
        {"runtime": args.runtime, "started": started, "cases": results, "regression": regression},
        indent=2) + "\n", encoding="utf-8")
    if args.update_baseline:
        skipped = update_baseline(baseline, args.runtime, results)
        if skipped:
            print(f"baseline not updated for cases with an agent error: {', '.join(skipped)}")
            return 1
        print(f"baseline updated: {BASELINE}")
        return 0
    return 1 if reasons else 0


if __name__ == "__main__":
    sys.exit(main())
