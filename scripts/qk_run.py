#!/usr/bin/env python3
"""qk-run: drive one task from request to an opened pull request.

Stages: preflight -> planning -> awaiting_approval (human gate) -> implementing ->
verifying -> reviewing -> [fixing -> verifying -> reviewing, at most once] ->
publishing -> done. Any failed gate ends in `blocked` with a reason; `resume`
retries the blocked stage.

Agents only edit files in an isolated worktree. Only this runner commits, pushes
and opens the PR. It never merges, releases, deletes branches or switches models.
"""
import argparse
import json
import os
import queue
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

QK_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QK_ROOT / "skills" / "qk-commit" / "scripts"))
from qk_preflight import check_identity  # noqa: E402
DEFAULT_IMPL = "omp:anthropic/claude-opus-5-5"
DEFAULT_REVIEW = "codex:"
RUNTIMES = ("omp", "claude", "codex")
DEFAULT_TIMEOUT = 1800
HEARTBEAT_SECONDS = 60
STDERR_DRAIN_SECONDS = 5
KILL_GRACE_SECONDS = 10
DISPLAY_LIMIT = 120
TITLE_LIMIT = 72
PLAN_RE = re.compile(r"<<<QK-PLAN\s*\n(.*?)\n\s*QK-PLAN>>>", re.S)
RESULT_RE = re.compile(r"```qk-result\s*\n(.*?)\n```", re.S)
VERIFY_RE = re.compile(r"```qk-verify\s*\n(.*?)\n```", re.S)
CONVENTIONAL_RE = re.compile(r"^[a-z]+(\([^()\r\n]+\))?!?: \S")
FOREIGN_PREFIX_RE = re.compile(r"^[^\s:]+: ")
TITLE_TYPES = {"fix": "fix", "fixes": "fix", "repair": "fix", "resolve": "fix", "correct": "fix",
               "doc": "docs", "docs": "docs", "document": "docs", "test": "test", "tests": "test",
               "refactor": "refactor", "simplify": "refactor", "rename": "refactor"}
TERMINAL = ("done", "aborted")


class Blocked(Exception):
    """A gate failed; the run stops in `blocked` with this reason."""


# ---------------------------------------------------------------- state


def state_root():
    base = os.environ.get("QK_RUN_STATE_DIR")
    if base:
        return Path(base)
    xdg = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(xdg) / "qk-run"


def run_dir(run_id):
    return state_root() / run_id


def load(run_id):
    path = run_dir(run_id) / "state.json"
    if not path.is_file():
        sys.exit(f"qk-run: no run {run_id!r} under {state_root()}")
    return json.loads(path.read_text(encoding="utf-8"))


