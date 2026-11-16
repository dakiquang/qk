#!/usr/bin/env python3
"""Local evidence reads and read-only pull-request decision snapshots."""

import argparse
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone
import importlib
import json
from pathlib import Path
import re
import subprocess
import sys
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
    parser = argparse.ArgumentParser(usage="%(prog)s [-h] {show,stats,log,sync,brief,run,eval} ...")
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
    sync.add_argument("--backfill", action="store_true", help="first import stopped run states")
    brief = commands.add_parser("brief", help="summarize open/unknown PRs offline")
    brief.add_argument("--repo")
    commands.add_parser("run", help="existing runner (argv passed unchanged)")
    commands.add_parser("eval", help="existing evaluator (argv passed unchanged)")
    return parser


def _data(record):
    data = record.get("data", {})
    return data if isinstance(data, dict) else {}


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


def _snapshots(records):
    """Count a resumed run once, without hiding historical finding events."""
    latest = {("run", _run_key(record)): record for record in _latest_runs(records)}
    for record in records:
        kind = record.get("kind")
        if kind == "run":
            continue
        if kind == "decision":
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
            label = record.get("kind", "unknown")
        elif args.by == "task_kind":
            label = record.get("task_kind") or "unclassified"
        else:
            data = _data(record)
            label = (data.get("impl") if record.get("kind") == "run"
                     else data.get("runtime")) or "unclassified"
        if args.public:
            # Labels are unconstrained local inputs, even kind/runtime names.
            label = label if args.by == "kind" and label in {
                "run", "finding", "eval", "decision", "claim"} else "other"
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
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", sha):
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
    runs = _latest_runs(ledger.records())
    by_url = defaultdict(list)
    for run in runs:
        if _data(run).get("pr_url"):
            by_url[_data(run)["pr_url"]].append(run)
    written = 0
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
                ledger.append("decision", data, repo=run.get("repo", ""),
                              task_kind=run.get("task_kind", ""), refs=[run["id"]])
                written += 1
        except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
            print("qk sync: %s: %s" % (_text(url), _text(error)), file=sys.stderr)
            failures += 1
    print("Synced %d decision snapshots; %d failures." % (written, failures))
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


def _brief(args, records):
    runs = _latest_runs(records)
    decisions = [record for record in records if record.get("kind") == "decision"]
    shown = 0
    for run in runs:
        data = _data(run)
        url = data.get("pr_url")
        if not url or (args.repo and run.get("repo") != args.repo):
            continue
        matched = [decision for decision in decisions
                   if _data(decision).get("pr_url") == url
                   and (_data(decision).get("run_key") == _run_key(run)
                        or (not _data(decision).get("run_key")
                            and ((_data(decision).get("run_id") is not None
                                  and _data(decision).get("run_id") == data.get("run_id"))
                                 or run["id"] in decision.get("refs", []))))]
        snapshot = _data(matched[-1]) if matched else {}
        if snapshot.get("state") in {"MERGED", "CLOSED"}:
            continue
        shown += 1
        status = snapshot.get("state", "UNKNOWN")
        title = snapshot.get("title") or "PR title unknown"
        _brief_line("#%d %s: %s (%s)" % (shown, run.get("repo", ""), title, url),
                    "--id " + run["id"])
        _brief_line("  Done: run %s status=%s; impl=%s review=%s; PR=%s; synced=%s" % (
            _short_text(data.get("run_id", run["id"]), 24), data.get("status", "unknown"),
            _short_text(data.get("impl") or "unknown", 24),
            _short_text(data.get("review") or "unknown", 24), status,
            snapshot.get("checked_at") or "never / unknown"), "--id " + run["id"])
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
        kind = run.get("task_kind") or "unclassified"
        history = [item for item in runs if (item.get("task_kind") or "unclassified") == kind
                   and item.get("repo") == run.get("repo")]
        done = sum(_data(item).get("status") == "done" for item in history)
        _brief_line("  History: %s %d/%d done/total (informational)" % (kind, done, len(history)))
        print("  Decision: human decision required; sync state is a recorded observation, not approval.")
    if not shown:
        print("No open or unknown PRs recorded.")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"run", "eval"}:
        module = importlib.import_module("qk_" + argv[0])
        return module.main(argv[1:])
    args = _parser().parse_args(argv)
    try:
        ledger = importlib.import_module("qk_ledger")
        if args.command == "sync":
            return _sync(args, ledger)
        if args.command == "log":
            record = ledger.append("claim", {"about": args.about, "text": args.text}, refs=[args.about])
            print(_text("%s source=%s recorded_by=%s" % (
                record["id"], record["source"], record["recorded_by"])))
            return 0
        records = ledger.records()
        return {"show": _show, "stats": _stats, "brief": _brief}[args.command](args, records)
    except (OSError, ValueError, TypeError) as error:
        print("qk: %s" % _text(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
