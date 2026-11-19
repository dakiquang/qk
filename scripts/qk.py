#!/usr/bin/env python3
"""Local evidence reads, read-only PR snapshots and terminal-confirmed brief decisions."""

import argparse
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone
import importlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata
from urllib.parse import urlparse


PR_FIELDS = "url,title,state,mergedAt,closedAt,mergedBy,headRefOid"


def _text(value):
    text = str(value)
    return "".join("\\u%04x" % ord(char) if unicodedata.category(char).startswith("C")
                   or char in "\u2028\u2029" else char for char in text)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _date(value):
    if not isinstance(value, str) or not value:
        raise ValueError("missing timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed


def _since(value):
    match = re.fullmatch(r"(\d+)([smhdw])", value)
    if not match:
        raise argparse.ArgumentTypeError("use a duration such as 7d or 24h")
    try:
        seconds = int(match[1]) * {"s": 1, "m": 60, "h": 3600, "d": 86400,
                                   "w": 604800}[match[2]]
        return datetime.now(timezone.utc) - timedelta(seconds=seconds)
    except OverflowError as error:
        raise argparse.ArgumentTypeError("duration is too large") from error


def _parser():
    parser = argparse.ArgumentParser(usage="%(prog)s [-h] {show,stats,log,sync,brief,lesson,run,eval} ...")
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("show", help="read recorded evidence")
    show.add_argument("--kind")
    show.add_argument("--since", type=_since, metavar="7d")
    show.add_argument("--repo")
    show.add_argument("--id")
    show.add_argument("--json", action="store_true")
    stats = commands.add_parser("stats", help="aggregate recorded evidence")
    stats.add_argument("--task-kind")
    stats.add_argument("--by", choices=("kind", "task_kind", "runtime"), default="kind")
    stats.add_argument("--public", action="store_true", help="counts only; omit private labels")
    log = commands.add_parser("log", help="record a model claim")
    kinds = log.add_subparsers(dest="log_kind", required=True)
    claim = kinds.add_parser("claim", help="attach a claim to existing evidence")
    claim.add_argument("--about", required=True)
    claim.add_argument("--text", required=True)
    sync = commands.add_parser("sync", help="read PR state using gh; never change PRs")
    sync.add_argument("--backfill", action="store_true", help="first import stopped runs and saved eval attempts")
    brief = commands.add_parser("brief", help="summarize open/unknown PRs; on a terminal, ask per card")
    brief.add_argument("--repo")
    lesson = commands.add_parser("lesson", help="propose and decide evidence-backed lessons")
    lessons = lesson.add_subparsers(dest="lesson_command", required=True)
    suggest = lessons.add_parser("suggest", help="find repeated failures without writing")
    suggest.add_argument("--min", type=int, default=2, metavar="N")
    propose = lessons.add_parser("propose", help="propose an imperative rule with evidence")
    propose.add_argument("--class", dest="lesson_class", required=True, metavar="TEXT")
    propose.add_argument("--rule", required=True, metavar="TEXT",
                         help="caller-supplied imperative rule")
    propose.add_argument("--scope", action="append", required=True, metavar="SCOPE")
    propose.add_argument("--evidence", action="append", required=True, metavar="ID")
    propose.add_argument("--case", required=True, metavar="NAME")
    listing = lessons.add_parser("list", help="show the latest state of each lesson")
    listing.add_argument("--status", choices=("proposed", "active", "dismissed", "retired", "promoted"), metavar="S")
    listing.add_argument("--json", action="store_true")
    measure = lessons.add_parser("measure", help="run the lesson's case with and without it; record the result")
    measure.add_argument("id", metavar="ID")
    measure.add_argument("--runtime", required=True, help="runtime:model, e.g. codex:gpt-6.1-sol")
    measure.add_argument("--timeout", type=int, help="seconds per agent turn (default: the runner's)")
    decide = lessons.add_parser("decide", help="record a lesson status decision")
    decide.add_argument("id", metavar="ID")
    decide.add_argument("status", choices=("active", "dismissed", "retired", "promoted"), metavar="STATUS")
    decide.add_argument("--reason", metavar="TEXT")
    commands.add_parser("run", help="existing runner (argv passed unchanged)")
    commands.add_parser("eval", help="existing evaluator (argv passed unchanged)")
    return parser


def _data(record):
    data = record.get("data", {})
    return data if isinstance(data, dict) else {}


def _lesson_suggest(args, records):
    if args.min < 1:
        raise ValueError("--min must be at least 1")
    candidates = defaultdict(list)
    for record in records:
        data = _data(record)
        if record["kind"] == "eval":
            case = data.get("case")
            criteria = data.get("criteria")
            if (not isinstance(case, str) or not case.strip()
                    or not isinstance(criteria, list)):
                continue
            # Count each criterion at most once per eval record.
            failed = {item["name"] for item in criteria
                      if isinstance(item, dict) and item.get("passed") is False
                      and isinstance(item.get("name"), str) and item["name"].strip()}
            for criterion in sorted(failed):
                candidates[("eval", case, criterion)].append(record["id"])
        elif record["kind"] == "finding":
            label = data.get("class")
            if isinstance(label, str) and label.strip():
                candidates[("finding", label)].append(record["id"])
    shown = 0
    for candidate, ids in sorted(candidates.items()):
        if len(ids) >= args.min:
            print("%s\tids=%s" % ("\t".join(_text(value) for value in candidate), ",".join(ids)))
            shown += 1
    if not shown:
        print("No repeated failures in the ledger (need >= %d)." % args.min)
    return 0


def _lesson(args, ledger):
    if args.lesson_command == "propose":
        data = {"status": "proposed", "class": args.lesson_class, "rule": args.rule,
                "scope": args.scope, "evidence": args.evidence, "case": args.case,
                "measured": []}
        print(ledger.append("lesson", data, source="model")["id"])
        return 0
    if args.lesson_command == "measure":
        evaluator = importlib.import_module("qk_eval")
        return evaluator.measure_lesson(args.id, args.runtime,
                                        args.timeout or evaluator.qk_run.DEFAULT_TIMEOUT)
    if args.lesson_command == "decide":
        data = {"lesson_id": args.id, "status": args.status}
        if args.reason is not None:
            data["reason"] = args.reason
        print(ledger.append("lesson", data, source="user")["id"])
        return 0
    records = ledger.records()
    if args.lesson_command == "suggest":
        return _lesson_suggest(args, records)
    rows = []
    for record in ledger.latest_lessons(records):
        data = record["data"]
        if args.status and data["status"] != args.status:
            continue
        rows.append({"id": data["lesson_id"], "status": data["status"],
                     "case": data["case"], "scope": data["scope"],
                     "evidence_count": len(data["evidence"]),
                     "measured_count": len(data["measured"]),
                     "needs_measure": data["status"] == "proposed" and not data["measured"],
                     "needs_remeasure": data["status"] == "active" and not ledger.measured_helps(data)})
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=True))
    else:
        for row in rows:
            print(_text("{id} {status} case={case} scope={scope} evidence={evidence_count} "
                        "measured={measured_count}{marker}".format(
                            **row, marker=" needs-measure" if row["needs_measure"] else
                            " needs-remeasure" if row["needs_remeasure"] else "")))
    return 0