def save(state):
    directory = run_dir(state["id"])
    directory.mkdir(parents=True, exist_ok=True)
    state["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    tmp = directory / "state.json.tmp"
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(directory / "state.json")


def log(state, message):
    line = f"[{time.strftime('%H:%M:%S')}] {state['stage']}: {message}"
    print(line, flush=True)
    with open(run_dir(state["id"]) / "run.log", "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


# ---------------------------------------------------------------- processes


def sh(args, cwd, check=True, timeout=600, input_text=None):
    proc = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                          timeout=timeout, input=input_text)
    if check and proc.returncode != 0:
        raise Blocked(f"{' '.join(args[:3])} failed ({proc.returncode}): {proc.stderr.strip()[:500]}")
    return proc


def git(cwd, *args, check=True):
    return sh(["git", *args], cwd, check=check).stdout.strip()


def gh(cwd, *args, check=True):
    """GitHub CLI call. Separate function so tests can replace it."""
    proc = sh(["gh", *args], cwd, check=check)
    return (proc.stdout or proc.stderr if args[:2] == ("auth", "status") else proc.stdout).strip()


# ---------------------------------------------------------------- agents


def parse_spec(spec):
    runtime, _, model = spec.partition(":")
    if runtime not in RUNTIMES:
        raise SystemExit(f"qk-run: runtime must be one of {RUNTIMES}, got {runtime!r}")
    return runtime, model


FAMILY_NAMES = (("anthropic", ("claude", "opus", "sonnet", "haiku")),
                ("openai", ("gpt", "codex")),
                ("google", ("gemini",)),
                ("xai", ("grok",)))
PROVIDER_FAMILIES = {"anthropic": "anthropic", "openai": "openai", "openai-codex": "openai",
                     "google": "google", "xai": "xai", "xai-oauth": "xai"}


def family(spec):
    """Model family of a runtime:model spec. Unknown families are an error, never a pass."""
    runtime, model = parse_spec(spec)
    provider, _, name = model.lower().rpartition("/")
    if not name:
        if runtime == "claude":
            return "anthropic"
        if runtime == "codex":
            return "openai"
        raise SystemExit(f"qk-run: {spec!r} needs an explicit model, e.g. omp:anthropic/claude-opus-5-5")
    for found, hints in FAMILY_NAMES:
        if any(hint in name for hint in hints) or re.match(r"o\d", name) and found == "openai":
            return found
    if provider in PROVIDER_FAMILIES:
        return PROVIDER_FAMILIES[provider]
    raise SystemExit(f"qk-run: cannot tell the model family of {spec!r}; use a provider/model id")


CODEX_KEEP_RE = re.compile(r"^\s*(model|model_reasoning_effort)\s*=")
TOML_TABLE_RE = re.compile(r"^\s*\[")


def codex_home(directory):
    """Private HOME for Codex inside the run directory, created once per run and reused.

    It keeps only the real config's top-level `model` and `model_reasoning_effort` and links the real
    `auth.json`, so Codex loads no user skills or MCP servers but stays logged in."""
    home = Path(directory) / "codex-home"
    codex = home / ".codex"
    real = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    if not codex.is_dir():
        codex.mkdir(parents=True)
        kept = []
        config = real / "config.toml"
        if config.is_file():
            for line in config.read_text(encoding="utf-8").splitlines():
                if TOML_TABLE_RE.match(line):
                    break
                if CODEX_KEEP_RE.match(line):
                    kept.append(line + "\n")
        (codex / "config.toml").write_text("".join(kept), encoding="utf-8")
    auth = codex / "auth.json"
    if (real / "auth.json").is_file() and not auth.exists() and not auth.is_symlink():
        auth.symlink_to(real / "auth.json")  # checked on every call: a login made after the home was created still counts
    return home


def agent_command(spec, write, cwd, extra_dirs, read_only_mcp=()):
    """Command line, last-message file (Codex) and environment (None = inherit) for one agent turn.

    Every runtime runs without user skills; read-only stages also run without MCP where the runtime allows it."""
    runtime, model = parse_spec(spec)
    if runtime == "claude":
        cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--disable-slash-commands",
               "--permission-mode", "acceptEdits" if write else "plan"]
        if write:
            cmd += ["--allowedTools", "Bash,Edit,Write,Read,Grep,Glob"]
        else:
            cmd += ["--tools", "Read,Grep,Glob"]
            if not read_only_mcp:
                cmd += ["--strict-mcp-config"]
        for directory in extra_dirs:
            cmd += ["--add-dir", str(directory)]
        if model:
            cmd += ["--model", model]
        return cmd, None, None
    if runtime == "codex":
        out = Path(extra_dirs[0]) / f"codex-last-{secrets.token_hex(4)}.txt"
        cmd = ["codex", "exec", "--sandbox", "workspace-write" if write else "read-only",
               "--ephemeral", "--json", "-C", str(cwd), "--output-last-message", str(out)]
        for directory in extra_dirs:
            cmd += ["--add-dir", str(directory)]
        if model:
            cmd += ["-m", model]
        real_home = Path.home()
        cache = os.environ.get("XDG_CACHE_HOME") or str(real_home / ".cache")
        data = os.environ.get("XDG_DATA_HOME") or str(real_home / ".local" / "share")
        home = codex_home(extra_dirs[0])
        env = dict(os.environ, HOME=str(home), CODEX_HOME=str(home / ".codex"))
        env.setdefault("UV_CACHE_DIR", str(Path(cache) / "uv"))
        env.setdefault("UV_PYTHON_INSTALL_DIR", str(Path(data) / "uv" / "python"))
        return cmd + ["-"], out, env
    cmd = ["omp", "-p", "--mode", "json", "--no-session", "--no-title", "--no-skills", "--no-extensions",
           "--no-rules", "--cwd", str(cwd)]
    profile = os.environ.get("QK_RUN_OMP_PROFILE")
    if profile:
        cmd += ["--profile", profile]
    if model:
        cmd += ["--model", model]
    if write:
        cmd += ["--approval-mode", "yolo", "--tools", "read,grep,glob,edit,write,bash"]
    else:
        cmd += ["--tools", "read,grep,glob"]
    for directory in extra_dirs:
        cmd += ["--add-dir", str(directory)]
    return cmd, None, None


DISPLAY_ROOTS = []  # (prefix, replacement) pairs set by call_agent so paths display relative to the worktree


def shorten(text):
    """Show paths under the agent's working directory relative to it, and the home directory as ~.

    A root is replaced only as a whole path segment, so `<root>-old/x` stays as it is."""
    for prefix, replacement in DISPLAY_ROOTS:
        bare = replacement.rstrip("/") or "."
        text = re.sub(re.escape(prefix) + r"(/|(?=[\s'\":;,)]|$))",
                      lambda m, r=replacement, b=bare: r if m.group(1) == "/" else b, text)
    return text


def action(verb, target, suffix=""):
    """One display line `<verb> <target><suffix>` of at most DISPLAY_LIMIT characters; only the target is clipped."""
    if not isinstance(target, str) or not target.strip():
        return None
    target = shorten(target)
    room = DISPLAY_LIMIT - len(verb) - 1 - len(suffix)
    return f"{verb} {' '.join(target.split())[:room]}{suffix}"


CLAUDE_TOOLS = {"Read": ("read", "file_path"), "Edit": ("edit", "file_path"),
                "Write": ("write", "file_path"), "Bash": ("run", "command")}
OMP_TOOLS = {"read": ("read", "path"), "edit": ("edit", "path"),
             "write": ("write", "path"), "bash": ("run", "command")}
MCP_PREFIXES = ("xd://", "mcp://")
DESTINATION_KEYS = ("path", "file_path", "uri")  # arguments that name where a tool call goes, not what it searches for


def mcp_target(name, args):
    """The MCP or runtime-device identifier a tool call reaches, or None for an ordinary tool call.

    A call counts when the tool name contains `mcp__` or starts with `xd://`/`mcp://`, or when a destination
    argument (`path`, `file_path`, `uri`) starts with `xd://`/`mcp://` (omp routes MCP through
    `write xd://mcp__...`). Other arguments, such as a search pattern, never count."""
    if "mcp__" in name or name.startswith(MCP_PREFIXES):
        return name
    for key in DESTINATION_KEYS if isinstance(args, dict) else ():
        value = args.get(key)
        if isinstance(value, str) and value.startswith(MCP_PREFIXES):
            return value
    return None


