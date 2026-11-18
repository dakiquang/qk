# Lessons: measured rules about AI mistakes

[Tiếng Việt](../vi/lessons.md) · [Docs index](README.md) · [CLI](../../scripts/qk.py) · [Store](../../scripts/qk_ledger.py)

A lesson is one imperative rule, written after an AI agent made the same mistake at least twice. It lives in the [evidence ledger](ledger.md) as append-only `lesson` records; the latest record for a lesson ID is its state. A lesson reaches an agent only when you pass `--lessons`, and only after a measurement shows that it helps.

## Why measure first

Writing rules down is cheap; knowing whether they work is not. A study [reported here](https://levelup.gitconnected.com/stop-teaching-your-ai-agent-the-wrong-lessons-c1a6c980e713) found that machine-written instruction files did not meaningfully raise task success on two benchmarks and raised inference cost by 20–23% (we have not read the original paper; it covers only the agents and tasks in that study). Memory and learning features in other tools check that a lesson still matches the code, or let a person approve it, but none we found measures whether the lesson makes the agent miss less before turning it on.

qk does that measurement with the tools it already has: a code-graded [eval case](evals.md) that reproduces the mistake, run with and without the lesson. A lesson that does not help is a valid result, not a failure of the process.

qk's [first lesson](evidence.md#first-lesson) is an example: on Codex it missed 1 of 2 runs with the lesson and 1 of 2 without, so it was dismissed.

## Lifecycle

| Step | Command | Who |
|---|---|---|
| Find repeated mistakes | `qk lesson suggest` (reads only) | code |
| Propose | `qk lesson propose --class TEXT --rule TEXT --scope stage:review --evidence ID --evidence ID --case NAME` | model or person; recorded as `source: model` |
| Measure | `qk lesson measure ID --runtime SPEC` | code; recorded as `source: code` |
| Turn on or drop | `qk lesson decide ID active` or `dismissed` | you; recorded as `source: user` |
| Use | `qk run start --lessons`, `qk eval --lessons` | you choose per run |
| Remove or promote | `qk lesson decide ID retired` or `promoted` | you |
| Inspect | `qk lesson list` | anyone |

A proposal needs:

- `rule`: one line, at most 300 characters, saying what the agent must do. Write the general habit, not the answer to the eval case, or the measurement only shows that the agent can copy a hint.
- `scope`: 1–3 entries, at least one of `stage:review`, `stage:impl`, `stage:plan`; add `repo:NAME` to limit it to one repository.
- `evidence`: at least two distinct existing `eval` or `finding` IDs where the mistake happened.
- `case`: an existing directory under `evals/cases/` that reproduces the mistake.

## How measurement decides

`qk lesson measure` runs the lesson's case twice without and twice with the lesson, then every other case of the same stage once with it as a control. Controls are compared with the runtime's baseline; when the baseline has no entry for that runtime, one run without the lesson stands in. Target criteria are the ones the lesson's evidence failed on its case.

The lesson helps only when:

- both runs with the lesson pass every target criterion;
- at least one run without the lesson misses one;
- no control loses a criterion or breaks the token rule (more than both 10% and 25,000 tokens).

The verdict, its reasons and every eval ID are appended to the ledger. Two runs per cell is thin evidence; read the reasons, and the answers under the results directory, before deciding.

## Turn a lesson on

`qk lesson decide ID active` is refused unless the latest measurement is under 60 days old and shows that the lesson helps. Allowed changes are proposed → active or dismissed, then active → retired or promoted.

An active lesson is still loaded only when you ask: `--lessons` adds at most 5 active lessons scoped to the turn's stage (and repository, if named), about 800 tokens in all. Without the flag the prompts are byte-for-byte unchanged. Runner state and eval results record which lesson IDs were used.

## Remove or re-measure

- `qk lesson decide ID retired` stops a lesson from being loaded. Records are never deleted; the history stays.
- An active lesson whose latest helping measurement is older than 60 days is marked `needs-remeasure` in `qk lesson list` and is skipped by `--lessons` until you measure it again.
- A lesson whose eval case was deleted is skipped.
- `promoted` records that the rule now lives somewhere enforced (a test, a runner check or a skill line); you make that change in a normal PR.

The CLI records who it believes acted, but it cannot prove who ran a command. The [store tests](../../tests/test_qk_ledger.py) and [eval tests](../../tests/test_qk_eval.py) own the checks for these rules.