def _run_key(record):
    return _data(record).get("run_key") or record["id"]


def _latest_runs(records):
    latest = {}
    for record in records:
        if record.get("kind") != "run":
            continue
        previous = latest.get(_run_key(record))
        # Legacy snapshots are revision zero; arrival order cannot supersede a resume.
        if previous is None or _data(record).get("source_revision", 0) >= _data(previous).get("source_revision", 0):
            latest[_run_key(record)] = record
    return list(latest.values())


def _decision_key(record):
    data = _data(record)
    return (data.get("run_key") or data.get("run_id"), data.get("pr_url"))


def _user_decision(record):
    """Human choices are events; they never stand in for a sync snapshot."""
    return record.get("kind") == "decision" and record.get("source") == "user"


def _snapshots(records):
    """Count a resumed run once, without hiding historical finding events."""
    latest = {("run", _run_key(record)): record for record in _latest_runs(records)}
    for record in records:
        kind = record.get("kind")
        if kind == "run":
            continue
        if _user_decision(record):
            key = ("user_decision", record["id"])
        elif kind == "decision":
            key = (kind, _decision_key(record))
        else:
            key = (kind, record["id"])
        latest[key] = record
    return list(latest.values())


def _show(args, records):
    selected = [record for record in records
                if (not args.kind or record.get("kind") == args.kind)
                and (not args.repo or record.get("repo") == args.repo)
                and (not args.id or record.get("id") == args.id)]
    if args.since:
        selected = [record for record in selected if _date(record.get("at")) >= args.since]
    if args.json:
        print(json.dumps(selected, indent=2, ensure_ascii=True))
    else:
        for record in selected:
            print(_text("{id} {at} {kind} source={source} recorded_by={recorder} repo={repo} "
                        "task_kind={task} {data}".format(
                            id=record["id"], at=record.get("at", "unknown"),
                            kind=record.get("kind", "unknown"), source=record.get("source", "unknown"),
                            recorder=record.get("recorded_by", "unknown"), repo=record.get("repo", ""),
                            task=record.get("task_kind") or "unclassified",
                            data=json.dumps(_data(record), ensure_ascii=True, sort_keys=True))))
    return 0