def target_display(identifier):
    """`mcp <identifier>` for MCP tools; `tool <name>` for other `xd://<name>` runtime devices."""
    name = identifier[len("xd://"):] if identifier.startswith("xd://") else identifier
    if identifier.startswith("xd://") and not name.startswith("mcp__"):
        return action("tool", name) or identifier
    return action("mcp", name) or identifier


def normalise(text):
    return re.sub(r"[^A-Za-z0-9]", "_", text)


def mcp_allowed(identifier, names):
    """True when the identifier is a tool of a server listed with --read-only-mcp (`mcp__<server>_...`)."""
    if identifier.startswith("mcp://"):
        return False
    name = identifier[len("xd://"):] if identifier.startswith("xd://") else identifier
    return any(normalise(name).startswith(f"mcp__{normalise(server)}_") for server in names if server.strip())


def claude_calls(event):
    """(tool name, input) of every tool use in a Claude assistant event."""
    message = event.get("message")
    content = message.get("content") if event.get("type") == "assistant" and isinstance(message, dict) else None
    return [(part["name"], part.get("input")) for part in (content if isinstance(content, list) else [])
            if isinstance(part, dict) and part.get("type") == "tool_use" and isinstance(part.get("name"), str)]


def omp_calls(event):
    """(tool name, args) of an omp tool start event."""
    if event.get("type") == "tool_execution_start" and isinstance(event.get("toolName"), str):
        return [(event["toolName"], event.get("args"))]
    return []


def claude_event(event):
    """Claude Code stream-json event -> (display line or None, final text or None)."""
    if event.get("type") == "result":
        return None, event["result"] if isinstance(event.get("result"), str) else None
    for name, args in claude_calls(event):
        target = mcp_target(name, args)
        if target:
            return target_display(target), None
        if name in CLAUDE_TOOLS:
            verb, key = CLAUDE_TOOLS[name]
            return action(verb, args.get(key) if isinstance(args, dict) else None), None
    return None, None


def codex_event(event):
    """Codex `exec --json` event -> (display line or None, final text or None)."""
    item = event.get("item")
    if event.get("type") not in ("item.started", "item.completed") or not isinstance(item, dict):
        return None, None
    if item.get("type") == "command_execution":
        code = item.get("exit_code")
        suffix = f" -> exit {code}" if isinstance(code, int) and not isinstance(code, bool) else ""
        return action("run", item.get("command"), suffix), None
    if event["type"] == "item.completed" and item.get("type") == "agent_message" and isinstance(item.get("text"), str):
        return None, item["text"]
    return None, None


def omp_event(event):
    """omp `--mode json` event -> (display line or None, final text or None)."""
    for name, args in omp_calls(event):
        target = mcp_target(name, args)
        if target:
            return target_display(target), None
        if name in OMP_TOOLS:
            verb, key = OMP_TOOLS[name]
            return action(verb, args.get(key) if isinstance(args, dict) else None), None
    message = event.get("message")
    if event.get("type") == "message_end" and isinstance(message, dict) and message.get("role") == "assistant":
        content = message.get("content")
        parts = content if isinstance(content, list) else []
        texts = [p["text"] for p in parts
                 if isinstance(p, dict) and p.get("type") == "text" and isinstance(p.get("text"), str)]
        return None, "".join(texts) if texts else None
    return None, None


EVENT_PARSERS = {"claude": claude_event, "codex": codex_event, "omp": omp_event}
TOOL_CALLS = {"claude": claude_calls, "codex": lambda event: [], "omp": omp_calls}  # Codex isolation has no MCP


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def claude_usage(event):
    """Usage of a Claude `result` event; `input` adds cache reads and writes, which Claude counts apart."""
    usage = event.get("usage") if event.get("type") == "result" else None
    if not isinstance(usage, dict):
        return None
    cached = number(usage.get("cache_read_input_tokens"))
    found = {"input": number(usage.get("input_tokens")) + cached + number(usage.get("cache_creation_input_tokens")),
             "cached": cached, "output": number(usage.get("output_tokens"))}
    if number(event.get("total_cost_usd")):
        found["cost_usd"] = event["total_cost_usd"]
    return found


def codex_usage(event):
    """Usage of a Codex `turn.completed` event; its `input_tokens` already include cached tokens."""
    usage = event.get("usage") if event.get("type") == "turn.completed" else None
    if not isinstance(usage, dict):
        return None
    return {"input": number(usage.get("input_tokens")), "cached": number(usage.get("cached_input_tokens")),
            "output": number(usage.get("output_tokens"))}


def omp_usage(event):
    """Usage of one omp turn (`turn_end`); `input` adds cache reads and writes, which omp counts apart."""
    message = event.get("message") if event.get("type") == "turn_end" else None
    usage = message.get("usage") if isinstance(message, dict) else None
    if not isinstance(usage, dict):
        return None
    cached = number(usage.get("cacheRead"))
    found = {"input": number(usage.get("input")) + cached + number(usage.get("cacheWrite")),
             "cached": cached, "output": number(usage.get("output"))}
    cost = usage.get("cost")
    if isinstance(cost, dict) and number(cost.get("total")):
        found["cost_usd"] = cost["total"]
    return found


USAGE_READERS = {"claude": claude_usage, "codex": codex_usage, "omp": omp_usage}


def add_usage(total, usage):
    """Sum of two usage dicts; either may be None. `cost_usd` is kept only when some part reported it."""
    if usage is None:
        return total
    summed = dict(total or {"input": 0, "cached": 0, "output": 0})
    for key in ("input", "cached", "output"):
        summed[key] += usage[key]
    if "cost_usd" in usage:
        summed["cost_usd"] = summed.get("cost_usd", 0) + usage["cost_usd"]
    return summed


