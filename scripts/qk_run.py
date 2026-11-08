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
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

QK_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IMPL = "omp:anthropic/claude-opus-5-5"
DEFAULT_REVIEW = "codex:"
RUNTIMES = ("omp", "claude", "codex")
DEFAULT_TIMEOUT = 1800
PLAN_RE = re.compile(r"<<<QK-PLAN\s*\n(.*?)\n\s*QK-PLAN>>>", re.S)
RESULT_RE = re.compile(r"```qk-result\s*\n(.*?)\n```", re.S)
VERIFY_RE = re.compile(r"```qk-verify\s*\n(.*?)\n```", re.S)
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
    return sh(["gh", *args], cwd, check=check).stdout.strip()


# ---------------------------------------------------------------- agents


def parse_spec(spec):
    runtime, _, model = spec.partition(":")
    if runtime not in RUNTIMES:
        raise SystemExit(f"qk-run: runtime must be one of {RUNTIMES}, got {runtime!r}")
    return runtime, model


def family(spec):
    runtime, model = parse_spec(spec)
    text = model.lower()
    if runtime == "claude" or "claude" in text or text.startswith("anthropic/"):
        return "anthropic"
    if runtime == "codex" or "gpt" in text or text.startswith(("openai", "openai-codex")):
        return "openai"
    return text.split("/")[0] or runtime


def agent_command(spec, write, cwd, extra_dirs):
    runtime, model = parse_spec(spec)
    if runtime == "claude":
        cmd = ["claude", "-p", "--output-format", "text",
               "--permission-mode", "acceptEdits" if write else "plan"]
        if write:
            cmd += ["--allowedTools", "Bash,Edit,Write,Read,Grep,Glob"]
        else:
            cmd += ["--tools", "Read,Grep,Glob"]
        for directory in extra_dirs:
            cmd += ["--add-dir", str(directory)]
        if model:
            cmd += ["--model", model]
        return cmd, None
    if runtime == "codex":
        out = Path(extra_dirs[0]) / f"codex-last-{secrets.token_hex(4)}.txt"
        cmd = ["codex", "exec", "--sandbox", "workspace-write" if write else "read-only",
               "--ephemeral", "-C", str(cwd), "--output-last-message", str(out)]
        for directory in extra_dirs:
            cmd += ["--add-dir", str(directory)]
        if model:
            cmd += ["-m", model]
        return cmd + ["-"], out
    cmd = ["omp", "-p", "--no-session", "--no-title", "--cwd", str(cwd)]
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
    return cmd, None


def call_agent(spec, prompt, cwd, write, timeout, extra_dirs):
    """Run one headless agent turn; return its final text. Replaced in tests."""
    cmd, out_file = agent_command(spec, write, cwd, extra_dirs)
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), input=prompt, capture_output=True,
                              text=True, timeout=timeout)
    except FileNotFoundError:
        raise Blocked(f"runtime binary not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        raise Blocked(f"{spec} timed out after {timeout}s; the agent may still be running")
    text = proc.stdout
    if out_file and out_file.is_file():
        text = out_file.read_text(encoding="utf-8")
        out_file.unlink()
    if proc.returncode != 0:
        raise Blocked(f"{spec} exited {proc.returncode}: {(proc.stderr or text).strip()[-800:]}")
    return text


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


def run_agent(state, role, prompt, write=None):
    spec = state["impl"] if role == "impl" else state["review"]
    write = role == "impl" if write is None else write
    worktree = Path(state["worktree"])
    if not write:
        state["tree_snapshot"] = tree_snapshot(worktree)
    head = git(worktree, "rev-parse", "HEAD")
    user_status = git(Path(state["repo"]), "status", "--porcelain")
    log(state, f"{spec} ({'write' if write else 'read-only'})")
    text = call_agent(spec, prompt, worktree, write, state["timeout"],
                      [run_dir(state["id"])])
    (run_dir(state["id"]) / f"{state['stage']}-{int(time.time())}.out.md").write_text(text or "", encoding="utf-8")
    if git(worktree, "rev-parse", "HEAD") != head:
        raise Blocked("agent changed HEAD (commit/reset/checkout) in the worktree; only the runner may commit")
    if git(Path(state["repo"]), "status", "--porcelain") != user_status:
        raise Blocked("agent changed the user's primary checkout; stop and inspect it")
    if not write and tree_snapshot(worktree) != state.get("tree_snapshot"):
        raise Blocked("read-only agent modified the worktree")
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
    gh(repo, "auth", "status")
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
                 base_sha=git(worktree, "rev-parse", "HEAD"))
    return "planning"