def _stats(args, records):
    selected = [record for record in _snapshots(records)
                if args.task_kind is None or (record.get("task_kind") or "unclassified") == args.task_kind]
    counts = Counter()
    for record in selected:
        if args.by == "kind":
            label = "user_decision" if _user_decision(record) else record.get("kind", "unknown")
        elif args.by == "task_kind":
            label = record.get("task_kind") or "unclassified"
        else:
            data = _data(record)
            label = (data.get("impl") if record.get("kind") == "run"
                     else data.get("runtime")) or "unclassified"
        if args.public:
            # Labels are unconstrained local inputs, even kind/runtime names.
            label = label if args.by == "kind" and label in {
                "run", "finding", "eval", "decision", "user_decision", "claim"} else "other"
        counts[label] += 1
    print("total\t%d" % len(selected))
    for label, count in sorted(counts.items()):
        print("%s\t%d" % (_text(label), count))
    return 0


def _backfill(ledger):
    runner = importlib.import_module("qk_run")
    root = Path(runner.state_root())
    failures = 0
    for state_file in sorted(root.glob("*/state.json")):
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                raise ValueError("state must be an object")
            if state.get("stage") in {"done", "blocked", "aborted"}:
                ledger.record_run(state, state_file.parent)
        except (OSError, ValueError, TypeError) as error:
            print("qk sync: backfill %s: %s" % (_text(state_file), _text(error)), file=sys.stderr)
            failures += 1
    evaluator = importlib.import_module("qk_eval")
    for directory in sorted(Path(evaluator.state_root()).glob("*")):
        if not directory.is_dir():
            continue
        results_file = directory / "results.json"
        try:
            results = json.loads(results_file.read_text(encoding="utf-8"))
            if (not isinstance(results, dict) or not isinstance(results.get("runtime"), str)
                    or not results["runtime"].strip() or not isinstance(results.get("cases"), dict)):
                raise ValueError("eval results require a runtime and cases object")
            attempts = []
            for case, result in results["cases"].items():
                if not case or Path(case).name != case or case in {".", ".."}:
                    raise ValueError("invalid eval case name")
                if not isinstance(result, dict):
                    raise ValueError("eval case result must be an object")
                runs = result.get("runs", 1)
                if type(runs) is not int or runs not in (1, 2):
                    raise ValueError("eval case runs must be 1 or 2")
                for index in range(1, runs + 1):
                    attempt = directory / case / ("run-%d" % index)
                    if index == runs:
                        observed = result
                    else:
                        # results.json retains only the final attempt; earlier grades survive on disk.
                        criteria = json.loads((attempt / "check.json").read_text(encoding="utf-8"))
                        observed = {"criteria": criteria, "tokens": None, "seconds": None}
                    attempts.append((case, observed, attempt))
            for case, observed, attempt in attempts:
                ledger.record_eval(results["runtime"], case, observed, attempt, results.get("kit"))
        except (OSError, ValueError, TypeError) as error:
            print("qk sync: backfill %s: %s" % (_text(results_file), _text(error)), file=sys.stderr)
            failures += 1
    return failures


