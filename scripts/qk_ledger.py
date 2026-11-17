#!/usr/bin/env python3
"""Append-only local evidence, not a tamper-proof or authorization boundary.

Writers and readers share a side-file lock. A failed append may leave a torn
last line: subsequent operations fail explicitly rather than deleting evidence.
Like claims, lesson source labels are an interface boundary, not proof of who
ran the command.
"""
import hashlib
import json
import math
import os
import re
import secrets
import stat
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

STORE_NAME = "ledger.jsonl"
LOCK_NAME = "ledger.lock"
MAX_CLAIM_TEXT = 1000
LESSON_FIELDS = ("class", "rule", "scope", "evidence", "case", "measured")
LESSON_STATUSES = ("proposed", "active", "dismissed", "retired", "promoted")


def state_dir() -> Path:
    base = os.environ.get("QK_STATE_DIR")
    if base:
        return Path(base).expanduser()
    xdg = os.environ.get("XDG_STATE_HOME")
    return (Path(xdg).expanduser() if xdg else Path.home() / ".local" / "state") / "qk"


def store_path() -> Path:
    return state_dir() / STORE_NAME


def _outside_repository(directory: Path) -> None:
    for parent in (directory,) + tuple(directory.parents):
        if (parent / ".git").exists() or (parent / ".git").is_symlink():
            raise ValueError("qk state directory must be outside Git repositories")
        if ((parent / "HEAD").is_file() and (parent / "objects").is_dir()
                and (parent / "refs").is_dir()):
            raise ValueError("qk state directory must be outside bare Git repositories")


