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
MAX_PROMPT = 4000  # only the start of a prompt is scanned
MAX_STDIN = 1_000_000  # larger hook payloads are ignored unread
LIMITS = {"title": 120, "content": 1000, "project": 100}
MAX_QUOTE = 300
STATUSES = ("pending", "applied", "dismissed")
PROPOSAL_FIELDS = ("scope", "project", "title", "content", "quote")

# Phrases that state a standing rule, not a choice for the task at hand. Common words
# such as "always", "never", "by default", "mặc định" only count at the start of a
# sentence or after an instruction lead-in, so "this function never returns" or
# "giá trị mặc định là None" do not match. A bare Vietnamese "luôn" usually means
# "right away" ("làm luôn đi"), so it counts only as "luôn luôn".
_START = r"(?:^|(?<=[.!?;:\n])\s*)"
_LEAD = r"(?:please|you should|make sure to|remember to|i want you to|hãy|nhớ)\s+"
CUE_RE = re.compile(
    r"\b(?:"
    r"từ nay|từ giờ(?!\s+(?:đến|tới))|từ lần sau|lần sau (?:nhớ|hãy|đừng|phải|luôn|cứ)|"
    r"luôn luôn|lúc nào cũng|đừng bao giờ|không bao giờ được|ghi nhớ|nhớ là|"
    r"from now on|going forward|from here on|"
    r"next time,\s|"
    r"remember (?:that|to)|stop using|don't ever|never again"
    r")\b"
    rf"|{_START}(?:by default|mặc định|always|never(?!\s+mind))\b"
    rf"|\b{_LEAD}(?:always|never)\b",
    re.IGNORECASE | re.MULTILINE,
)
FENCE_RE = re.compile(r"```.*?(?:```|\Z)", re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


# ---------------------------------------------------------------- detection


def has_cue(prompt):
    """True when the prompt states something that may be a lasting preference."""
    text = unicodedata.normalize("NFC", prompt or "")
    stripped = text.lstrip()
    if not stripped or stripped[0] in "/$":
        return False
    text = FENCE_RE.sub(" ", text[:MAX_PROMPT])
    text = INLINE_CODE_RE.sub(" ", text)
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(">"))
    return bool(CUE_RE.search(text))


def nudge():
    import shlex

    script = shlex.quote(os.path.realpath(__file__))
    return (
        "QK PREFERENCE CUE: the user's message may state a lasting working preference "
        "(a default, an always/never rule, or a correction meant for future work). "
        "If it is meant to apply beyond the current task, record it once as a proposal, "
        "passing a JSON object through a quoted heredoc so no shell quoting is needed: "
        f"python3 {script} propose --stdin <<'QK_PREF'\n"
        '{"scope": "global", "title": "<short title>", '
        '"content": "<the preference as one instruction>", "quote": "<the user\'s own words>"}\n'
        "QK_PREF\n"
        'Use "scope": "project" (optionally with "project": "<repo folder name>") only when '
        "it clearly applies to this repository. "
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
        raw = sys.stdin.read(MAX_STDIN + 1)
        if len(raw) > MAX_STDIN:
            return 0
        payload = json.loads(raw or "null")
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


def proposal_input(args):
    """Proposal fields from flags, or from one JSON object on stdin with --stdin."""
    if not args.stdin:
        return {name: getattr(args, name) for name in PROPOSAL_FIELDS}
    try:
        data = json.loads(sys.stdin.read(MAX_STDIN))
    except ValueError as error:
        raise ValueError(f"--stdin expects one JSON object: {error}") from None
    if not isinstance(data, dict):
        raise ValueError("--stdin expects one JSON object")
    unknown = set(data) - set(PROPOSAL_FIELDS)
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")
    values = {name: data.get(name) for name in PROPOSAL_FIELDS}
    if any(value is not None and not isinstance(value, str) for value in values.values()):
        raise ValueError("every field must be a string")
    return values


def cmd_propose(args):
    try:
        values = proposal_input(args)
    except ValueError as error:
        return fail(str(error))
    scope = values["scope"]
    if scope not in ("global", "project"):
        return fail("scope must be global or project")
    fields = {
        "title": normalize(values["title"] or ""),
        "content": normalize(values["content"] or ""),
        "project": normalize(values["project"] or ""),
    }
    for name in ("title", "content"):
        if not fields[name]:
            return fail(f"{name} must not be empty")
    if scope == "project" and not fields["project"]:
        fields["project"] = os.path.basename(os.getcwd())
    if scope == "global":
        fields["project"] = ""
    for name, limit in LIMITS.items():
        if len(fields[name]) > limit:
            return fail(f"{name} is longer than {limit} characters")
    quote = normalize(values["quote"] or "")[:MAX_QUOTE]

    with locked():
        for record in records():
            if (
                record.get("status") == "pending"
                and record.get("scope") == scope
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
            "scope": scope,
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
    propose.add_argument(
        "--stdin", action="store_true",
        help="read one JSON object with scope, project, title, content, quote from stdin",
    )
    propose.add_argument("--scope", choices=("global", "project"))
    propose.add_argument("--project", help="repository folder name (scope project)")
    propose.add_argument("--title")
    propose.add_argument("--content")
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