def planning(state):
    plan = run_dir(state["id"]) / "plan.md"
    feedback = state.get("feedback")
    previous = plan.read_text(encoding="utf-8") if feedback and plan.is_file() else ""
    prompt = f"""Read {skill('qk-plan')} and follow it in `{'revise' if feedback else 'create'}` mode, read-only.
Repository checkout: {state['worktree']} (base {state['base']}). Do not edit files or run commands that write.
Task: {state['task']}
Instead of saving a file, put the complete plan between a line `<<<QK-PLAN` and a line `QK-PLAN>>>`;
the runner saves it. The plan MUST contain a fenced block ```qk-verify``` listing, one per line, the shell
commands discovered from this repository that prove the done criteria. Each runs from the repository root
and must exit 0 on success. Do not invent commands; if none can be discovered, report needs_input.
{('Previous plan:\n' + previous + '\nUser feedback to apply: ' + feedback) if feedback else ''}
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
    return "verifying"


def untracked(worktree):
    return set(git(worktree, "ls-files", "-o", "--exclude-standard", "-z").split("\0")) - {""}


def verifying(state):
    worktree = Path(state["worktree"])
    before_untracked = untracked(worktree)
    before_tracked = git(worktree, "diff", "HEAD")
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
    if git(worktree, "diff", "HEAD") != before_tracked:
        raise Blocked("verification commands modified tracked files")
    failed = [r for r in results if r["exit"] != 0]
    if not failed:
        return "reviewing"
    state["problems"] = [f"`{r['cmd']}` exited {r['exit']}:\n{r['tail']}" for r in failed]
    return next_fix(state, "verification failed")


def changed_files(worktree):
    git(worktree, "add", "-A")
    names = git(worktree, "diff", "--cached", "--name-only").splitlines()
    git(worktree, "reset", "-q")
    return set(names)


def reviewing(state):
    worktree = Path(state["worktree"])
    diff_file = run_dir(state["id"]) / "review.diff"
    git(worktree, "add", "-A")
    diff_file.write_text(git(worktree, "diff", "--cached", state["base_sha"]), encoding="utf-8")
    git(worktree, "reset", "-q")
    prompt = f"""Independent read-only review. Do not edit files and do not run commands that write.
Repository: {worktree}. Approved plan: {run_dir(state['id']) / 'plan.md'}. Full diff: {diff_file}.
Check correctness, security, regressions, scope versus the plan, and missing tests. Re-read every line you cite.
Report only verified problems introduced by this diff. Put them in "findings" as
{{"severity": "blocker|important|nit", "file": "<repo-relative path>", "line": N, "claim": "...", "fix": "..."}}.
Use status "done" when the review itself completed, even if there are findings.
{RESULT_CONTRACT}"""
    _, result = run_agent(state, "review", prompt)
    files = changed_files(worktree)
    findings = [f for f in result.get("findings") or [] if isinstance(f, dict)]
    serious = [f for f in findings if f.get("severity") in ("blocker", "important") and f.get("file") in files]
    state["findings"] = findings
    if not serious:
        return "publishing"
    state["problems"] = [f"[{f['severity']}] {f['file']}:{f.get('line')} {f.get('claim')} Fix: {f.get('fix')}" for f in serious]
    return next_fix(state, "review found blocker/important issues")


def next_fix(state, why):
    if state.get("fix_rounds", 0) >= 1:
        raise Blocked(f"{why} after the single fix round:\n" + "\n".join(state["problems"]))
    return "fixing"


def fixing(state):
    state["fix_rounds"] = state.get("fix_rounds", 0) + 1
    problems = "\n".join(f"- {p}" for p in state["problems"])
    prompt = f"""Read {skill('qk-cook')}. Fix only the problems below in {state['worktree']}, with the smallest change,