def _pr_url(value):
    if not isinstance(value, str):
        raise ValueError("PR URL must be a string")
    parsed = urlparse(value)
    if (parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password
            or parsed.query or parsed.fragment
            or not re.fullmatch(r"/[^/\s]+/[^/\s]+/pull/[1-9]\d*/?", parsed.path)
            or any(unicodedata.category(char).startswith("C") for char in value)):
        raise ValueError("invalid PR URL")
    return value.rstrip("/")


def _head_sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", value) is not None


def _remote_snapshot(payload, expected_url):
    if not isinstance(payload, dict) or any(key not in payload for key in PR_FIELDS.split(",")):
        raise ValueError("incomplete PR response")
    if _pr_url(payload["url"]) != _pr_url(expected_url):
        raise ValueError("PR response URL does not match requested PR")
    state = payload["state"]
    if state not in ("OPEN", "CLOSED", "MERGED"):
        raise ValueError("invalid PR state")
    if not isinstance(payload["title"], str) or not payload["title"].strip():
        raise ValueError("invalid PR title")
    sha = payload["headRefOid"]
    if not _head_sha(sha):
        raise ValueError("invalid PR head SHA")
    for key in ("mergedAt", "closedAt"):
        if payload[key] is not None:
            _date(payload[key])
    merger = payload["mergedBy"]
    if merger is not None and (not isinstance(merger, dict)
                               or not isinstance(merger.get("login"), str)
                               or not merger["login"].strip()):
        raise ValueError("invalid PR merger")
    if state == "MERGED" and not payload["mergedAt"]:
        raise ValueError("merged PR is missing mergedAt")
    if state == "CLOSED" and (not payload["closedAt"] or payload["mergedAt"] is not None
                              or merger is not None):
        raise ValueError("inconsistent closed PR timestamps")
    if state == "OPEN" and (payload["mergedAt"] is not None or payload["closedAt"] is not None
                            or merger is not None):
        raise ValueError("inconsistent open PR metadata")
    return {"pr_url": payload["url"], "state": state, "title": payload["title"],
            "head_sha": sha, "merged_by": merger["login"] if merger else None,
            "merged_at": payload["mergedAt"], "closed_at": payload["closedAt"],
            "checked_at": _now()}


