# Overnight runs

[Tiếng Việt](../vi/overnight.md) · [Docs index](README.md) · [Runner](runner.md) · [Ledger](ledger.md)

Approve plans in the evening, let the [runner](runner.md) work through them one at a time overnight, and decide on the results in the morning. You need `qk` on your `PATH` (see [Install from a clone](ledger.md#install-from-a-clone)), a primary checkout with no uncommitted changes, and macOS for `caffeinate` and `--notify`. Runner messages print the same subcommands as `qk-run …`; `qk run …` is the same command.

## Evening

1. Start each task. `start` prints the run id as `qk-run <id>`, then plans and stops with `Plan ready: …`:
   ```bash
   qk run start "Add X. Done when <check> passes." --repo <path>
   ```
2. Read `plan.md` in the run directory: `~/.local/state/qk-run/<id>/plan.md` by default, or under `$QK_RUN_STATE_DIR`, or `$XDG_STATE_HOME/qk-run`, when set. Edit it in place, or re-plan with `qk run revise <id> "<feedback>"`.
3. Queue it:
   ```bash
   qk run approve <id> --later
   ```
   `approve` re-reads `plan.md`, refuses a plan without a `qk-verify` block, freezes it as `approved-plan.md`, prints the verify commands that will run and sets the stage to `queued`.
4. Repeat for more tasks. Queued runs execute oldest first.

## Night

```bash
caffeinate -i qk run drain --until 07:00 --notify
```

- One run at a time, oldest queued first. A second `drain` exits with `another drain is already running`.
- `--until 07:00` means the next 07:00 after now. The deadline is checked only before a run starts: the run in progress finishes, then drain prints `Deadline reached; N queued runs left.` Runs not started stay queued for the next drain.
- `--notify` shows one notification for each blocked run and one for the summary. A failed notification only prints a warning.
- The last line is `Drain: X done, Y blocked, Z left queued.` The exit code is 1 if any run blocked.

## Morning

```bash
qk sync
qk brief
```

`qk sync` reads PR state with `gh` and prints `Decision snapshots: N recorded; N unchanged; N failures.` (exit 1 on any failure). `qk brief` prints one card per run. A card for a run that is not blocked shows:

- a title line ending in `RISK: <level> — <rule>; full: qk show --id <id>` (a rule longer than 100 characters is cut);
- `Done`, `Evidence`, `Unchecked`, `History`;
- `Decision: human decision required; …`.

A blocked card shows the title line, then `Done`, `Next` and `History` only. So does a card for a run stopped mid-stage (see [When something goes wrong](#when-something-goes-wrong)).

Cards are ordered high, medium, low; within a level, stopped runs come first, then blocked runs. The first matching rule sets the level, and its text is printed:

- **high:** `stopped at <stage> (runner gone)`, `blocked at <stage>: <reason>`, `<n> blocker/important findings remain` (nit findings do not count; a run recorded before severity was kept shows `<n> findings remain (severity unknown)` and counts every remaining finding), `verify failed (<n> nonzero)`, `sensitive file <path>` (`+N more`). Sensitive means `.github/`, dependency manifests and lockfiles (`package.json`, `*.lock`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Gemfile`, `Dockerfile`, `requirements*.txt`, …), `*.tf`, `migrations/`, or a path containing `auth`, `secret`, `permission` or `policy`.
- **medium:** `fix round used`, `<n> lines changed` (over 300), `<n> files changed` (over 10), `PR head differs from recorded commit`, `never synced`, `scope unknown`.
- **low:** `no rule matched`.

The rules do not grant approval. The brief leaves out aborted runs, runs that are not blocked whose PR is merged or closed, and runs without a PR unless they are blocked or stopped mid-stage. With nothing to show, it prints `No open, unknown or blocked runs recorded.`

### Deciding from the terminal

When stdin and stdout are both a terminal, `qk brief` asks after each card. Piped or redirected, it only prints and makes no network call.

- Not blocked: `[y] merge  [n] leave  [d] diff  [s] skip`. `y` merges with `gh`, and only if the PR head still equals the run's recorded commit: it reads the methods the repository allows, asks which one when there are several, and passes `--match-head-commit`. If the merge does not happen, it prints `qk brief: not merged: <reason>` and asks again. `d` prints the PR diff and asks again. `n` records that you leave the PR.
- Blocked: `[a] abort later  [r] resume later  [s] skip`. These only record your intent; run `qk run abort` or `qk run resume` yourself.
- Stopped mid-stage: `[a] abort later  [s] skip`. `a` only records your intent.
- `s` records nothing. End of input (Ctrl-D) stops the questions; the remaining cards are printed only.

Each choice is written to the ledger as a decision with `source=user`, then prints `Recorded <choice>: <id>`. A recorded choice does not hide the card; a merged PR leaves the brief after the next `qk sync`.

A blocked card shows `Next: qk run resume <id> after fixing the cause, or qk run abort <id>`. Check the cause with `qk run status <id>`. `resume` runs in your terminal, not in a drain. If the run blocked at verifying, reviewing or fixing, your hand fixes are verified and reviewed again (see [Authority](runner.md#authority)). `qk run abort <id>` keeps the worktree; remove it with `git worktree remove`.

## When something goes wrong

- **A drain killed mid-run** (Ctrl-C, a closed terminal, a kill) leaves that run in its in-progress stage. `resume`, `approve` and `drain` all skip it. While a run works, the runner holds `run.lock` in its run directory and the kernel drops it when the process dies, so `qk brief` shows a run in a working stage whose lock is free as `stopped at <stage> (runner gone)`, with `Next: qk run status <id>, then qk run abort <id>`. The free lock shows only that the runner is gone: an agent it started runs in its own session and may still be finishing its turn in the worktree, so check with `ps` before you abort. Only `qk run abort <id>` gets the run out. Abort leaves the branch, a pushed branch and any PR as they are.
- **Quota or login failures** end that run as `blocked`, and drain moves on to the next run, which may block for the same reason.
- **Two tasks at once:** drain never runs two queued runs together, but it does not stop `start`, `approve` without `--later`, or `resume` that you run by hand in another terminal.
- **Sleep:** a sleeping machine pauses the agents and the drain. Keep `caffeinate -i` in front of `drain`.

## Publishing account

The active `gh` account must have push permission on the repository. The runner checks it at `start` and again right before the push during the drain; `gh pr create` also uses that account. `git push` uses git's own credentials, so they must be able to push too; with an SSH origin, the key decides, and the check cannot tell which account owns it. From the qk clone, check without changing anything:

```bash
python3 skills/qk-commit/scripts/qk_preflight.py identity --repo <path>
```

**Way 1: switch the active account.** Run `gh auth switch -u <other-account>` before `start`, keep it through the drain, then `gh auth switch -u <your-account>` afterwards. This covers `git push` only when git gets github.com credentials from `gh auth git-credential`; check with `git config --get-regexp '^credential'`. The switch is global, so every other terminal sees it too.

**Way 2: one terminal only, no global change.** `GH_TOKEN` takes precedence over the stored `gh` login, and the `GIT_CONFIG_*` variables add git config for this shell and its children. The empty helper clears your other credential helpers for github.com:

```bash
export GH_TOKEN="$(gh auth token --user <other-account>)"
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=credential.https://github.com.helper GIT_CONFIG_VALUE_0=
export GIT_CONFIG_KEY_1=credential.https://github.com.helper GIT_CONFIG_VALUE_1='!gh auth git-credential'
```

Run `start`, `drain` and `qk sync` in that terminal. Agents started from it inherit these variables, and implementing agents run in write mode.