def tokens_line(usage):
    cost = f" cost=${usage['cost_usd']:.4f}" if "cost_usd" in usage else ""
    return f"tokens in={usage['input']} cached={usage['cached']} out={usage['output']}{cost}"


def stop_agent(proc):
    """SIGTERM the agent's process group, then SIGKILL it after the grace period."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=KILL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()


def feed(stream, text):
    try:
        stream.write(text)
        stream.close()
    except OSError:
        pass


def pump(stream, put):
    for line in stream:
        put(line)
    put(None)


def call_agent(spec, prompt, cwd, write, timeout, extra_dirs, *, events, progress, read_only_mcp=()):
    """Run one headless agent turn, streaming its tool actions to `progress`; return (final text, usage or None).

    Raw JSON events are appended to `events`. A read-only turn that calls MCP or another runtime device
    (except servers in `read_only_mcp`) is stopped and blocks. Replaced in tests."""
    cmd, out_file, env = agent_command(spec, write, cwd, extra_dirs, read_only_mcp)
    runtime = parse_spec(spec)[0]
    parse, calls, read_usage = EVENT_PARSERS[runtime], TOOL_CALLS[runtime], USAGE_READERS[runtime]
    DISPLAY_ROOTS[:] = [(str(Path(cwd).resolve()), ""), (str(Path(cwd)), ""), (str(Path.home()), "~/")]
    try:
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                start_new_session=True, env=env)
    except FileNotFoundError:
        raise Blocked(f"runtime binary not found: {cmd[0]}")
    lines, errors = queue.Queue(), []
    stderr_reader = threading.Thread(target=pump, args=(proc.stderr, errors.append), daemon=True)
    for thread in (threading.Thread(target=feed, args=(proc.stdin, prompt), daemon=True),
                   threading.Thread(target=pump, args=(proc.stdout, lines.put), daemon=True), stderr_reader):
        thread.start()
    start = quiet_since = time.monotonic()
    deadline = start + timeout
    last, final, usage = "no action yet", None, None
    try:
        with open(events, "a", encoding="utf-8") as sink:
            while True:
                now = time.monotonic()
                if now >= deadline:
                    stop_agent(proc)
                    raise Blocked(f"{spec} timed out after {timeout}s; agent stopped")
                if now >= quiet_since + HEARTBEAT_SECONDS:
                    progress(f"still running ({int(now - start)}s, last: {last})")
                    quiet_since = now
                try:
                    line = lines.get(timeout=min(deadline, quiet_since + HEARTBEAT_SECONDS) - now)
                except queue.Empty:
                    continue
                if line is None:
                    if usage:
                        progress(tokens_line(usage))
                    break
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(event, dict):
                    continue
                sink.write(line if line.endswith("\n") else line + "\n")
                sink.flush()
                quiet_since = time.monotonic()
                display, text = parse(event)
                if display:
                    last = display
                    progress(display)
                if text is not None:
                    final = text
                usage = add_usage(usage, read_usage(event))
                if not write:
                    for name, args in calls(event):
                        target = mcp_target(name, args)
                        if target and not mcp_allowed(target, read_only_mcp):
                            stop_agent(proc)
                            if usage:
                                progress(tokens_line(usage))
                            blocked = Blocked(f"read-only stage called {target_display(target)}")
                            blocked.usage = usage  # run_agent records the tokens the stopped turn used
                            raise blocked
        try:
            proc.wait(timeout=max(deadline - time.monotonic(), 0))
        except subprocess.TimeoutExpired:
            stop_agent(proc)
            raise Blocked(f"{spec} timed out after {timeout}s; agent stopped")
    finally:
        if proc.poll() is None:
            stop_agent(proc)
    stderr_reader.join(timeout=STDERR_DRAIN_SECONDS)  # the agent has exited; let the reader finish
    text = final or ""
    if out_file and out_file.is_file():
        text = out_file.read_text(encoding="utf-8")
        out_file.unlink()
    if proc.returncode != 0:
        stderr = "".join(line for line in errors if line)
        raise Blocked(f"{spec} exited {proc.returncode}: {(stderr or text).strip()[-800:]}")
    return text, usage


def parse_result(text):
    blocks = RESULT_RE.findall(text or "")
    if not blocks:
        raise Blocked("agent output has no ```qk-result``` block")
    try:
        result = json.loads(blocks[-1])
    except json.JSONDecodeError as error:
        raise Blocked(f"qk-result is not valid JSON: {error}")
    if result.get("status") not in ("done", "blocked", "needs_input"):
        raise Blocked(f"qk-result has invalid status {result.get('status')!r}")
    if result["status"] != "done":
        raise Blocked(f"agent reported {result['status']}: {result.get('reason') or result.get('summary')}")
    return result


RESULT_CONTRACT = """
End your reply with exactly one fenced block:
```qk-result
{"status": "done|blocked|needs_input", "summary": "...", "files": [], "evidence": [], "reason": "", "findings": []}
```
Use "blocked" or "needs_input" with a reason instead of guessing. Respond in the user's language.
""".strip()

CLEAN = ("Before reporting, delete build/test artifacts you created (caches, compiled files, coverage, "
         "logs) unless the repository already tracks such files.")

NO_GIT = ("Do not run git commit, git push, git checkout, git reset, git stash, git branch "
          "or open pull requests. The runner owns all git and GitHub actions.")


def checkout_state(path):
    return (git(path, "symbolic-ref", "-q", "HEAD", check=False),
            git(path, "rev-parse", "HEAD", check=False),
            git(path, "status", "--porcelain"))


def check_worktree(state, worktree):
    """Only the runner moves the worktree: it must stay on the run branch at the runner's commit."""
    expected = state.get("commit") or state["base_sha"]
    ref = git(worktree, "symbolic-ref", "-q", "HEAD", check=False)
    head = git(worktree, "rev-parse", "HEAD")
    if ref != f"refs/heads/{state['branch']}" or head != expected:
        raise Blocked(f"worktree HEAD is {ref or 'detached'} at {head[:12]}, expected {state['branch']} at "
                      f"{expected[:12]}; only the runner may commit or switch branches. "
                      f"Inspect {worktree}; abort the run if it cannot be restored")