def _open_private(path: Path, flags: int) -> int:
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(str(path), flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("ledger files must be regular files")
        os.fchmod(fd, 0o600)
    except BaseException:
        os.close(fd)
        raise
    return fd


@contextmanager
def _locked(exclusive: bool) -> Iterator[Path]:
    try:
        import fcntl
    except ImportError as error:
        raise RuntimeError("qk ledger requires filesystem locking support") from error
    directory = state_dir().resolve()
    _outside_repository(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = _open_private(directory / LOCK_NAME, os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield directory
    finally:
        os.close(fd)


def _text(value: object, name: str, *, empty: bool = True) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError(f"{name} must be {'a nonempty string' if not empty else 'a string'}")
    return value


def _validate_record(record: object) -> dict:
    if not isinstance(record, dict):
        raise ValueError("record must be an object")
    if type(record.get("v")) is not int or record["v"] != 1:
        raise ValueError("unsupported ledger version")
    for field in ("id", "kind", "at", "source", "recorded_by"):
        _text(record.get(field), field, empty=False)
    for field in ("repo", "task_kind"):
        _text(record.get(field), field)
    refs = record.get("refs")
    if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
        raise ValueError("refs must be a list of strings")
    if not isinstance(record.get("data"), dict):
        raise ValueError("data must be an object")
    if "key" in record:
        _text(record["key"], "key", empty=False)
    return record


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON number {value}")


def _unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field {key}")
        result[key] = value
    return result


def _read_records(directory: Path) -> list:
    path = directory / STORE_NAME
    try:
        fd = _open_private(path, os.O_RDONLY)
    except FileNotFoundError:
        return []
    result = []
    ids = set()
    keys = set()
    with os.fdopen(fd, "rb") as handle:
        for number, raw in enumerate(handle, 1):
            try:
                if not raw.endswith(b"\n"):
                    raise ValueError("torn record (missing newline)")
                record = _validate_record(json.loads(
                    raw.decode("utf-8"), parse_constant=_reject_constant,
                    object_pairs_hook=_unique_object,
                ))
                if record["id"] in ids:
                    raise ValueError("duplicate record id")
                if "key" in record and record["key"] in keys:
                    raise ValueError("duplicate idempotency key")
                ids.add(record["id"])
                if "key" in record:
                    keys.add(record["key"])
                result.append(record)
            except (ValueError, UnicodeError) as error:
                raise ValueError(f"invalid ledger {path}, line {number}: {error}") from error
    return result


def records() -> list:
    """Read complete records under the writer's lock; never skip damaged lines."""
    with _locked(False) as directory:
        return _read_records(directory)


def _claim(data: dict, existing: list) -> dict:
    if set(data) != {"about", "text"}:
        raise ValueError("claim requires only about and text")
    about = _text(data["about"], "about", empty=False)
    text = _text(data["text"], "text", empty=False)
    if len(text) > MAX_CLAIM_TEXT or any(
        unicodedata.category(char).startswith("C") or char in "\n\r\u2028\u2029"
        for char in text
    ):
        raise ValueError(f"claim text must be a single line of at most {MAX_CLAIM_TEXT} characters")
    for record in existing:
        if record["id"] == about:
            return record
    raise ValueError(f"claim refers to missing record {about}")


def latest_lessons(existing: list) -> list:
    """Select lesson states by ledger order, retaining the proposal identity."""
    latest = {}
    for record in existing:
        if record["kind"] == "lesson":
            latest[record["data"]["lesson_id"]] = record
    return list(latest.values())


def _lesson_line(value: object, name: str, limit: int) -> str:
    value = _text(value, name, empty=False)
    if len(value) > limit or any(
        unicodedata.category(char).startswith("C") or char in "\n\r\u2028\u2029"
        for char in value
    ):
        raise ValueError(f"{name} must be a single line of at most {limit} characters")
    return value


def _lesson(data: dict, existing: list, identifier: str) -> dict:
    if data.get("status") == "proposed":
        if set(data) - {"lesson_id"} != {"status", *LESSON_FIELDS}:
            raise ValueError("lesson proposal requires status, class, rule, scope, evidence, case and measured")
        if data.get("lesson_id", identifier) != identifier:
            raise ValueError("lesson proposal id must equal its record id")
        _lesson_line(data["class"], "class", 200)
        _lesson_line(data["rule"], "rule", 300)
        scope = data["scope"]
        if (not isinstance(scope, list) or not 1 <= len(scope) <= 3
                or any(not isinstance(item, str) or not re.fullmatch(
                    r"stage:(?:review|impl|plan)|repo:[A-Za-z0-9][A-Za-z0-9._-]*", item)
                       for item in scope)
                or not any(item.startswith("stage:") for item in scope)):
            raise ValueError("scope requires 1-3 safe stage/repo strings and at least one stage")
        evidence = data["evidence"]
        if (not isinstance(evidence, list) or any(not isinstance(item, str) for item in evidence)
                or len(evidence) < 2 or len(set(evidence)) != len(evidence)):
            raise ValueError("evidence requires at least 2 distinct eval or finding ids")
        by_id = {record["id"]: record for record in existing}
        for item in evidence:
            if item not in by_id:
                raise ValueError(f"evidence refers to missing record {item}")
            if by_id[item]["kind"] not in ("eval", "finding"):
                raise ValueError(f"evidence {item} must be an eval or finding record")
        case = _text(data["case"], "case", empty=False)
        cases = Path(__file__).resolve().parents[1] / "evals" / "cases"
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", case):
            raise ValueError("case must be a directory name under evals/cases")
        target = (cases / case).resolve()
        if target.parent != cases.resolve() or not target.is_dir():
            raise ValueError("case must be an existing directory under evals/cases")
        if data["measured"] != []:
            raise ValueError("lesson proposals require an empty measured list")
        return dict(data, lesson_id=identifier)
    if (set(data) - {"reason"} != {"lesson_id", "status"}
            or data.get("status") not in LESSON_STATUSES[1:]):
        raise ValueError("lesson decision requires lesson_id, status (active/dismissed/retired/promoted), and optional reason")
    lesson_id = _text(data["lesson_id"], "lesson_id", empty=False)
    if "reason" in data:
        _lesson_line(data["reason"], "reason", 300)
    previous = next((record["data"] for record in latest_lessons(existing)
                     if record["data"]["lesson_id"] == lesson_id), None)
    if previous is None:
        raise ValueError(f"missing lesson {lesson_id}")
    old, new = previous["status"], data["status"]
    if new not in {"proposed": ("dismissed", "active"),
                  "active": ("retired", "promoted")}.get(old, ()):
        raise ValueError(f"invalid lesson transition: {old} -> {new}")
    if (new == "active"
            and (not isinstance(previous["measured"], list) or not previous["measured"])):
        raise ValueError("measure the lesson before activating it")
    return dict({field: previous[field] for field in LESSON_FIELDS}, **data)


def append(kind: str, data: dict, *, repo: str = "", task_kind: str = "",
           refs: tuple = (), key: Optional[str] = None,
           source: Optional[str] = None) -> dict:
    """Append durably; key lookup and claim/lesson validation share one lock."""
    _text(kind, "kind", empty=False)
    _text(repo, "repo")
    _text(task_kind, "task_kind")
    if source is not None and (kind != "lesson" or source not in ("model", "user")):
        raise ValueError("explicit source is only supported for lessons (model or user)")
    if not isinstance(data, dict):
        raise ValueError("data must be an object")
    if not isinstance(refs, (tuple, list)) or any(not isinstance(ref, str) for ref in refs):
        raise ValueError("refs must be a sequence of strings")
    if key is not None:
        _text(key, "key", empty=False)
    # Snapshot caller-owned mutable input and reject non-JSON/NaN before touching disk.
    try:
        data = json.loads(json.dumps(data, allow_nan=False, ensure_ascii=False))
    except (TypeError, ValueError) as error:
        raise ValueError(f"data must contain valid JSON: {error}") from error
    with _locked(True) as directory:
        existing = _read_records(directory)
        if kind == "claim":
            parent = _claim(data, existing)
            repo, task_kind = parent["repo"], parent["task_kind"]
        ids = {record["id"] for record in existing}
        identifier = secrets.token_hex(6)
        while identifier in ids:
            identifier = secrets.token_hex(6)
        if key is not None:
            for record in existing:
                if record.get("key") == key:
                    if record["kind"] != kind:
                        raise ValueError("idempotency key belongs to another record kind")
                    fd = _open_private(directory / STORE_NAME, os.O_WRONLY)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                    fd = os.open(str(directory), os.O_RDONLY)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                    return record
        if kind == "lesson":
            data = _lesson(data, existing, identifier)
        record = {
            "v": 1, "id": identifier, "kind": kind,
            "at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            "source": (source or "model") if kind == "lesson" else (
                "model" if kind in ("finding", "claim") else "code"),
            "recorded_by": "model" if kind == "claim" else "code",
            "repo": repo, "task_kind": task_kind, "refs": list(refs), "data": data,
        }
        if key is not None:
            record["key"] = key
        raw = (json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        fd = _open_private(directory / STORE_NAME, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
        try:
            remaining = memoryview(raw)
            while remaining:
                written = os.write(fd, remaining)
                if written <= 0:
                    raise OSError("ledger append made no progress")
                remaining = remaining[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        # Persist the new directory entry as well as the file's contents.
        fd = os.open(str(directory), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return record


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _number(value: object, name: str) -> object:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return value


def record_eval(spec: str, case: str, result: dict, directory: object,
                kit: Optional[str] = None) -> dict:
    """Record one attempt, including an unsuccessful first flip attempt."""
    _text(spec, "runtime", empty=False)
    _text(case, "case", empty=False)
    kit = "qk" if kit is None else _text(kit, "kit", empty=False)
    if not isinstance(result, dict) or not isinstance(result.get("criteria"), list):
        raise ValueError("eval result requires a criteria list")
    criteria = []
    for criterion in result["criteria"]:
        if not isinstance(criterion, dict) or type(criterion.get("passed")) is not bool:
            raise ValueError("eval criterion requires a boolean passed value")
        criteria.append({"name": _text(criterion.get("name"), "criterion name", empty=False),
                         "passed": criterion["passed"]})
    attempt = Path(directory).resolve()
    agent_error = bool(result.get("error"))
    data = {
        "case": case, "kit": kit, "runtime": spec, "criteria": criteria,
        "passed": all(item["passed"] for item in criteria) and not agent_error,
        "tokens": (None if result.get("tokens") is None
                   else _number(result["tokens"], "tokens")),
        "seconds": (None if "seconds" in result and result["seconds"] is None
                    else _number(result.get("seconds", 0), "seconds")),
        "agent_error": agent_error,
    }
    return append("eval", data, refs=[str(attempt), str(attempt / "check.json"),
                                      str(attempt / "final.md")],
                  key="eval:" + _digest(str(attempt)))


def _count(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _usage(value: object) -> dict:
    """Keep numeric accounting and runtime names, never raw agent envelopes."""
    if not isinstance(value, dict):
        raise ValueError("usage must be an object")
    result = {}
    for stage in ("preflight", "planning", "implementing", "verifying",
                  "reviewing", "fixing", "publishing"):
        if stage not in value:
            continue
        entries = value[stage]
        if not isinstance(entries, list):
            raise ValueError("usage stage must be a list")
        result[stage] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("usage entry must be an object")
            projected = {}
            if "spec" in entry:
                projected["spec"] = _text(entry["spec"], "usage spec")
            for field in ("input", "cached", "output", "cost_usd"):
                if field in entry:
                    projected[field] = _number(entry[field], "usage " + field)
            result[stage].append(projected)
    return result


def _relative_file(value: object) -> str:
    if not isinstance(value, str) or len(value) > 240:
        return ""
    path = Path(value)
    if (path.is_absolute() or ".." in path.parts or "\\" in value or ":" in value
            or any(unicodedata.category(char).startswith("C") for char in value)
            or "\u2028" in value or "\u2029" in value):
        return ""
    return value


def _finding(value: object, round_number: int) -> dict:
    if not isinstance(value, dict):
        raise ValueError("finding must be an object")
    line = value.get("line")
    if line is not None and (type(line) is not int or line < 1):
        line = None
    return {
        "round": round_number,
        "severity": _text(value.get("severity", ""), "finding severity"),
        "class": _text(value.get("class", ""), "finding class"),
        "file": _relative_file(value.get("file", "")), "line": line,
        "verdict": "reported",
    }


def _finding_identity(finding: dict) -> tuple:
    return tuple(finding[field] for field in ("severity", "class", "file", "line"))


def _findings(state: dict, round_number: int) -> list:
    latest = state.get("findings", [])
    if not isinstance(latest, list):
        raise ValueError("findings must be a list")
    history = state.get("review_history")
    if history is None or history == []:
        return [_finding(value, round_number) for value in latest]
    if not isinstance(history, list):
        raise ValueError("review_history must be a list")
    result = []
    for review in history:
        if not isinstance(review, dict) or not isinstance(review.get("findings"), list):
            raise ValueError("review history requires round and findings")
        number = _count(review.get("round"), "review round")
        result.append([_finding(value, number) for value in review["findings"]])
    final = {_finding_identity(finding) for finding in result[-1]}
    for findings in result[:-1]:
        for finding in findings:
            if _finding_identity(finding) not in final:
                finding["verdict"] = "not-reported-in-final-review"
    return [finding for findings in result for finding in findings]


def record_run(state: dict, directory: object) -> dict:
    """Project a stopped snapshot; repeated calls also repair missing findings."""
    if not isinstance(state, dict) or state.get("stage") not in ("done", "blocked", "aborted"):
        raise ValueError("only done, blocked or aborted runs can be recorded")
    source = Path(directory).resolve()
    repo_path = _text(state.get("repo", ""), "repo")
    root = Path(repo_path).resolve() if repo_path else None
    repo = root.name if root else ""
    task_kind = _text(state.get("task_kind", ""), "task_kind")
    findings = state.get("findings", [])
    addressed = state.get("addressed", [])
    if not isinstance(findings, list) or not isinstance(addressed, list):
        raise ValueError("findings and addressed must be lists")
    verify = state.get("verify_results", [])
    if not isinstance(verify, list):
        raise ValueError("verify_results must be a list")
    checks = []
    for index, check in enumerate(verify):
        if not isinstance(check, dict) or type(check.get("exit")) is not int:
            raise ValueError("verification result requires an integer exit")
        checks.append({"index": index, "exit": check["exit"]})
    data = {
        "run_id": _text(state.get("id"), "run id", empty=False),
        "run_key": str(source), "status": state["stage"],
        "source_revision": _count(state.get("ledger_revision", 0), "ledger_revision"),
        "repo_path": str(root) if root else "",
        "impl": _text(state.get("impl", ""), "impl"),
        "review": _text(state.get("review", ""), "review"),
        "commit": _text(state.get("commit", ""), "commit"),
        "pr_url": _text(state.get("pr_url", ""), "pr_url"),
        "verify_results": checks, "usage": _usage(state.get("usage", {})),
        "fix_rounds": _count(state.get("fix_rounds", 0), "fix_rounds"),
        "remaining_count": len(findings), "addressed_count": len(addressed),
    }
    projected = _findings(state, data["fix_rounds"])
    snapshot = _digest({"repo": repo, "task_kind": task_kind,
                        "data": data, "findings": projected})
    run = append("run", data, repo=repo, task_kind=task_kind,
                 refs=[str(source / "state.json")], key="run:" + snapshot)
    for position, finding in enumerate(projected):
        append("finding", dict(finding, run_id=data["run_id"], run_key=data["run_key"]),
               repo=run["repo"], task_kind=task_kind, refs=[run["id"]],
               key=f"finding:{snapshot}:{position}")
    return run