staying within the approved plan {run_dir(state['id']) / 'plan.md'}. Do not weaken tests or checks.
Problems:
{problems}
{CLEAN}
{NO_GIT}
{RESULT_CONTRACT}"""
    run_agent(state, "impl", prompt)
    return "verifying"


def plan_title(state):
    plan = (run_dir(state["id"]) / "plan.md").read_text(encoding="utf-8")
    for line in plan.splitlines():
        if line.startswith("# "):
            return line[2:].strip()[:72]
    return state["task"].splitlines()[0][:72]


def pr_body(state):
    plan = (run_dir(state["id"]) / "plan.md").read_text(encoding="utf-8")
    checks = "\n".join(f"- `{r['cmd']}` → exit {r['exit']}" for r in state.get("verify_results", []))
    findings = state.get("findings") or []
    remaining = "\n".join(f"- [{f.get('severity')}] {f.get('file')}:{f.get('line')} {f.get('claim')}" for f in findings) or "- none"
    return (f"## Task\n\n{state['task']}\n\n## Verification (run by qk-run)\n\n{checks}\n\n"
            f"## Independent review ({state['review']})\n\nRemaining findings:\n{remaining}\n\n"
            f"Fix rounds: {state.get('fix_rounds', 0)}\n\n<details><summary>Approved plan</summary>\n\n{plan}\n\n</details>\n")


def publishing(state):
    worktree = Path(state["worktree"])
    if not state.get("commit"):
        git(worktree, "add", "-A")
        if not git(worktree, "diff", "--cached", "--name-only"):
            raise Blocked("nothing to commit")
        git(worktree, "commit", "-q", "-m", plan_title(state))
        state["commit"] = git(worktree, "rev-parse", "HEAD")
        save(state)
    if not state.get("pushed"):
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
                                 "--title", plan_title(state), "--body-file", str(body)).splitlines()[-1]
        save(state)
    print(f"\nPR ready for review: {state['pr_url']} (head {state['commit']})")
    return "done"


STAGES = {"preflight": preflight, "planning": planning, "implementing": implementing,
          "verifying": verifying, "reviewing": reviewing, "fixing": fixing, "publishing": publishing}


def advance(state):
    while state["stage"] in STAGES:
        stage = state["stage"]
        try:
            state["stage"] = STAGES[stage](state)
        except Blocked as error:
            state.update(stage="blocked", blocked_at=stage, reason=str(error))
            save(state)
            log(state, f"BLOCKED at {stage}: {error}")
            print(f"Resume after fixing the cause: qk-run resume {state['id']}")
            return 1
        save(state)
    return 0


# ---------------------------------------------------------------- CLI


def cmd_start(args):
    for spec in (args.impl, args.review):
        parse_spec(spec)
    if family(args.impl) == family(args.review):
        sys.exit(f"qk-run: implementer and reviewer must be different model families ({family(args.impl)})")
    run_id = time.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)
    state = {"id": run_id, "task": args.task, "slug": slugify(args.task), "repo": str(Path(args.repo).resolve()),
             "impl": args.impl, "review": args.review, "timeout": args.timeout, "stage": "preflight"}
    run_dir(run_id).mkdir(parents=True, exist_ok=False)
    save(state)
    print(f"qk-run {run_id}")
    return advance(state)


def cmd_approve(args):
    state = load(args.id)
    if state["stage"] != "awaiting_approval":
        sys.exit(f"qk-run: run is {state['stage']}, not awaiting_approval")
    state["stage"] = "implementing"
    save(state)
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
    save(state)
    return advance(state)


def cmd_status(args):
    state = load(args.id)
    keys = ("id", "stage", "reason", "branch", "worktree", "fix_rounds", "pr_url", "commit")
    print(json.dumps({k: state[k] for k in keys if k in state}, ensure_ascii=False, indent=2))
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
