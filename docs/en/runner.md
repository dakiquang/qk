# qk-run: from request to pull request

[Tiếng Việt](../vi/runner.md) · [Docs index](README.md) · [Source](../../scripts/qk_run.py)

`qk-run` is an opt-in runner that drives one task through the qk skills on Claude Code, Codex or omp, stops once for you to approve the plan, then keeps going until it has opened a verified pull request — or stops as `blocked` with a reason. The skills themselves still never call each other; only this runner chains them, and only when you start it.

## Use

```bash
python3 scripts/qk_run.py start "Add X. Done when <check> passes." --repo <path>
python3 scripts/qk_run.py approve <id>            # after reading the plan
python3 scripts/qk_run.py revise <id> "<feedback>" # replan instead
python3 scripts/qk_run.py status <id>
python3 scripts/qk_run.py resume <id>             # retry a blocked stage as it stands
python3 scripts/qk_run.py abort <id>
```

Requires Python 3.9+ and the `git` and `gh` CLIs. Defaults: implementer `omp:anthropic/claude-opus-5-5`, reviewer `codex:` (Codex's own default model). Override with `--impl runtime:model` and `--review runtime:model`; runtimes are `omp`, `claude`, `codex`. Implementer and reviewer must be different model families; an omp spec needs an explicit model whose family can be recognised (for example `omp:anthropic/claude-opus-5-5`), otherwise `start` refuses it. Set `QK_RUN_OMP_PROFILE` to run omp under a named profile. `--timeout` limits each agent turn and each verify command (default 1800 s).

## Stages

1. **preflight** — refuses a dirty primary checkout (never stashes), checks push permission for the active `gh` account on GitHub origin, discovers the base branch, creates a worktree on a new branch `qk/<slug>-<id>`.
2. **planning** — read-only `qk/plan`; the runner saves the plan, which must contain a `qk-verify` block of repository commands.
3. **awaiting_approval** — the only human gate. You may edit `plan.md` before approving; `approve` re-reads it, prints the verify commands that will run and freezes it as `approved-plan.md`. The reviewer, the fix round and the PR use that frozen copy, and the run blocks if it changes.
4. **implementing** — `qk/cook` in the worktree.
5. **verifying** — the runner itself runs every `qk-verify` command, removes files those commands created, and blocks if they changed any other worktree content (tracked or new files).
6. **reviewing** — a different model family reviews the full diff read-only and returns structured findings.
7. **fixing** — at most one round for failed checks or blocker/important findings on changed files, then verify and review again.
8. **publishing** — the runner commits (plan title, no AI attribution), pushes the branch and opens a ready-for-review PR with the checks, the problems addressed in the fix round, remaining findings and the approved plan.

State and logs live outside the repository, in `$XDG_STATE_HOME/qk-run/<id>/` (default `~/.local/state/qk-run/`). The worktree stays there after the run.

## Authority

- Agents only edit files in the worktree. The runner alone commits, pushes and opens the PR.
- The runner blocks when the worktree leaves the run branch or its HEAD moves away from the runner's commit, when an agent changes the primary checkout's branch, HEAD or files, or when a read-only agent changes worktree contents. These checks also run when the agent call itself fails or times out.
- The worktree's branch, HEAD and expected contents are stored, not re-captured: `resume` after such a block stays blocked until the worktree is restored, so a violating commit or edit cannot be published by resuming. Hand edits to the worktree after a block also keep it blocked; to change the work, `abort` and start a new run. The primary checkout is compared only across each agent turn, so leave it untouched while an agent runs; a change made by you between turns does not block.
- Never merges, releases, tags, deploys, force-pushes, deletes branches or switches models. Quota, login or missing-model failures stop as `blocked`.
- `resume` after publishing does not recommit, repush or open a second PR.

## Limits

- A worktree is not a sandbox. Implementing agents run with their runtime's write mode (`claude --permission-mode acceptEdits` with Bash allowed, `codex exec --sandbox workspace-write`, `omp --approval-mode yolo`), so they can still reach files and network outside the repository.
- Success is defined by the plan's `qk-verify` commands and one cross-model review; weak commands mean weak evidence.
- One task per run; no queue, daemon or parallel runs.

## Verified

On 2026-11-08: 30 unit tests with a scripted agent and real Git repositories, run on Python 3.9 and 3.12+, cover the main path, the single fix round (verification failure and a second serious review both block without publishing; a fixer updating the plan status still publishes), agent commits and branch switches, commits in the primary checkout, read-only violations and their resume, verification artifacts and mutations, plan edits before approval and the frozen approved plan, model-family checks, dirty checkouts, existing branches and PRs, and resume after a failed PR call. Real end-to-end runs on a private scratch GitHub repository opened ready-for-review PRs containing only the intended files with each implementer: omp (Opus 5.5) reviewed by Codex, Claude Code (Sonnet) reviewed by Codex, and Codex reviewed by omp (Opus 5.5). After the review fixes, the default omp/Codex pair was rerun once with the same result. These are single runs, not certification.
