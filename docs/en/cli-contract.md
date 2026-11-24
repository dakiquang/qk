# CLI contract for external tools

[Tiếng Việt](../vi/cli-contract.md) · [Docs index](README.md) · [CLI](../../scripts/qk.py) · [Contract tests](../../tests/test_contract_v1.py)

A small part of the `qk` CLI is a versioned contract that tools outside this repository may rely on: run one isolated agent turn, record a run they stopped, and measure themselves on qk's eval cases. Everything else in qk can change without notice. qk does not know who calls it; a caller names itself only where it writes to the ledger.

Each contract command does one thing and exits. None of them runs another in sequence or keeps multi-step state, and none commits, pushes, opens a pull request or merges in a repository you give it; the only commit is the base commit `qk eval prepare` makes in the new case repository it creates. Orchestration belongs to the caller.

## Rules

- Contract version: `qk contract --json` prints it. This page describes version **1**.
- Machine output is one JSON object on stdout when `--json` is given. Progress and messages for people go to stderr.
- JSON from the new commands carries `"contract": 1`. `qk show --json` and `qk lesson list --json` keep their existing output.
- Exit codes: `0` done; `2` blocked, or input rejected (nothing ran, nothing was recorded); `1` any other error.
- Pin qk by tag and commit, and call `qk contract --json` at start-up to check the version and the command list.

## Commands

| Command | Use |
|---|---|
| `qk contract [--json]` | Contract version, qk version and the contract commands this build has |
| `qk show --json [--kind K] [--id ID] [--repo R] [--since 7d]` | Read ledger records (fields `v`, `id`, `kind`, `at`, `source`, `recorded_by`, `repo`, `task_kind`, `refs`, `data`) |
| `qk lesson list --json` | Read the latest state of each lesson |
| `qk agent run …` | One non-interactive agent turn |
| `qk agent family SPEC [--json]` | Model family of a `runtime:model` spec |
| `qk log run …` | Record a run another tool stopped |
| `qk eval prepare …`, `qk eval grade …` | Build and grade an eval case without running an agent |
| `qk brief --json`, `qk brief --pending` | Read the brief's cards without asking anything or calling the network. `--json`: `{"contract": 1, "cards": [...]}`; each card has `run_id`, `repo`, `title`, `pr_url`, `status`, `level`, `rule`, `lines` (the brief's own text), `choices` (what `qk decide` accepts) and `decided`. `--pending`: one line when cards wait for a decision, otherwise nothing |

`qk brief` without these flags, and `qk decide`, are for the person who decides. A tool runs `qk decide` only on the person's own stated choice ([Overnight runs](overnight.md#deciding-from-the-terminal)).

### `qk agent run`

```text
qk agent run --spec RUNTIME:MODEL --cwd DIR (--write | --read-only)
             [--add-dir DIR]... [--timeout SECONDS] [--read-only-mcp NAME]...
             [--no-result-contract] [--no-git-rules]
             [--lessons plan|impl|review [--repo NAME]]
             [--events FILE] [--json]   < prompt
```