def _sync(args, ledger):
    failures = _backfill(ledger) if args.backfill else 0
    records = ledger.records()
    runs = _latest_runs(records)
    decisions = {_decision_key(record): _data(record) for record in records
                 if record.get("kind") == "decision" and not _user_decision(record)}
    by_url = defaultdict(list)
    for run in runs:
        if _data(run).get("pr_url"):
            by_url[_data(run)["pr_url"]].append(run)
    written = unchanged = 0
    for url, linked_runs in by_url.items():
        try:
            _pr_url(url)
            cwd = None
            for run in linked_runs:
                repo_path = _data(run).get("repo_path")
                if isinstance(repo_path, str) and Path(repo_path).is_dir():
                    cwd = repo_path
                    break
            reply = subprocess.run(["gh", "pr", "view", url, "--json", PR_FIELDS],
                                   cwd=cwd, capture_output=True, text=True, timeout=60)
            if reply.returncode:
                raise ValueError("gh exited %d: %s" % (reply.returncode, reply.stderr.strip()))
            snapshot = _remote_snapshot(json.loads(reply.stdout), url)
            for run in linked_runs:
                data = dict(snapshot, run_id=_data(run).get("run_id"), run_key=_run_key(run))
                previous = decisions.get((_run_key(run), snapshot["pr_url"]))
                if previous is not None and all(key in previous and previous[key] == value
                                                for key, value in snapshot.items() if key != "checked_at"):
                    unchanged += 1
                    continue
                ledger.append("decision", data, repo=run.get("repo", ""),
                              task_kind=run.get("task_kind", ""), refs=[run["id"]])
                written += 1
        except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
            print("qk sync: %s: %s" % (_text(url), _text(error)), file=sys.stderr)
            failures += 1
    print("Decision snapshots: %d recorded; %d unchanged; %d failures." % (written, unchanged, failures))
    return 1 if failures else 0


def _related_claims(run, records):
    """Follow evidence links within one run; claims never bridge other evidence."""
    key = _run_key(run)
    evidence = {}
    related = set()
    for record in records:
        kind = record.get("kind")
        if kind == "run":
            if _run_key(record) != key:
                continue
            related.add(record["id"])
        elif kind in {"finding", "eval"}:
            owner = _data(record).get("run_key")
            if owner and owner != key:
                continue
            if owner == key:
                related.add(record["id"])
        elif kind == "decision":
            data = _data(record)
            owner = data.get("run_key")
            if (owner == key or (not owner and (
                    (data.get("run_id") is not None
                     and data.get("run_id") == _data(run).get("run_id"))
                    or run["id"] in record.get("refs", [])))):
                related.add(record["id"])
            continue
        else:
            continue
        evidence[record["id"]] = record

    edges = defaultdict(set)
    for record in evidence.values():
        for ref in record.get("refs", []):
            if ref in evidence:
                edges[record["id"]].add(ref)
                edges[ref].add(record["id"])
    for record in records:
        about = _data(record).get("about")
        if record.get("kind") == "claim" and isinstance(about, str):
            edges[about].add(record["id"])

    queue = deque(related)
    while queue:
        for linked in edges[queue.popleft()] - related:
            related.add(linked)
            queue.append(linked)
    return [record for record in records
            if record["id"] in related and record.get("kind") == "claim"]


def _short_text(value, limit):
    text = _text(value)
    return text if len(text) <= limit else text[:limit - 3] + "..."


def _brief_line(text, details="", limit=240):
    suffix = "; full: qk show " + _text(details) if details else ""
    print(_short_text(text, limit - len(suffix)) + suffix)


def _verify_summary(verifies):
    if not verifies:
        return "missing verify evidence"
    passed = failed = 0
    for item in verifies:
        exit_code = item.get("exit") if isinstance(item, dict) else None
        if type(exit_code) is int:
            if exit_code == 0:
                passed += 1
            else:
                failed += 1
    return "%d checks (exit=0:%d nonzero:%d unknown:%d)" % (
        len(verifies), passed, failed, len(verifies) - passed - failed)


# Sensitive repo-relative paths, matched case-insensitively.
BRIEF_SENSITIVE_FILES = re.compile(
    r"^\.github/|(?:^|/)(?:package\.json|package-lock\.json|yarn\.lock|pnpm-lock\.yaml|"
    r"composer\.json|composer\.lock|pyproject\.toml|poetry\.lock|pipfile|pipfile\.lock|"
    r"go\.mod|go\.sum|cargo\.toml|cargo\.lock|gemfile|gemfile\.lock|dockerfile|"
    r"requirements[^/]*\.txt|[^/]*\.lock)$|\.tf$|(?:^|/)migrations(?:/|$)|auth|secret|permission|policy",
    re.IGNORECASE)


