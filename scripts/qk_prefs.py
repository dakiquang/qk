#!/usr/bin/env python3
"""qk-prefs: capture lasting working preferences as proposals that wait for approval.

Commands:
  hook --runtime claude|codex   UserPromptSubmit hook. Reads the hook JSON on stdin and,
                                when the prompt contains a lasting-preference cue, prints
                                context that asks the agent to record a proposal.
  propose ...                   Append one pending proposal (used by the agent).
  list [--all]                  Print pending (or all) proposals as JSON lines.
  resolve ID applied|dismissed  Mark a pending proposal after the user decides.

The hook never blocks a prompt, never calls the network and never logs prompt text.
Nothing here edits memory, rules, CLAUDE.md or AGENTS.md; applying a proposal is done
by the explicit qk-prefs skill after the user approves it.
"""
import json
import os
import re
import sys
import unicodedata

# The hook runs on every prompt, so modules only the store commands need
# (argparse, tempfile, secrets, datetime, pathlib, fcntl) are imported lazily.

STORE_NAME = "preferences-pending.jsonl"
LOCK_NAME = "preferences-pending.lock"
MAX_PROMPT = 4000
LIMITS = {"title": 120, "content": 1000, "project": 100}
MAX_QUOTE = 300
STATUSES = ("pending", "applied", "dismissed")

# Unambiguous phrases only. A bare Vietnamese "luôn" usually means "right away"
# ("làm luôn đi"), so it is matched only as "luôn luôn".
CUE_RE = re.compile(
    r"\b(?:"
    r"từ nay|từ giờ|từ lần sau|lần sau|mặc định|luôn luôn|lúc nào cũng|"
    r"đừng bao giờ|không bao giờ được|ghi nhớ|nhớ là|thay vì|"
    r"from now on|going forward|by default|always|never(?!\s+mind)|next time|"
    r"remember (?:that|to)|i prefer|i'd prefer|stop using|instead of"
    r")\b",
    re.IGNORECASE,
)
FENCE_RE = re.compile(r"```.*?(?:```|\Z)", re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


# ---------------------------------------------------------------- detection


def has_cue(prompt):
    """True when the prompt states something that may be a lasting preference."""
    text = unicodedata.normalize("NFC", prompt or "")
    stripped = text.lstrip()
    if not stripped or stripped[0] in "/$" or len(text) > MAX_PROMPT:
        return False
    text = FENCE_RE.sub(" ", text)
    text = INLINE_CODE_RE.sub(" ", text)
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(">"))
    return bool(CUE_RE.search(text))


def nudge():
    import shlex

    script = shlex.quote(os.path.realpath(__file__))
    return (
        "QK PREFERENCE CUE: the user's message may state a lasting working preference "
        "(a default, an always/never rule, or a correction meant for future work). "
        "If it is meant to apply beyond the current task, record it once as a proposal with: "
        f"python3 {script} propose --scope global|project [--project <repo folder name>] "
        "--title '<short title>' --content '<the preference as one instruction>' "
        "--quote '<the user's own words>'. "
        "Use --scope project only when it clearly applies to this repository. "
        "Skip one-off task details. Do not edit memory, rules, CLAUDE.md or AGENTS.md, "
        "and do not ask the user first: the proposal waits for their approval via qk-prefs. "
        "Never put secrets, tokens, credentials or customer data in a proposal. "
        "Then continue the task."
    )


