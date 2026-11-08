# qk-run: from request to pull request

[Tiếng Việt](../vi/runner.md) · [Docs index](README.md) · [Source](../../scripts/qk_run.py)

`qk-run` is an opt-in runner that drives one task through the qk skills on Claude Code, Codex or omp, stops once for you to approve the plan, then keeps going until it has opened a verified pull request — or stops as `blocked` with a reason. The skills themselves still never call each other; only this runner chains them, and only when you start it.

## Use

```bash
python3 scripts/qk_run.py start "Add X. Done when <check> passes." --repo <path>
python3 scripts/qk_run.py approve <id>            # after reading the plan
python3 scripts/qk_run.py revise <id> "<feedback>" # replan instead
python3 scripts/qk_run.py status <id>
python3 scripts/qk_run.py resume <id>             # retry a blocked stage
python3 scripts/qk_run.py abort <id>
```

Defaults: implementer `omp:anthropic/claude-opus-5-5`, reviewer `codex:` (Codex's own default model). Override with `--impl runtime:model` and `--review runtime:model`; runtimes are `omp`, `claude`, `codex`. Implementer and reviewer must be different model families. Set `QK_RUN_OMP_PROFILE` to run omp under a named profile. `--timeout` limits each agent turn and each verify command (default 1800 s).

## Stages

1. **preflight** — refuses a dirty primary checkout (never stashes), checks `gh auth`, discovers the base branch, creates a worktree on a new branch `qk/<slug>-<id>`.
2. **planning** — read-only `qk/plan`; the runner saves the plan, which must contain a `qk-verify` block of repository commands.
3. **awaiting_approval** — the only human gate.
4. **implementing** — `qk/cook` in the worktree.
5. **verifying** — the runner itself runs every `qk-verify` command; removes files those commands created; blocks if they change tracked files.
6. **reviewing** — a different model family reviews the full diff read-only and returns structured findings.
7. **fixing** — at most one round for failed checks or blocker/important findings on changed files, then verify and review again.
8. **publishing** — the runner commits (plan title, no AI attribution), pushes the branch and opens a ready-for-review PR with the checks, remaining findings and the plan.

State and logs live outside the repository, in `$XDG_STATE_HOME/qk-run/<id>/` (default `~/.local/state/qk-run/`). The worktree stays there after the run.

## Authority

- Agents only edit files in the worktree. The runner alone commits, pushes and opens the PR.
- The runner blocks when an agent changes `HEAD`, touches the primary checkout, or when a read-only agent changes worktree contents.
- Never merges, releases, tags, deploys, force-pushes, deletes branches or switches models. Quota, login or missing-model failures stop as `blocked`.
- `resume` after publishing does not recommit, repush or open a second PR.

## Limits

- A worktree is not a sandbox. Implementing agents run with their runtime's write mode (`claude --permission-mode acceptEdits` with Bash allowed, `codex exec --sandbox workspace-write`, `omp --approval-mode yolo`), so they can still reach files and network outside the repository.
- Success is defined by the plan's `qk-verify` commands and one cross-model review; weak commands mean weak evidence.
- One task per run; no queue, daemon or parallel runs.

## Verified

On 2026-11-08: 16 unit tests with a scripted agent and real Git repositories cover every transition, the single fix round, blocked commits, read-only violations, dirty checkouts, verification artifacts and resume after a failed PR call. Real end-to-end runs on a private scratch GitHub repository opened ready-for-review PRs containing only the intended files with each implementer: omp (Opus 5.5) reviewed by Codex, Claude Code (Sonnet) reviewed by Codex, and Codex reviewed by omp (Opus 5.5). These are single runs, not certification.