def _blocked_reason(run):
    """First line of why a run stopped, read from its local state.json; the ledger keeps no reason text."""
    for ref in run.get("refs", []):
        if not ref.endswith("state.json"):
            continue
        try:
            reason = json.loads(Path(ref).read_text(encoding="utf-8")).get("reason")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(reason, str) and reason.strip():
            return reason.strip().splitlines()[0]
    return "reason unknown"


def _brief_risk(data, snapshot, reason="reason unknown"):
    if data.get("status") == "blocked":
        return "high", "blocked at %s: %s" % (data.get("blocked_at") or "unknown", reason)
    remaining = data.get("remaining_count") or 0
    if remaining > 0:
        return "high", "%d findings remain" % remaining
    failed = sum(isinstance(item, dict) and type(item.get("exit")) is int and item["exit"] != 0
                 for item in data.get("verify_results") or [])
    if failed:
        return "high", "verify failed (%d nonzero)" % failed
    files = data.get("changed_files")
    sensitive = [path for path in files or [] if BRIEF_SENSITIVE_FILES.search(path)]
    if sensitive:
        return "high", "sensitive file " + sensitive[0] + (
            " +%d more" % (len(sensitive) - 1) if len(sensitive) > 1 else "")
    if data.get("fix_rounds", 0) > 0:
        return "medium", "fix round used"
    if files is not None:
        lines = (data.get("lines_added") or 0) + (data.get("lines_deleted") or 0)
        if lines > 300:
            return "medium", "%d lines changed" % lines
        if len(files) > 10:
            return "medium", "%d files changed" % len(files)
    if data.get("commit") and snapshot.get("head_sha") and data["commit"] != snapshot["head_sha"]:
        return "medium", "PR head differs from recorded commit"
    if not snapshot:
        return "medium", "never synced"
    if files is None:
        return "medium", "scope unknown"
    return "low", "no rule matched"


def _gh(argv, timeout):
    """Run one gh command without a checkout cwd; the PR URL or owner/repo selects the repository."""
    reply = subprocess.run(["gh"] + argv, capture_output=True, text=True, timeout=timeout)
    if reply.returncode:
        raise ValueError("gh exited %d: %s" % (reply.returncode, reply.stderr.strip()))
    return reply.stdout


MERGE_METHODS = (("squash", "squashMergeAllowed"), ("merge", "mergeCommitAllowed"),
                 ("rebase", "rebaseMergeAllowed"))


def _merge(url, commit):
    """Merge only the recorded commit; return (ok, head, reason). EOF at the method prompt propagates."""
    head = None
    try:
        url = _pr_url(url)
        if not commit:
            return False, None, "run has no recorded commit"
        payload = json.loads(_gh(["pr", "view", url, "--json", "headRefOid"], 60))
        head = payload.get("headRefOid") if isinstance(payload, dict) else None
        if not _head_sha(head):
            raise ValueError("invalid PR head SHA")
        if head != commit:
            return False, head, "PR head %s differs from recorded commit %s" % (head, commit)
        parsed = urlparse(url)
        owner, name = parsed.path.split("/")[1:3]
        # HOST/OWNER/REPO keeps the lookup on the PR's own host (GitHub Enterprise included).
        settings = json.loads(_gh(["repo", "view", "/".join((parsed.netloc, owner, name)), "--json",
                                   ",".join(field for _, field in MERGE_METHODS)], 60))
        if not isinstance(settings, dict) or any(type(settings.get(field)) is not bool for _, field in MERGE_METHODS):
            raise ValueError("invalid repository response")
        methods = [method for method, field in MERGE_METHODS if settings.get(field) is True]
        if not methods:
            return False, head, "repository allows no merge method"
        method = methods[0]
        if len(methods) > 1:
            method = input("Merge method [%s]: " % "/".join(methods)).strip().lower()
            if method not in methods:
                return False, head, "merge method must be one of " + ", ".join(methods)
        _gh(["pr", "merge", url, "--" + method, "--match-head-commit", commit], 120)
        return True, head, ""
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        return False, head, str(error)