def hook_output(runtime):
    # Claude Code and Codex document the same UserPromptSubmit output shape; both were
    # checked in a real session (see docs/en/runtimes.md). The flag stays so a runtime
    # with a different shape can be added without changing hook registrations.
    del runtime
    return json.dumps(
        {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": nudge()}},
        ensure_ascii=False,
    )


def run_hook(runtime):
    try:
        payload = json.loads(sys.stdin.read() or "null")
        prompt = payload.get("prompt") if isinstance(payload, dict) else None
        if isinstance(prompt, str) and has_cue(prompt):
            sys.stdout.write(hook_output(runtime) + "\n")
    except Exception:  # a hook must never break the user's prompt
        pass
    return 0


def cmd_hook(args):
    return run_hook(args.runtime)


# ---------------------------------------------------------------- store


def state_dir():
    from pathlib import Path

    base = os.environ.get("QK_PREFS_STATE_DIR")
    if base:
        return Path(base)
    xdg = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(xdg) / "qk"


def store_path():
    return state_dir() / STORE_NAME


def file_lock():
    try:
        import fcntl
    except ImportError:  # Windows: run without a lock
        return None
    return fcntl


class locked:
    """Exclusive lock on a side file; the store itself is replaced on resolve."""

    def __enter__(self):
        directory = state_dir()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.fd = os.open(str(directory / LOCK_NAME), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl = file_lock()
        if fcntl:
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        os.close(self.fd)
        return False


def read_lines():
    """Return (raw_line, record_or_None) pairs; unparseable lines are kept verbatim."""
    path = store_path()
    if not path.is_file():
        return []
    pairs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            record = None
        pairs.append((line, record if isinstance(record, dict) else None))
    return pairs


def records():
    return [record for _, record in read_lines() if record]


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def cmd_propose(args):
    fields = {
        "title": normalize(args.title),
        "content": normalize(args.content),
        "project": normalize(args.project or ""),
    }
    for name in ("title", "content"):
        if not fields[name]:
            return fail(f"--{name} must not be empty")
    for name, limit in LIMITS.items():
        if len(fields[name]) > limit:
            return fail(f"--{name} is longer than {limit} characters")
    if args.scope == "project" and not fields["project"]:
        fields["project"] = os.path.basename(os.getcwd())
    if args.scope == "global":
        fields["project"] = ""
    quote = normalize(args.quote or "")[:MAX_QUOTE]

    with locked():
        for record in records():
            if (
                record.get("status") == "pending"
                and record.get("scope") == args.scope
                and record.get("project", "") == fields["project"]
                and record.get("content") == fields["content"]
            ):
                print(record.get("id", ""))
                return 0
        import secrets

        record = {
            "id": secrets.token_hex(4),
            "created": now(),
            "status": "pending",
            "scope": args.scope,
            "project": fields["project"],
            "title": fields["title"],
            "content": fields["content"],
            "quote": quote,
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        fd = os.open(str(store_path()), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    print(record["id"])
    return 0


def cmd_list(args):
    for record in records():
        if args.all or record.get("status") == "pending":
            print(json.dumps(record, ensure_ascii=False))
    return 0


def cmd_resolve(args):
    with locked():
        pairs = read_lines()
        out, found = [], False
        for raw, record in pairs:
            if record and record.get("id") == args.id:
                if record.get("status") != "pending":
                    return fail(f"proposal {args.id} is already {record.get('status')}")
                record = dict(record, status=args.status, resolved=now())
                if args.target:
                    record["target"] = normalize(args.target)[:300]
                raw, found = json.dumps(record, ensure_ascii=False), True
            out.append(raw)
        if not found:
            return fail(f"no proposal {args.id}")
        import tempfile

        fd, tmp = tempfile.mkstemp(dir=str(state_dir()), prefix=".prefs-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("\n".join(out) + "\n")
            os.replace(tmp, str(store_path()))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    print(f"{args.id} {args.status}")
    return 0


def now():
    from datetime import datetime

    return datetime.now().astimezone().isoformat(timespec="seconds")


def fail(message):
    print(f"qk-prefs: {message}", file=sys.stderr)
    return 1


# ---------------------------------------------------------------- cli


def parser():
    import argparse

    root = argparse.ArgumentParser(prog="qk_prefs.py", description=__doc__.splitlines()[0])
    sub = root.add_subparsers(dest="command", required=True)

    hook = sub.add_parser("hook", help="UserPromptSubmit hook (reads JSON on stdin)")
    hook.add_argument("--runtime", choices=("claude", "codex"), default="claude")
    hook.set_defaults(func=cmd_hook)

    propose = sub.add_parser("propose", help="record one pending proposal")
    propose.add_argument("--scope", choices=("global", "project"), required=True)
    propose.add_argument("--project", help="repository folder name (scope project)")
    propose.add_argument("--title", required=True)
    propose.add_argument("--content", required=True)
    propose.add_argument("--quote", help="the user's own words")
    propose.set_defaults(func=cmd_propose)

    listing = sub.add_parser("list", help="print proposals as JSON lines")
    listing.add_argument("--all", action="store_true", help="include resolved proposals")
    listing.set_defaults(func=cmd_list)

    resolve = sub.add_parser("resolve", help="mark a pending proposal")
    resolve.add_argument("id")
    resolve.add_argument("status", choices=STATUSES[1:])
    resolve.add_argument("--target", help="where an applied proposal was written")
    resolve.set_defaults(func=cmd_resolve)
    return root


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    # Fast path for the per-prompt hook: skip argparse for the exact forms runtimes use.
    if argv[:1] == ["hook"] and argv[1:] in ([], ["--runtime", "claude"], ["--runtime", "codex"]):
        return run_hook(argv[2] if len(argv) == 3 else "claude")
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