def run_agent(state, role, prompt, write=None):
    spec = state["impl"] if role == "impl" else state["review"]
    write = role == "impl" if write is None else write
    worktree = Path(state["worktree"])
    check_worktree(state, worktree)
    if not write and tree_snapshot(worktree) != state["expected_tree"]:
        raise Blocked(f"worktree {worktree} differs from the state this read-only stage expects; "
                      "restore it or abort the run")
    primary = checkout_state(Path(state["repo"]))
    log(state, f"{spec} ({'write' if write else 'read-only'})")
    stem = run_dir(state["id"]) / f"{state['stage']}-{int(time.time())}-{secrets.token_hex(2)}"
    error, text, usage = None, "", None
    try:
        text, usage = call_agent(spec, prompt, worktree, write, state["timeout"], [run_dir(state["id"])],
                                 events=Path(f"{stem}.events.jsonl"), progress=lambda message: log(state, message),
                                 read_only_mcp=state.get("read_only_mcp", []))
    except Blocked as exc:
        error, usage = exc, getattr(exc, "usage", None)
    if usage:
        state.setdefault("usage", {}).setdefault(state["stage"], []).append({"spec": spec, **usage})
    Path(f"{stem}.out.md").write_text(text or "", encoding="utf-8")
    if checkout_state(Path(state["repo"])) != primary:
        raise Blocked("agent changed the user's primary checkout (branch, HEAD or files); stop and inspect it")
    check_worktree(state, worktree)
    if not write and tree_snapshot(worktree) != state["expected_tree"]:
        raise Blocked("read-only agent modified the worktree")
    if error:
        raise error
    return text, parse_result(text)


def tree_snapshot(worktree):
    """Content hash of the whole working tree (tracked and untracked, not ignored)."""
    git(worktree, "add", "-A")
    tree = git(worktree, "write-tree")
    git(worktree, "reset", "-q")
    return tree


def skill(name):
    return QK_ROOT / "skills" / name / "SKILL.md"


# ---------------------------------------------------------------- stages


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:40].rstrip("-") or "task")


def preflight(state):
    repo = Path(git(Path(state["repo"]), "rev-parse", "--show-toplevel"))
    state["repo"] = str(repo)
    if git(repo, "status", "--porcelain"):
        raise Blocked("primary checkout has uncommitted changes; commit or move them first (the runner never stashes)")
    ok, report = check_identity(repo, gh_call=gh, git_call=git)
    if not ok:
        raise Blocked(report)
    remote = git(repo, "remote", "get-url", "origin")
    base = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False).removeprefix("origin/")
    if not base:
        base = gh(repo, "repo", "view", "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name")
    if not base:
        raise Blocked("cannot discover the base branch from origin")
    branch = f"qk/{state['slug']}-{state['id'][-6:]}"
    if git(repo, "branch", "--list", branch) or git(repo, "ls-remote", "--heads", "origin", branch):
        raise Blocked(f"branch {branch} already exists")
    git(repo, "fetch", "origin", base)
    worktree = run_dir(state["id"]) / "worktree"
    git(repo, "worktree", "add", "-b", branch, str(worktree), f"origin/{base}")
    state.update(base=base, branch=branch, worktree=str(worktree), remote=remote,
                 base_sha=git(worktree, "rev-parse", "HEAD"), expected_tree=tree_snapshot(worktree))
    return "planning"


def planning(state):
    plan = run_dir(state["id"]) / "plan.md"
    feedback = state.get("feedback")
    previous = plan.read_text(encoding="utf-8") if feedback and plan.is_file() else ""
    revision = f"Previous plan:\n{previous}\nUser feedback to apply: {feedback}" if feedback else ""
    prompt = f"""Read {skill('qk-plan')} and follow it in `{'revise' if feedback else 'create'}` mode, read-only.
Repository checkout: {state['worktree']} (base {state['base']}). Do not edit files or run commands that write.
Task: {state['task']}
Instead of saving a file, put the complete plan between a line `<<<QK-PLAN` and a line `QK-PLAN>>>`;
the runner saves it. Start the plan with a `# <title>` line: an imperative title of at most 60 characters,
without a project-name prefix. The plan MUST contain a fenced block ```qk-verify``` listing, one per line, the shell
commands discovered from this repository that prove the done criteria. Each runs from the repository root
and must exit 0 on success. Do not invent commands; if none can be discovered, report needs_input.
{revision}
{NO_GIT}
{RESULT_CONTRACT}"""
    text, _ = run_agent(state, "impl", prompt, write=False)
    plans = PLAN_RE.findall(text)
    if not plans:
        raise Blocked("planner returned no <<<QK-PLAN ... QK-PLAN>>> block")
    plan.write_text(plans[-1].strip() + "\n", encoding="utf-8")
    commands = verify_commands(plans[-1])
    if not commands:
        raise Blocked("plan has no non-empty ```qk-verify``` block")
    state["verify"] = commands
    state.pop("feedback", None)
    print(f"\nPlan ready: {plan}\nReview it, then run:\n  qk-run approve {state['id']}\n"
          f"  qk-run revise {state['id']} \"<feedback>\"")
    return "awaiting_approval"