def _ask(run, snapshot, blocked, ledger):
    """Ask about one card; return False at end of input. Only complete choices are recorded."""
    shown_at = time.monotonic()
    data = _data(run)
    if blocked:
        prompt, choices = "[a] abort later  [r] resume later  [s] skip: ", {
            "a": "abort-later", "r": "resume-later"}
    else:
        prompt, choices = "[y] merge  [n] leave  [d] diff  [s] skip: ", {"n": "leave"}
    while True:
        try:
            answer = input(prompt).strip().lower()
            decided_at, elapsed = _now(), round(time.monotonic() - shown_at, 3)
            if answer == "s":
                return True
            head = snapshot.get("head_sha")
            if not blocked and answer == "d":
                try:
                    diff = _gh(["pr", "diff", _pr_url(data.get("pr_url"))], 60)
                except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
                    print("qk brief: diff unavailable: %s" % _text(error), file=sys.stderr)
                    continue
                for line in diff.splitlines():
                    print(_text(line.expandtabs()))
                continue
            if not blocked and answer == "y":
                merged, head, reason = _merge(data.get("pr_url"), data.get("commit"))
                if not merged:
                    print("qk brief: not merged: %s" % _text(reason), file=sys.stderr)
                    continue
                choice = "merge"
            elif answer in choices:
                choice = choices[answer]
            else:
                continue
        except EOFError:
            print()
            return False
        record = ledger.append("decision", {
            "choice": choice, "pr_url": data.get("pr_url") or None, "run_key": _run_key(run),
            "run_id": data.get("run_id"), "head": head, "decided_at": decided_at,
            "elapsed_s": elapsed},
            repo=run.get("repo", ""), task_kind=run.get("task_kind", ""), refs=[run["id"]], source="user")
        print(_text("Recorded %s: %s" % (choice, record["id"])))
        return True


def _print_card(shown, run, snapshot, level, rule, runs, records):
    data = _data(run)
    blocked = data.get("status") == "blocked"
    status = snapshot.get("state", "UNKNOWN")
    title = snapshot.get("title") or data.get("task") or "PR title unknown"
    prefix = "#%d %s: " % (shown, run.get("repo", ""))
    tail = " (%s)  RISK: %s — %s" % (
        data.get("pr_url") or "no PR", level, _short_text(rule, 100))
    title_limit = max(3, 240 - len(_text(prefix + tail)) - len("; full: qk show --id " + run["id"]))
    _brief_line(prefix + _short_text(title, title_limit) + tail, "--id " + run["id"])
    scope = "scope unknown" if "changed_files" not in data else "%d files, +%s/-%s" % (
        len(data["changed_files"]), data.get("lines_added", 0), data.get("lines_deleted", 0))
    done_line = "  Done: run %s status=%s; %s; impl=%s review=%s" % (
        _short_text(data.get("run_id", run["id"]), 24), data.get("status", "unknown"), scope,
        _short_text(data.get("impl") or "unknown", 24),
        _short_text(data.get("review") or "unknown", 24))
    if not blocked:
        done_line += "; PR=%s; synced=%s" % (status, snapshot.get("checked_at") or "never / unknown")
    _brief_line(done_line, "--id " + run["id"])
    kind = run.get("task_kind") or "unclassified"
    history = [item for item in runs if (item.get("task_kind") or "unclassified") == kind
               and item.get("repo") == run.get("repo")]
    done = sum(_data(item).get("status") == "done" for item in history)
    history_line = "  History: %s %d/%d done/total (informational)" % (kind, done, len(history))
    if blocked:
        _brief_line("  Next: qk run resume %s after fixing the cause, or qk run abort %s" % (
            data.get("run_id", run["id"]), data.get("run_id", run["id"])), "--id " + run["id"])
        _brief_line(history_line)
        return
    commit, head = data.get("commit"), snapshot.get("head_sha")
    if not commit or not head:
        freshness = "UNKNOWN commit comparison / not verified"
    elif commit != head:
        freshness = "STALE / not verified (recorded %s; PR head %s)" % (commit, head)
    else:
        freshness = "recorded commit %s (matches last synced head)" % commit
    verifies = data.get("verify_results") or []
    remaining = data.get("remaining_count")
    addressed = data.get("addressed_count")
    review = "remaining=%s, queued-for-fix=%s" % (
        remaining if remaining is not None else "unknown",
        addressed if addressed is not None else "unknown")
    _brief_line("  Evidence: verify: %s; review: %s; %s" % (
        _verify_summary(verifies), review, freshness), "--id " + run["id"], limit=320)
    claims = _related_claims(run, records)
    claim_text = "no recorded model claims"
    if claims:
        claim = claims[0]
        claim_text = "%d total; preview only: %s [source=%s recorded_by=%s]: %s" % (
            len(claims), claim["id"], claim.get("source", "unknown"),
            claim.get("recorded_by", "unknown"), _short_text(_data(claim).get("text", ""), 40))
    _brief_line("  Unchecked: remaining findings=%s; claims (not independent verification): %s" % (
        remaining if remaining is not None else "unknown", claim_text),
        "--kind claim" if claims else "")
    _brief_line(history_line)
    _brief_line("  Decision: human decision required; sync state is a recorded observation, not approval.")


