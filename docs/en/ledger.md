# Evidence ledger and the `qk` CLI

[Tiếng Việt](../vi/ledger.md) · [Docs index](README.md) · [CLI](../../scripts/qk.py) · [Store](../../scripts/qk_ledger.py)

The ledger keeps the evidence behind a decision in one local place. It is not a second memory system or permission to merge. `qk brief` orders runs by fixed, printed rules, not a score or a model judgement. Nothing starts a daemon, adds a hook, or loads instructions into your runtime.

## Install from a clone

The skills installer copies skill directories, not the CLI. Keep a qk clone and make its entry point available to non-interactive shells used by agents:

```bash
mkdir -p ~/.local/bin
ln -s /path/to/qk/scripts/qk.py ~/.local/bin/qk
qk --help
```

Use an unused destination; do not replace another executable. Put `~/.local/bin` on the agent's `PATH`. A shell alias works for your own interactive terminal but may not exist in an agent's shell. Python 3.9+ is required; PR sync also needs `gh` authenticated for the relevant repository. Existing runner and eval scripts remain usable.

Start with `qk show --help`, `qk sync --help` or `qk brief --help`. `qk run --help` and `qk eval --help` delegate to the existing [runner](runner.md) and [eval harness](evals.md).

## Storage and privacy

The ledger is `ledger.jsonl` under `$QK_STATE_DIR`, or `$XDG_STATE_HOME/qk`, or `~/.local/state/qk`. Keep it outside repositories, including private ones. Records are local and the file is private to your user. Run and eval artifacts remain in their original state directories; references can stop working if those artifacts are removed or moved.

The store keeps summaries and references, not copies of code, diffs, prompts or raw logs. Verification checks store only their position and exit code; command text stays in the run's referenced `state.json`. Repository names, paths and model claims can still be private. Do not publish the ledger. Use `qk stats --public` for aggregate counts without arbitrary private labels; inspect any output before publishing it.

A torn final line from an append interrupted by a crash or a full disk deliberately makes later reads and writes fail; `qk-run` and `qk_eval` only log a ledger warning. To recover, make sure no `qk-run`, `qk_eval` or `qk` command is running, copy `ledger.jsonl` to a backup, remove only the incomplete final line, then run `qk show` to confirm the file reads again.

`source` identifies who supplied the content; `recorded_by` identifies who collected it. A finding is model-authored even when the runner records it. A `claim` is an unverified model conclusion about an existing record, not a new observation. The `log` interface only accepts claims; this is an interface boundary, not tamper protection against another process with your user permissions. Code collecting a statement does not establish that the statement is true.

## Lessons

Lessons are evidence-backed rules about AI mistakes, stored here as `lesson` records and turned on only after a measurement shows they help. See [Lessons](lessons.md).

## Use the evidence to decide

- `qk sync --backfill` imports stopped runs and every saved eval attempt from their state roots without duplicates (earlier reruns recover grades from `check.json`, with unavailable timing and token totals left unknown), and warns once per missing or malformed eval result directory.
- `qk sync` records only changed PR snapshots, reports recorded and unchanged counts, and leaves the `qk brief` sync timestamp at the last observed change. It only reads GitHub; it never merges, closes or comments. Select the correct account per command with `GH_TOKEN` where necessary; the CLI does not switch your active account.
- `qk brief` reads local evidence without a network call. Read its sync timestamp. Evidence is stale when the PR head differs from the recorded commit; missing sync or commit data is not a clean bill of health.
  Blocked runs are included, with resume and abort commands; the reason line is read from the run's local `state.json`, because the ledger stores only the blocked stage. Cards are ordered high, medium, then low.
  - High: blocked, remaining findings, nonzero verification exits, or sensitive files (CI, dependencies, infrastructure, migrations, auth, secrets, permissions or policy).
  - Medium: a fix round, more than 300 changed lines or 10 files, a differing PR head, never synced, or unknown scope.
  - Low: no rule matched; the matched rule is printed beside the level. These rules do not grant approval.
- `qk log claim --about ID --text "One conclusion"` attaches one model conclusion to an existing event. Get the ID from `qk show --json`; never invent one. Skill use remains within the current session's write authority.

New claims inherit the referenced event's repository and task-kind labels, including when that event is another claim. Repository/task filters therefore keep the related observations together. Existing append-only records are not rewritten; older claims with empty labels remain unclassified.

The compact brief summarizes verification exits as zero/nonzero/unknown and shows a partial claim preview. Use its record IDs with `qk show` for full evidence; `queued-for-fix` is not a confirmed fix.

History counts `done` runs, not proven-correct changes. A merged PR is an observed human action, not proof that no defect remains. Older runs lack complete review history; an absent finding in a later review does not prove a fix. Eval records retain every attempt, including an initial result that caused a rerun.

The [store tests](../../tests/test_qk_ledger.py) and [CLI tests](../../tests/test_qk_cli.py) own the persistence and decision-boundary checks. Runtime smoke evidence belongs in [Test evidence](evidence.md), not in a support promise.