- The prompt comes from stdin. qk appends the result contract (a `qk-result` block), and with `--write` also the no-git and clean-up rules; the two `--no-…` flags turn these off. `--lessons` appends active, measured lessons for that stage.
- Isolation is the runner's: no user skills; a `--read-only` turn has no MCP except the servers named with `--read-only-mcp`, and calling another one stops the turn as `blocked`.
- Each turn has its own scratch directory (Codex's private home, the last-message file), removed when the turn ends, so two turns at once share nothing. `--cwd` and `--add-dir` are made absolute first.
- SIGTERM stops the agent's process group, removes the scratch directory and reports `blocked` with exit 2.
- It never touches git. The caller checks the working tree afterwards.

Output:

```json
{"contract": 1, "status": "done", "reason": "", "family": "anthropic", "spec": "claude:",
 "result": {"status": "done", "summary": "…", "files": [], "evidence": [], "reason": "", "findings": []},
 "text": "…", "usage": {"input": 15, "cached": 4, "output": 7}, "limit": null, "lessons": [], "events": null,
 "seconds": 12}
```

`status` is `done`, `blocked` or `needs_input`. A missing runtime, a timeout, a non-zero exit and an isolation breach are all `blocked` with a `reason`. `result` is `null` when the result contract is off or the reply has no valid block. `usage` is `null` when the runtime reports no tokens and may lack `cost_usd` (Codex reports none). `limit` is `null` unless the runtime exited because of its usage limit; then `status` is still `blocked` and `limit` is `{"runtime": "claude", "reset_at": "2026-11-23T23:50:00+07:00", "message": "…"}`, where `reset_at` is ISO 8601 or `null` when the message names no reset time.

### `qk agent family SPEC`

Prints the family (`anthropic`, `openai`, `google`, `xai`) by the rule qk-run uses to keep the implementer and the reviewer apart. With `--json`: `{"contract": 1, "spec": "…", "family": "…"}`. An unknown family exits 2.

### `qk log run`

```text
qk log run --producer "NAME VERSION" --state-dir DIR [--json]   < state.json
```

Records a stopped run and its findings through the same projection qk-run uses, so it shows in `qk show`, `qk stats` and `qk brief`. Input on stdin:

| Field | Required | Notes |
|---|---|---|
| `id` | yes | The caller's run id |
| `stage` | yes | `done`, `blocked` or `aborted` |
| `repo` | yes | Absolute path of the repository; the ledger stores its last directory name, and `qk brief` runs `gh` from it |
| `task`, `task_kind` | no | `task` is cut to 120 characters |
| `impl`, `review` | no | Text labels; several models joined by commas |
| `commit`, `pr_url` | no | `qk brief` shows the PR; `qk decide` re-reads its head before merging |
| `verify_results` | no | List of `{"exit": integer}` |
| `usage` | no | By stage; only the runner's stage names are kept: `preflight`, `planning`, `implementing`, `verifying`, `reviewing`, `fixing`, `publishing` |
| `fix_rounds`, `findings`, `addressed` | no | Findings carry `severity`, `class`, `file` and `line` |
| `diff_stat` | no | `{"files": [], "added": n, "deleted": n}` |
| `blocked_at` | when blocked | Stage name only; the ledger keeps no reason text |
| `limited` | no | When blocked by a usage limit: `{"runtime": "…", "reset_at": "ISO 8601" or null}`; `qk brief` then shows `waiting for <runtime> limit until HH:MM` |
| `ledger_revision` | no | Raise it when recording a later state of the same run |

- `--state-dir` is the caller's directory for this run: it must exist outside any repository and hold `state.json`, which the record points to. Its path identifies the run, so later snapshots of the same run replace earlier ones in `qk brief`.
- `--producer` is stored as `data.producer` (one line, at most 100 characters). A blocked card for such a run names the producer instead of suggesting `qk run resume`.
- Rejected input exits 2 and records nothing. The same input twice adds nothing.
- Output: `{"contract": 1, "id": "<run record id>", "findings": n}`; without `--json`, the record id.

### `qk eval prepare` and `qk eval grade`

```text
qk eval prepare CASE DIR [--json]
qk eval grade   CASE WORKDIR [--final FILE] [--events FILE] [--json]
```

- `prepare` builds the case's Git repository in `DIR/repo` exactly as `qk-eval` does: the base committed, and for a review case the change applied uncommitted. It returns `{"contract": 1, "case", "skill", "write", "workdir", "task", "plan", "diff"}`: `task` for a task case, `plan` and `diff` (copied next to the repository, outside the case directory) for a review case. `DIR/repo`, and for a review case `DIR/plan.md` and `DIR/review.diff`, must not exist.
- `grade` runs the case's `check.py` from a private copy, on a throwaway copy of `WORKDIR` (graders may stage and reset files) with the final reply and the events side by side as `qk-eval` lays them out, and returns `{"contract": 1, "case", "criteria": [{"name", "passed", "detail"}], "passed"}`. `--final` is the agent's last reply (empty by default). `--events` is the turn's raw events: some graders read them, and they add the `clean` criterion, which fails when the events name the case directory. A `--final` or `--events` path that is not a file exits 2. A case that fails its criteria still exits 0; read `passed`.
- Neither runs an agent, writes the baseline or records anything. The old `qk eval --case/--skill/--all` flags are unchanged.

## Formats in the contract

| Format | Content |
|---|---|
| `qk-result` block | JSON in a ```` ```qk-result ```` fence: `status` (`done`, `blocked`, `needs_input`), `summary`, `files`, `evidence`, `reason`, `findings` |
| `qk-verify` block | A ```` ```qk-verify ```` fence, one shell command per line; success is exit 0 |
| Plan | Text between `<<<QK-PLAN` and `QK-PLAN>>>` |
| `skills/<name>/SKILL.md` | Read from the pinned qk checkout |

Callers parse these blocks themselves.

## Versioning

- Compatible, same version: a new command, a new optional flag, a new JSON field.
- Breaking, new version and a CHANGELOG entry: removing or renaming a command, flag or field; changing a field's meaning, an exit code or a block format.
- `tests/test_contract_v1.py` compares output with the samples in `tests/fixtures/contract/`. Changing a sample is a contract decision, not a test fix.

Not in the contract: Python functions in `scripts/`, qk-run's state machine and state directory, ledger file names, internal prompt wording, and every command not listed above.