def verify_commands(text):
    blocks = VERIFY_RE.findall(text)
    if not blocks:
        return []
    return [line.strip() for line in blocks[-1].splitlines() if line.strip() and not line.strip().startswith("#")]


def implementing(state):
    prompt = f"""Read {skill('qk-cook')} and follow it to implement the approved plan {run_dir(state['id']) / 'plan.md'}.
Work only inside {state['worktree']}. The plan is approved; do not ask for approval again.
{CLEAN}
{NO_GIT}
{RESULT_CONTRACT}"""
    run_agent(state, "impl", prompt)
    if not git(Path(state["worktree"]), "status", "--porcelain"):
        raise Blocked("implementation produced no changes")
    state["impl_tree"] = tree_snapshot(Path(state["worktree"]))
    return "verifying"


def untracked(worktree):
    return set(git(worktree, "ls-files", "-o", "--exclude-standard", "-z").split("\0")) - {""}


def verifying(state):
    worktree = Path(state["worktree"])
    if tree_snapshot(worktree) != state["impl_tree"]:
        raise Blocked(f"worktree {worktree} changed since the implementation was recorded; "
                      "restore it or abort the run")
    before_untracked = untracked(worktree)
    results = []
    for command in state["verify"]:
        log(state, f"$ {command}")
        try:
            proc = subprocess.run(command, shell=True, cwd=str(worktree), capture_output=True,
                                  text=True, timeout=state["timeout"])
            code, output = proc.returncode, (proc.stdout + proc.stderr)[-4000:]
        except subprocess.TimeoutExpired:
            code, output = -1, "timed out"
        results.append({"cmd": command, "exit": code, "tail": output})
        log(state, f"exit {code}")
    state["verify_results"] = results
    created = sorted(untracked(worktree) - before_untracked)
    for relative in created:
        path = worktree / relative
        path.unlink()
        parent = path.parent
        while parent != worktree and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    if created:
        log(state, f"removed {len(created)} file(s) created by verification")
    if tree_snapshot(worktree) != state["impl_tree"]:
        raise Blocked("verification commands modified the worktree (tracked or new files); restore it or abort the run")
    failed = [r for r in results if r["exit"] != 0]
    if not failed:
        state["expected_tree"] = state["impl_tree"]
        return "reviewing"
    state["problems"] = [f"`{r['cmd']}` exited {r['exit']}:\n{r['tail']}" for r in failed]
    return next_fix(state, "verification failed")


def changed_files(worktree):
    git(worktree, "add", "-A")
    names = git(worktree, "diff", "--cached", "--name-only").splitlines()
    git(worktree, "reset", "-q")
    return set(names)


def repo_path(path, worktree):
    text = str(path or "").strip()
    for root in (str(worktree), str(Path(worktree).resolve())):
        if text.startswith(root + "/"):
            text = text[len(root) + 1:]
    while text.startswith("./"):
        text = text[2:]
    return text


def approved_plan(state):
    """The plan exactly as the user approved it; agents may edit their working copy, not this one."""
    import hashlib
    path = run_dir(state["id"]) / "approved-plan.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != state.get("approved_plan_sha"):
        raise Blocked(f"{path} is missing or changed after approval")
    return path, text


def reviewing(state):
    worktree = Path(state["worktree"])
    plan, _ = approved_plan(state)
    diff_file = run_dir(state["id"]) / "review.diff"
    git(worktree, "add", "-A")
    diff_file.write_text(git(worktree, "diff", "--cached", state["base_sha"]), encoding="utf-8")
    git(worktree, "reset", "-q")
    prompt = f"""Independent read-only review. Do not edit files and do not run commands that write.
Repository: {worktree}. Approved plan: {plan}. Full diff: {diff_file}.
Check correctness, security, regressions, scope versus the plan, and missing tests. Re-read every line you cite.
Report only verified problems introduced by this diff. Put them in "findings" as
{{"severity": "blocker|important|nit", "file": "<repo-relative path>", "line": N, "claim": "...", "fix": "..."}}.
Use status "done" when the review itself completed, even if there are findings.
{RESULT_CONTRACT}"""
    _, result = run_agent(state, "review", prompt)
    files = changed_files(worktree)
    findings = [f for f in result.get("findings") or [] if isinstance(f, dict)]
    for finding in findings:
        finding["file"] = repo_path(finding.get("file"), worktree)
        finding["severity"] = str(finding.get("severity", "")).lower()
    serious = [f for f in findings if f["severity"] in ("blocker", "important") and f["file"] in files]
    state["findings"] = findings
    if not serious:
        return "publishing"
    state["problems"] = [f"[{f['severity']}] {f['file']}:{f.get('line')} {f.get('claim')} Fix: {f.get('fix')}" for f in serious]
    return next_fix(state, "review found blocker/important issues")


def next_fix(state, why):
    if state.get("fix_rounds", 0) >= 1:
        raise Blocked(f"{why} after the single fix round:\n" + "\n".join(state["problems"]))
    state.setdefault("addressed", []).extend(state["problems"])
    return "fixing"


