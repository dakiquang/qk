# qk-run: from request to pull request

[Tiếng Việt](../vi/runner.md) · [Docs index](README.md) · [Source](../../scripts/qk_run.py)

`qk-run` is an opt-in runner that drives one task through the qk skills on Claude Code, Codex or omp, stops once for you to approve the plan, then keeps going until it has opened a verified pull request — or stops as `blocked` with a reason. The skills themselves still never call each other; only this runner chains them, and only when you start it.

## Use

```bash
python3 scripts/qk_run.py start "Add X. Done when <check> passes." --repo <path>
python3 scripts/qk_run.py approve <id>            # after reading the plan
python3 scripts/qk_run.py revise <id> "<feedback>" # replan instead
python3 scripts/qk_run.py status <id>
python3 scripts/qk_run.py resume <id>             # retry a blocked stage, or verify your hand fix
python3 scripts/qk_run.py abort <id>
```

Requires Python 3.9+ and the `git` and `gh` CLIs. Defaults: implementer `omp:anthropic/claude-opus-5-5`, reviewer `codex:` (Codex's own default model). Override with `--impl runtime:model` and `--review runtime:model`; runtimes are `omp`, `claude`, `codex`. Implementer and reviewer must be different model families; an omp spec needs an explicit model whose family can be recognised (for example `omp:anthropic/claude-opus-5-5`), otherwise `start` refuses it. Set `QK_RUN_OMP_PROFILE` to run omp under a named profile. `--timeout` limits each agent turn and each verify command (default 1800 s). `--read-only-mcp NAME` (repeatable, Claude and omp only) lets read-only stages call the MCP server `NAME`; see [Isolation](#isolation). `start` refuses it when Codex would run planning (`--impl`) or review (`--review`).

## Stages

1. **preflight** — refuses a dirty primary checkout (never stashes), checks push permission for the active `gh` account on GitHub origin, discovers the base branch, creates a worktree on a new branch `qk/<slug>-<id>`.
2. **planning** — read-only `qk/plan`; the runner saves the plan, which must contain a `qk-verify` block of repository commands.
3. **awaiting_approval** — the only human gate. You may edit `plan.md` before approving; `approve` re-reads it, prints the verify commands that will run and freezes it as `approved-plan.md`. The reviewer, the fix round and the PR use that frozen copy, and the run blocks if it changes.
4. **implementing** — `qk/cook` in the worktree.
5. **verifying** — the runner itself runs every `qk-verify` command, removes files those commands created, and blocks if they changed any other worktree content (tracked or new files).
6. **reviewing** — a different model family reviews the full diff read-only and returns structured findings.
7. **fixing** — at most one round for failed checks or blocker/important findings on changed files, then verify and review again.
8. **publishing** — the runner commits with the approved plan's title (no AI attribution). The runner adds a conventional type (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`) and lowercases the first letter (acronyms such as `README` or `CI` keep their case) when most of the base branch's last 20 non-merge commit subjects follow `type(scope): subject`. It then pushes the branch and opens a ready-for-review PR with the same title, the checks, the problems addressed in the fix round, remaining findings and the approved plan. It re-checks push permission immediately before pushing.

State and logs live outside the repository, in `$XDG_STATE_HOME/qk-run/<id>/` (default `~/.local/state/qk-run/`). The worktree stays there after the run.

While an agent runs, the runner prints each of its tool actions as one line (`read <path>`, `edit <path>`, `write <path>`, `run <command>`, with ` -> exit <code>` when the runtime reports it) and `still running (<n>s, last: <action>)` after every 60 s without events. MCP calls show as `mcp <identifier>` with the runtime's full tool identifier (for example `mcp mcp__aws_mcp_aws_run_script`), and other omp runtime devices as `tool <name>` (for example `tool report_issue`), never as `write xd://...`. When the agent's stream ends, the runner logs its token usage as `tokens in=<n> cached=<n> out=<n>`, plus ` cost=$<x>` when the runtime reports it; `in` includes cached tokens. The same numbers go to `state.json` under `usage`, one list per stage with the agent spec. Compare them only within one runtime: each counts cache differently. The raw events of each turn go to `<stage>-<ts>-<id>.events.jsonl` next to `<stage>-<ts>-<id>.out.md`, and the runner's own log is `run.log`, both in the run directory; `status` prints the run directory and the last 10 log lines. When `--timeout` elapses, the runner sends SIGTERM to the agent's process group, SIGKILL after 10 s, and the run blocks.

## Isolation

Agents do not load your globally installed skills; the runner still points them at the qk skill they need by path. Read-only stages (planning and review) also run without MCP:

- **Claude**: every stage gets `--disable-slash-commands`. Read-only stages also get `--strict-mcp-config` with no config, so no MCP server starts; `--read-only-mcp` drops that flag. Write stages keep your MCP setup.
- **omp**: every stage gets `--no-skills --no-extensions --no-rules`; repository context files such as `AGENTS.md` still load. omp cannot turn MCP off in advance, so the guard below stops it.
- **Codex**: each run gets a private home, `<run dir>/codex-home`, created on the first Codex turn and reused after that. Codex runs with `HOME=<run dir>/codex-home` and `CODEX_HOME=<run dir>/codex-home/.codex`. Its `config.toml` keeps only the top-level `model` and `model_reasoning_effort` lines of your real config (`$CODEX_HOME`, default `~/.codex`), and `auth.json` is a symlink to your real one, so Codex stays logged in but sees no user skills or MCP servers. `UV_CACHE_DIR` and `UV_PYTHON_INSTALL_DIR` point to uv's usual locations under your real home unless you have set them.

Read-only guard: in a read-only stage, the first tool call whose name contains `mcp__` or starts with `xd://` or `mcp://`, or whose top-level argument starts with `xd://` or `mcp://`, makes the runner stop the agent's process group and block with `read-only stage called <action>`, for example `read-only stage called mcp mcp__aws_mcp_aws_run_script`. Tools of a server listed with `--read-only-mcp NAME` pass: the tool identifier, with every character other than a letter or digit read as `_`, must start with `mcp__<NAME>_`. `xd://report_issue` and `mcp://` resources never pass.

## Authority

- Agents only edit files in the worktree. The runner alone commits, pushes and opens the PR.
- The runner blocks when the worktree leaves the run branch or its HEAD moves away from the runner's commit, when an agent changes the primary checkout's branch, HEAD or files, or when a read-only agent changes worktree contents. These checks also run when the agent call itself fails or times out.
- The worktree's branch, HEAD and expected contents are stored, not re-captured: `resume` after such a block stays blocked until the worktree is restored, so a violating commit or edit cannot be published by resuming. The primary checkout is compared only across each agent turn, so leave it untouched while an agent runs; a change made by you between turns does not block.
- Hand fixes: when a run blocks at `verifying`, `reviewing` or `fixing`, the runner records the worktree as it was at the block. If you then edit files and `resume`, the runner logs `manual changes recorded: <files>`, takes your worktree as the new implementation and continues at `verifying`, so your fix is verified and reviewed again. This does not reset the single fix round. It applies only when the blocked stage left the worktree as recorded, or was `fixing`. If a read-only agent or a verify command changed the worktree, your extra edits are not accepted and the run stays blocked until the worktree is restored.
- Never merges, releases, tags, deploys, force-pushes, deletes branches or switches models. Quota, login or missing-model failures stop as `blocked`.
- `resume` after publishing does not recommit, repush or open a second PR.

## Limits

- A worktree is not a sandbox. Implementing agents run with their runtime's write mode (`claude --permission-mode acceptEdits` with Bash allowed, `codex exec --sandbox workspace-write`, `omp --approval-mode yolo`), so they can still reach files and network outside the repository.
- Success is defined by the plan's `qk-verify` commands and one cross-model review; weak commands mean weak evidence.
- The commit and PR title use the approved plan's title, and the PR body includes the whole approved plan. In a repository that follows Conventional Commits, the type comes from the plan title's first word (`fix`, `docs`, `test`, `refactor` and their variants) and otherwise defaults to `feat`; a plan title that is already conventional is kept as written; a non-conventional `<word>: ` prefix (a project name, but also a ticket prefix such as `ABC-123: ` or a capitalised `Fix: `) is dropped before the type is added; merge commits are not counted. Titles longer than 72 characters are cut at a word boundary. Other conventions (scopes, other casing rules) are not detected, so edit the plan title before `approve` or adjust the title when merging.
- One task per run; no queue, daemon or parallel runs.
- omp MCP is stopped only after its first call in a read-only stage: that call has already run when the guard stops the agent.
- `--read-only-mcp` matches by prefix, so `aws` also allows `aws-mcp`; use full server names.
- Under the private Codex home, tools that Codex runs do not see your `~/.gitconfig`, `gh` login or other configuration in your home directory.

## Evidence

The runner's behaviour is covered by [`tests/test_qk_run.py`](../../tests/test_qk_run.py), which drives it with a scripted agent against real Git repositories. Real end-to-end runs are recorded in [Test evidence](evidence.md#qk-run-runner).
