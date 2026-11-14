# qk-eval: before/after checks for skills and the runner review

[Tiếng Việt](../vi/evals.md) · [Docs index](README.md) · [Source](../../scripts/qk_eval.py)

`qk-eval` runs a few fixed tasks through one runtime and grades each result by code, not by a model. Use it before and after you change a skill or the runner's review step: it shows which criteria pass, how many tokens the run used and how long it took, and compares that with the recorded baseline.

## Use

```bash
python3 scripts/qk_eval.py --case csv-export --runtime omp:anthropic/claude-opus-5-5
python3 scripts/qk_eval.py --skill qk-debug --runtime codex:
python3 scripts/qk_eval.py --all --runtime claude:opus
python3 scripts/qk_eval.py --all --runtime codex: --update-baseline
```

Pick exactly one of `--case NAME`, `--skill NAME` (every case of that skill, or `runner-review`) and `--all`. `--runtime` takes the same `runtime:model` spec as [qk-run](runner.md). `--timeout` limits each agent turn (default 1800 s). An unknown case, or a selection with no cases, exits 2. Requires Python 3.9+ and `git`.

## Cases

Cases live in `evals/cases/<name>/`. Each one runs as a single agent turn in a fresh temporary git repository: the case's `repo/` is committed as the base, and the agent works there.

| Case | Runs | Graded criteria |
|---|---|---|
| `csv-export` | `qk-cook` on `task.md`, with write access | `hidden-tests` (hidden acceptance tests for the CSV contract), `repo-tests`, `scope` (only the new module and its test file change), `csv-module` (the module writes with `csv.writer` or `csv.DictWriter`), `report` |
| `pagination-empty-page` | `qk-debug` on `task.md`, with write access | `hidden-regression` (an empty page that still has a marker no longer ends the listing), `repo-tests`, `test-catches-bug` (the repository's tests fail once the original module is put back, and pass with a correct module), `scope` (only `collector/collect.py` and test files change), `report` |
| `waf-bundle-review` | the runner's review prompt, read-only, on the real `waf-upgrade-check` pull request that added the AWS MCP bundle mode (about 1,200 added lines in 10 files), with the eight defects its real review needed several rounds to find put back | `result`, one criterion per defect (`pagination-empty-page`, `rules-not-list`, `priority-type`, `nested-statement`, `capacity-type`, `label-name-type`, `listed-version-name`, `caller-account-check`: a blocker or important finding on the right file that names the field and what is wrong with it), `no-outside-important` |
| `bundle-malformed` | the runner's review prompt (`qk_run.review_prompt`), read-only, on an uncommitted diff | `result` (a valid `qk-result` with status `done`), `capacity`, `nested-statement`, `list-name` (a blocker or important finding on each of three missed validation checks, at the right lines and naming the field and what is wrong with it), `no-outside-important` (no blocker or important finding on a file outside the diff) |

Every case also gets `clean`, added by the harness: it fails when the turn's events name the case directory (`evals/cases/`), because the agent may have read the graders. The graders (`check.py`, `hidden/`) are copied to a private directory before the turn and run from that copy, so an agent with write access cannot change what grades it.

`report` passes when the final reply contains the labels `Done`, `Evidence`, `Not verified` and `Needs your decision`, each at the start of a line and followed by `:` (bold or not). Each case's `check.py` prints its criteria as JSON; a `check.py` that crashes, times out or prints something else counts as one failed criterion named `check.py`.

## Reading the result

```text
case                   criteria                                   result    tokens    time
csv-export             hidden-tests, repo-tests, scope=FAIL, csv-module, report    FAIL(1)   212,400   3m10s
vs baseline csv-export (2026-11-20): 5/5 → 4/5, lost: scope; tokens -6.0%; time +4.0%; rerun: yes
verdict: regression (criterion lost: csv-export/scope)
```

- Each failed criterion is marked `=FAIL` in the criteria column. `result` is `PASS`, `FAIL(n)` with the number of failed criteria, or `ERROR` when the agent call failed (missing binary, timeout, non-zero exit).
- `tokens` is input plus output tokens of the turn; input already includes cached tokens. It shows `n/a` when the runtime reported no usage.
- Without a baseline entry for the runtime, the comparison line reads `no baseline for <spec>` and nothing can regress.

## What counts as a regression

The exit code is 1 when any of these happens, and the verdict line names each reason:

- **Criterion lost:** a criterion that passed in the baseline fails now or is missing.
- **Tokens:** more than 10% above the baseline of the same case and runtime (+10% is still fine, +11% is not). Time is reported but never fails the run.
- **Agent error:** any case whose agent call failed. `check.py` still runs on whatever the agent left.

When the set of passing criteria differs from the baseline in either direction, that case is rerun once at once and the second run counts. A change in tokens alone does not trigger a rerun. Only the same runtime spec is ever compared.

## Updating the baseline

`evals/baseline.json` stores, per runtime spec and case, the date, each criterion's result, the tokens and the seconds. `--update-baseline` first prints the normal comparison, then records the counted result of every selected case for that runtime and exits 0. Other cases and other runtimes stay as they were. A case with an agent error is never recorded; the command lists it and exits 1.

Update the baseline only after you have looked at a changed result and accepted it on purpose — never to make a lost criterion disappear. Record one runtime at a time.

## Results on disk

Each run writes to `$XDG_STATE_HOME/qk-eval/<YYYYmmdd-HHMMSS>-<hex>/` (default `~/.local/state/qk-eval/`):

```text
results.json                  runtime, start time, counted result per case, regression flag
<case>/run-1/events.jsonl     raw runtime events of the turn
<case>/run-1/final.md         the agent's final reply
<case>/run-1/check.json       the graded criteria
<case>/run-1/plan.md          review case only: the approved plan and diff the reviewer was given
<case>/run-1/review.diff
<case>/run-2/...              only when the case was rerun
```

The temporary repository is deleted after grading. Codex also keeps its private home in the run directory.

## Cost and limits

Each case is one full agent turn, which can use hundreds of thousands of tokens. Run a single `--case` or `--skill` while you iterate, and `--all` before you accept a change. Nothing runs in CI.

The skill path in the prompt is absolute, so an agent can still read the rest of the qk checkout, including `evals/cases/*/check.py` and `hidden/`. Such a turn fails `clean`; it cannot change the graders, because they run from a copy taken before the turn. `--update-baseline` never records a case whose agent call or `check.py` failed.

Harness behaviour is covered by [`tests/test_qk_eval.py`](../../tests/test_qk_eval.py), which uses a scripted agent; it also checks that each case's repository passes its own tests and that the graders fail an untouched copy.