def fixing(state):
    state["fix_rounds"] = state.get("fix_rounds", 0) + 1
    approved_plan(state)
    problems = "\n".join(f"- {p}" for p in state["problems"])
    prompt = f"""Read {skill('qk-cook')}. Fix only the problems below in {state['worktree']}, with the smallest change,
staying within the approved plan {run_dir(state['id']) / 'plan.md'}. Do not weaken tests or checks.
Problems:
{problems}
{CLEAN}
{NO_GIT}
{RESULT_CONTRACT}"""
    run_agent(state, "impl", prompt)
    state["impl_tree"] = tree_snapshot(Path(state["worktree"]))
    return "verifying"


def clip_title(text, limit=TITLE_LIMIT):
    """Cut a title longer than `limit` at its last space within `limit + 1` characters; hard-cut a single word."""
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit + 1)
    return text[:cut].rstrip() if cut > 0 else text[:limit]


def plan_title(state):
    _, plan = approved_plan(state)
    for line in plan.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return state["task"].splitlines()[0]


def uses_conventional_commits(subjects):
    return sum(1 for s in subjects if CONVENTIONAL_RE.match(s)) * 2 > len(subjects)


def conventional_title(title, subjects):
    """Prefix a type and lowercase the first letter (acronyms excepted) when the history is conventional.

    A non-conventional `<word>: ` prefix (e.g. a project or ticket name) is dropped before the type is added."""
    if not uses_conventional_commits(subjects) or CONVENTIONAL_RE.match(title):
        return clip_title(title)
    prefix = FOREIGN_PREFIX_RE.match(title)
    if prefix and title[prefix.end():].strip():
        title = title[prefix.end():].strip()
    words = title.split()
    first = words[0] if words else ""
    word = re.sub(r"[^a-z]", "", first.lower())
    second = first[1:2]
    subject = title if second.isupper() or second.isdigit() else title[:1].lower() + title[1:]
    return clip_title(f"{TITLE_TYPES.get(word, 'feat')}: {subject}")


def commit_title(state):
    """Plan title, typed when most of the base branch's last 20 non-merge subjects are conventional."""
    subjects = git(Path(state["worktree"]), "log", "-n", "20", "--no-merges", "--format=%s",
                   state["base_sha"]).splitlines()
    return conventional_title(plan_title(state), subjects)


def pr_body(state):
    _, plan = approved_plan(state)
    checks = "\n".join(f"- `{r['cmd']}` → exit {r['exit']}" for r in state.get("verify_results", []))
    addressed = "\n".join(f"- {p.splitlines()[0]}" for p in state.get("addressed", [])) or "- none"
    findings = state.get("findings") or []
    remaining = "\n".join(f"- [{f.get('severity')}] {f.get('file')}:{f.get('line')} {f.get('claim')}" for f in findings) or "- none"
    return (f"## Task\n\n{state['task']}\n\n## Verification (run by qk-run)\n\n{checks}\n\n"
            f"## Independent review ({state['review']})\n\nAddressed in the fix round:\n{addressed}\n\n"
            f"Remaining findings:\n{remaining}\n\n"
            f"Fix rounds: {state.get('fix_rounds', 0)}\n\n<details><summary>Approved plan</summary>\n\n{plan}\n\n</details>\n")


def publishing(state):
    worktree = Path(state["worktree"])
    check_worktree(state, worktree)
    title = commit_title(state)
    if not state.get("commit"):
        git(worktree, "add", "-A")
        if not git(worktree, "diff", "--cached", "--name-only"):
            raise Blocked("nothing to commit")
        git(worktree, "commit", "-q", "-m", title)
        state["commit"] = git(worktree, "rev-parse", "HEAD")
        save(state)
    if not state.get("pushed"):
        ok, report = check_identity(worktree, gh_call=gh, git_call=git)
        if not ok:
            raise Blocked(report)
        git(worktree, "push", "-u", "origin", state["branch"])
        state["pushed"] = True
        save(state)
    if not state.get("pr_url"):
        existing = gh(worktree, "pr", "list", "--head", state["branch"], "--state", "all",
                      "--json", "url", "--jq", ".[0].url // empty")
        if existing:
            state["pr_url"] = existing
        else:
            body = run_dir(state["id"]) / "pr-body.md"
            body.write_text(pr_body(state), encoding="utf-8")
            state["pr_url"] = gh(worktree, "pr", "create", "--base", state["base"], "--head", state["branch"],
                                 "--title", title, "--body-file", str(body)).splitlines()[-1]
        save(state)
    print(f"\nPR ready for review: {state['pr_url']} (head {state['commit']})")
    return "done"


STAGES = {"preflight": preflight, "planning": planning, "implementing": implementing,
          "verifying": verifying, "reviewing": reviewing, "fixing": fixing, "publishing": publishing}


RESUMABLE_BY_HAND = ("verifying", "reviewing", "fixing")


def block(state, stage, error):
    """Stop the run in `blocked`. After verify, review or fix, also record the worktree as it was at the block,
    so `resume` can tell hand fixes made after it from changes made while the stage ran."""
    state.update(stage="blocked", blocked_at=stage, reason=str(error))
    state.pop("blocked_tree", None)
    if stage in RESUMABLE_BY_HAND:
        try:
            state["blocked_tree"] = tree_snapshot(Path(state["worktree"]))
        except Blocked:
            pass
    save(state)
    log(state, f"BLOCKED at {stage}: {error}")
    print(f"Resume after fixing the cause: qk-run resume {state['id']}")
    return 1


def advance(state):
    while state["stage"] in STAGES:
        stage = state["stage"]
        try:
            state["stage"] = STAGES[stage](state)
        except Blocked as error:
            return block(state, stage, error)
        save(state)
    return 0