def _brief(args, records, ledger):
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    runs = _latest_runs(records)
    decisions = [record for record in records
                 if record.get("kind") == "decision" and not _user_decision(record)]
    cards = []
    for run in runs:
        data = _data(run)
        url = data.get("pr_url")
        if (data.get("status") == "aborted" or (not url and data.get("status") != "blocked")
                or (args.repo and run.get("repo") != args.repo)):
            continue
        matched = [decision for decision in decisions
                   if _data(decision).get("pr_url") == url
                   and (_data(decision).get("run_key") == _run_key(run)
                        or (not _data(decision).get("run_key")
                            and ((_data(decision).get("run_id") is not None
                                  and _data(decision).get("run_id") == data.get("run_id"))
                                 or run["id"] in decision.get("refs", []))))]
        snapshot = _data(matched[-1]) if matched else {}
        if data.get("status") != "blocked" and snapshot.get("state") in {"MERGED", "CLOSED"}:
            continue
        reason = _blocked_reason(run) if data.get("status") == "blocked" else "reason unknown"
        level, rule = _brief_risk(data, snapshot, reason)
        cards.append((run, snapshot, level, rule))
    cards.sort(key=lambda card: ({"high": 0, "medium": 1, "low": 2}[card[2]],
                                 _data(card[0]).get("status") != "blocked"))
    for shown, (run, snapshot, level, rule) in enumerate(cards, 1):
        _print_card(shown, run, snapshot, level, rule, runs, records)
        if interactive:
            interactive = _ask(run, snapshot, _data(run).get("status") == "blocked", ledger)
    if not cards:
        print("No open, unknown or blocked runs recorded.")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"run", "eval"}:
        module = importlib.import_module("qk_" + argv[0])
        return module.main(argv[1:])
    args = _parser().parse_args(argv)
    try:
        ledger = importlib.import_module("qk_ledger")
        if args.command == "lesson":
            return _lesson(args, ledger)
        if args.command == "sync":
            return _sync(args, ledger)
        if args.command == "log":
            record = ledger.append("claim", {"about": args.about, "text": args.text}, refs=[args.about])
            print(_text("%s source=%s recorded_by=%s" % (
                record["id"], record["source"], record["recorded_by"])))
            return 0
        records = ledger.records()
        if args.command == "brief":
            return _brief(args, records, ledger)
        return {"show": _show, "stats": _stats}[args.command](args, records)
    except (OSError, ValueError, TypeError) as error:
        print("qk: %s" % _text(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