def accept_manual_changes(state):
    """On resume, accept hand edits made after a block at verify, review or fix, and continue at `verifying`.

    Accepted only when the blocked stage itself left the tree as recorded (`impl_tree`) or was the write stage
    `fixing`: changes made while a read-only stage or the verify commands ran stay blocked by that stage's check."""
    blocked = state.pop("blocked_tree", None)
    if state["stage"] not in RESUMABLE_BY_HAND or not blocked:
        return
    worktree = Path(state["worktree"])
    current = tree_snapshot(worktree)
    if current == blocked or (state["stage"] != "fixing" and blocked != state.get("impl_tree")):
        return
    check_worktree(state, worktree)
    files = git(worktree, "diff", "--name-only", blocked, current).splitlines()
    log(state, f"manual changes recorded: {', '.join(files)}")
    state.update(impl_tree=current, stage="verifying")


# ---------------------------------------------------------------- CLI


def cmd_start(args):
    for spec in (args.impl, args.review):
        parse_spec(spec)
    read_only_mcp = args.read_only_mcp or []
    if any(not name.strip() for name in read_only_mcp):
        sys.exit("qk-run: --read-only-mcp needs a server name; got an empty value")
    for flag, spec in (("--impl", args.impl), ("--review", args.review)):
        if read_only_mcp and parse_spec(spec)[0] == "codex":
            sys.exit(f"qk-run: --read-only-mcp is not supported for codex ({flag} {spec}): planning and review "
                     "are read-only and Codex runs them without MCP; use claude or omp for that role")
    if family(args.impl) == family(args.review):
        sys.exit(f"qk-run: implementer and reviewer must be different model families ({family(args.impl)})")
    run_id = time.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)
    state = {"id": run_id, "task": args.task, "slug": slugify(args.task), "repo": str(Path(args.repo).resolve()),
             "impl": args.impl, "review": args.review, "timeout": args.timeout, "read_only_mcp": read_only_mcp,
             "stage": "preflight"}
    run_dir(run_id).mkdir(parents=True, exist_ok=False)
    save(state)
    print(f"qk-run {run_id}")
    return advance(state)


def cmd_approve(args):
    import hashlib
    state = load(args.id)
    if state["stage"] != "awaiting_approval":
        sys.exit(f"qk-run: run is {state['stage']}, not awaiting_approval")
    text = (run_dir(state["id"]) / "plan.md").read_text(encoding="utf-8")
    commands = verify_commands(text)
    if not commands:
        sys.exit("qk-run: plan.md has no non-empty ```qk-verify``` block; edit it or use revise")
    (run_dir(state["id"]) / "approved-plan.md").write_text(text, encoding="utf-8")
    state.update(stage="implementing", verify=commands,
                 approved_plan_sha=hashlib.sha256(text.encode("utf-8")).hexdigest())
    save(state)
    print("Approved. Verification commands that will run:\n" + "\n".join(f"  $ {c}" for c in commands))
    return advance(state)


def cmd_revise(args):
    state = load(args.id)
    if state["stage"] != "awaiting_approval":
        sys.exit(f"qk-run: run is {state['stage']}, not awaiting_approval")
    state.update(stage="planning", feedback=args.feedback)
    save(state)
    return advance(state)


def cmd_resume(args):
    state = load(args.id)
    if state["stage"] != "blocked":
        sys.exit(f"qk-run: run is {state['stage']}; only blocked runs resume")
    state["stage"] = state.pop("blocked_at")
    state.pop("reason", None)
    try:
        accept_manual_changes(state)
    except Blocked as error:
        return block(state, state["stage"], error)
    save(state)
    return advance(state)


def cmd_status(args):
    state = load(args.id)
    keys = ("id", "stage", "reason", "branch", "worktree", "fix_rounds", "pr_url", "commit")
    print(json.dumps({k: state[k] for k in keys if k in state}, ensure_ascii=False, indent=2))
    directory = run_dir(args.id)
    print(f"run dir: {directory}")
    run_log = directory / "run.log"
    if run_log.is_file():
        print("last log lines:")
        for line in run_log.read_text(encoding="utf-8").splitlines()[-10:]:
            print(line)
    return 0


def cmd_abort(args):
    state = load(args.id)
    if state["stage"] in TERMINAL:
        sys.exit(f"qk-run: run already {state['stage']}")
    state["stage"] = "aborted"
    save(state)
    print(f"Aborted. Worktree kept at {state.get('worktree')}; remove it with `git worktree remove` when done.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="qk-run", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="start a run and stop at plan approval")
    start.add_argument("task")
    start.add_argument("--repo", default=".")
    start.add_argument("--impl", default=DEFAULT_IMPL, help=f"runtime:model (default {DEFAULT_IMPL})")
    start.add_argument("--review", default=DEFAULT_REVIEW, help=f"runtime:model (default {DEFAULT_REVIEW} = Codex default model)")
    start.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="seconds per agent turn or verify command")
    start.add_argument("--read-only-mcp", action="append", metavar="NAME",
                       help="MCP server that read-only stages may call (repeatable; claude and omp only)")
    start.set_defaults(func=cmd_start)
    for name, func in (("approve", cmd_approve), ("resume", cmd_resume), ("status", cmd_status), ("abort", cmd_abort)):
        command = sub.add_parser(name)
        command.add_argument("id")
        command.set_defaults(func=func)
    revise = sub.add_parser("revise")
    revise.add_argument("id")
    revise.add_argument("feedback")
    revise.set_defaults(func=cmd_revise)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
