# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `qk contract [--json]` prints the CLI contract version, the qk version and the commands external tools may
  rely on. `tests/test_contract_v1.py` fails when a promised command or JSON field disappears.
- `qk agent run --spec RUNTIME:MODEL --cwd DIR (--write | --read-only) --json < prompt` runs one non-interactive
  agent turn with the runner's isolation and prints its status, parsed `qk-result`, final text and token usage.
  It never touches git; exit 0 is done, 2 is blocked or rejected input. `qk agent family SPEC` prints the model
  family the runner uses to keep the implementer and reviewer apart.
- `qk agent run` handles SIGTERM: it stops the agent's process group, removes its scratch directory and reports
  `blocked` ("stopped by SIGTERM") with exit 2. Before, the agent kept running after the command was killed.
- `qk log run --producer NAME --state-dir DIR --json < state.json` records a run that another tool stopped
  (`done`, `blocked` or `aborted`) and its findings through the projection `qk-run` uses, so it shows in
  `qk show`, `qk stats` and `qk brief`. The run record carries the caller's `producer` label, and a blocked
  card names that producer instead of suggesting `qk run resume`. `--state-dir` must hold the caller's
  `state.json`. Rejected input exits 2 and records nothing; the same input twice adds nothing.
- `qk eval prepare CASE DIR --json` builds a case's repository in `DIR/repo` (with its task, or for a review case
  the plan and diff copied next to it) and `qk eval grade CASE WORKDIR [--final FILE] [--events FILE] --json` runs
  the case's `check.py` from a private copy, on a throwaway copy of the working tree and with the events beside
  the final reply as `qk eval` lays them out, and reports `criteria` and `passed`. Neither runs an agent, writes the
  baseline or records anything, so another tool can measure itself on the same cases with the same grading. The old
  `qk eval --case/--skill/--all` flags are unchanged.
- `qk decide RUN_ID merge|leave|abort-later|resume-later [--method M]` records a brief decision without a terminal,
  for example from an agent in a chat acting on the user's stated choice, with the same merge checks and choices as
  the card. Decisions record `via` (`brief` or `decide`), and `qk-run` agents are told never to merge or record
  decisions.
- `qk brief` includes blocked runs and orders decision cards by fixed, printed risk rules using recorded diff scope.
- On a terminal, `qk brief` asks for a decision after each card and records it with `source=user`;
  `y` merges only when the PR head still matches the run's recorded commit.
- `qk-run approve ID --later` queues an approved plan without running it, and `qk-run drain
  [--until HH:MM] [--notify]` runs queued runs one at a time; a run that crashes is blocked and the
  queue continues.
- Overnight guide (`docs/{en,vi}/overnight.md`): queue, drain, morning brief, recovery and the publishing account.
- `qk brief` shows a run left in a working stage with no runner (a killed drain or terminal) as a high-risk
  `stopped at <stage> (runner gone)` card; the runner holds `run.lock` in the run directory while it works. A run
  started before this change and still running has no lock, so it also shows as stopped until it finishes.

### Fixed

- `qk brief` checks that the active `gh` account can merge (`viewerPermission` of write or above) before asking for a
  merge method, and says how to rerun with `GH_TOKEN`; before, it asked for a method and then failed at `gh pr merge`.
- `qk brief` raises a card to high only for remaining blocker or important findings; run records keep a
  `serious_count`, and older records without it still count every remaining finding.
- Agent prompts in `qk-run` now require foreground commands; an agent that started its test suite in the
  background and promised to report later ended its one-shot turn without a result.

## [0.8.0] - 2026-11-18

### Added

- Evidence-backed lesson records and `qk lesson suggest/propose/list/decide`;
  activation requires prior measurement.
- `--lessons` for `qk-run` and `qk_eval`: adds active lessons scoped to each stage (at most 5,
  about 800 tokens) and records which were used; prompts are unchanged without it.
- `qk lesson measure ID --runtime SPEC`: runs the lesson's case with and without it plus same-stage
  controls and records the result; activation needs a helping measurement under 60 days old. A run
  that fails `clean` voids the measurement, and a proposal needs an eval of its case that failed a
  criterion other than `clean`.
- Lessons guide (`docs/{en,vi}/lessons.md`) and the first lesson's measurement in the test evidence.
- Local append-only evidence ledger and `scripts/qk.py`: `show`, aggregate `stats`,
  model `log claim`, read-only PR `sync` with run backfill, and an offline `brief`
  that marks evidence stale when a PR head changes.
- `qk run …` and `qk eval …` entry points; the original scripts remain supported.
  The runner records stopped runs and review history; evals record every attempt.
  Ledger failures warn without failing the underlying task.
- Optional `qk-run start --task-kind` history labels; model-authored findings retain
  their provenance rather than being presented as code-verified facts.
- `qk-cook`, `qk-test` and `qk-handoff` may save one conclusion with `qk log claim` when the
  `qk` CLI is installed, a ledger ID is known and writes are authorised.
- Behavioral eval cases for independent test failure triage and handoff drift.
- `pip-config-review` eval case from a public pip pull request, and the kit comparison results
  (no kit, Superpowers, qk) in the test evidence.

### Fixed

- New claims inherit the referenced event's repository and task-kind labels,
  including claims about claims, so repository/task filters retain the observations.
- PR sync skips unchanged decision snapshots and reports recorded/unchanged counts;
  the brief timestamp reflects the last observed change.
- Sync backfill imports saved eval attempts using the live evaluator’s ledger keys,
  including earlier rerun grades, and reports missing or malformed eval results.
- Run history selects source revisions rather than import order, so a delayed
  backfill cannot hide a resumed run or its PR.
- The triage eval accepts observed immediate exit-status capture but rejects
  short-circuited shell chains that print a result without running the check.

## [0.7.0] - 2026-11-15

### Added

- `qk_eval.py --kit none|qk|superpowers` compares kits on one Claude Code base (no user skills or plugins, the
  same output format for every kit); results never touch the baseline.

### Fixed

- The Claude Code `bundle-malformed` baseline is re-recorded with the new review prompt; it was the only
  review-case entry still from the previous prompt.

## [0.6.0] - 2026-11-15

### Added

- Eval case `waf-bundle-review`: the runner's review prompt on a real, 1,200-line pull request with eight real
  defects put back. Unlike the first three cases, it separates review prompts: with the previous prompt omp and
  Claude Code (Claude Opus 5.5) caught 0 of 8 at blocker or important; with the new prompt, 3 to 6 of 8 per run.
- `scripts/qk_eval.py` runs fixed eval cases on one runtime, grades each by
  code (`check.py`), prints criteria, tokens and time, and compares them with
  `evals/baseline.json`: a lost criterion, tokens more than 10% and more than
  25,000 above the baseline (about one agent turn), or an agent error exits 1; a flipped case is rerun once;
  `--update-baseline` records accepted results. See `docs/en/evals.md`.
- Three eval cases in `evals/cases/`: `csv-export` (`qk-cook`),
  `pagination-empty-page` (`qk-debug`) and `bundle-malformed` (the runner's
  review step).

### Changed

- The runner's review prompt is built by `qk_run.review_prompt` so evals use
  the same text. Reviewers now classify findings, search the full diff for
  further instances of a defect class, and rate crashes on accepted external
  input at least important.

## [0.5.0] - 2026-11-14

### Added

- `qk-run` shows each agent tool action live (`read`, `edit`, `write`, `run`),
  prints `still running (...)` after every 60 s without events, saves the raw
  events of each turn to `<stage>-<ts>.events.jsonl` in the run directory, and
  `status` prints the run directory and the last 10 lines of `run.log`.
- `qk-run` logs each agent call's token usage as
  `tokens in=... cached=... out=...` (plus `cost=$...` when the runtime
  reports it) and stores it per stage under `usage` in `state.json`.
- `qk-run start --read-only-mcp NAME` (repeatable, Claude and omp only) lets
  read-only stages call that MCP server.

### Changed

- A `qk-run` timeout now stops the agent's whole process group (SIGTERM, then
  SIGKILL after 10 s) instead of leaving it running.
- Commit and PR titles are cut at a word boundary at 72 characters, a
  non-conventional `<word>: ` prefix is dropped when a conventional type is
  added, and the planner is asked for a title of at most 60 characters.
- `qk-run` agents no longer load globally installed skills: Claude runs with
  `--disable-slash-commands`, omp with `--no-skills --no-extensions --no-rules`,
  and Codex in a private home inside the run directory with plugins, remote
  plugins and apps turned off.
  Read-only Claude stages also run with `--strict-mcp-config`.
- A read-only `qk-run` stage that calls MCP or another `xd://` runtime device
  is stopped and blocks with `read-only stage called <action>`.
- `qk-run` logs MCP calls as `mcp <identifier>` and `xd://report_issue` as
  `tool report_issue` instead of `write xd://...`.
- `qk-run resume` after a block at verify, review or fix accepts hand edits
  made after the block, logs `manual changes recorded: <files>` and continues
  at `verifying`. Changes made while a read-only stage ran still keep the run
  blocked.

## [0.4.0] - 2026-11-14

### Changed

- `qk-cook`, `qk-test`, `qk-debug`, `qk-research` and `qk-plan` audit now check
  only what could change the decision, once, and reuse what the session already
  saw, instead of re-verifying everything.

### Added

- A one-page philosophy in English and Vietnamese: understand enough to decide,
  through three principles (three roles, evidence rather than claims, enough).
  The README and docs index now point to it instead of keeping their own lists.

## [0.3.0] - 2026-11-14

### Added

- One-command installation with `npx skills add dakiquang/qk`, documented in
  English and Vietnamese with pinning (`#<tag>`), update and removal; the clone
  and link install stays as the manual option.

### Changed

- The identity check and the preference store now ship inside their skills
  (`skills/qk-commit/scripts/qk_preflight.py`, `skills/qk-prefs/scripts/qk_prefs.py`),
  so `qk-commit` and `qk-prefs` keep working when an installer copies a skill
  folder instead of linking the whole clone.

### Upgrade notes

- If you registered the preference hook with `scripts/qk_prefs.py` in a qk
  clone, point it at `skills/qk-prefs/scripts/qk_prefs.py` instead.

## [0.2.0] - 2026-11-14

### Changed

- Documentation prepared for a public repository: rewritten README, regrouped
  docs index, and dated runtime and runner test records moved to a separate
  English/Vietnamese test evidence page so the guides stay evergreen.
- `qk-run` now prefixes the commit and PR title with a Conventional Commits type
  and lowercases the subject's first letter (acronyms excepted) when most of the
  base branch's last 20 non-merge commits follow Conventional Commits.

### Removed

- Internal planning notes and a dated project summary that were not user
  documentation.

## [0.1.0] - 2026-11-14

### Added

- Manual runtime smoke checklist and release pinning instructions in the English and Vietnamese documentation.
- `qk-commit` for scoped commits, optional push and PR, plus `scripts/qk_preflight.py`
  to check push permission for the active GitHub account before publishing.
- Skills `qk-brainstorm`, `qk-research`, `qk-plan`, `qk-cook`, `qk-debug`,
  `qk-test`, `qk-handoff`, `qk-agent-coord` and `qk-release-notes`.
- `qk-dogfood`: explicit-only, evidence-based instruction improvement proposals
  in chat, with ownership checks and no apply mode; English/Vietnamese guides.
- `qk-prefs` and the opt-in preference hook (`scripts/qk_prefs.py`): prompts with
  a lasting-preference phrase become pending proposals; the skill applies only
  the ones the user approves. Idea from nghiacr002/personal-brain-style (MIT),
  implemented separately.
- Explicit-invocation only: `disable-model-invocation: true` for Claude Code and
  omp, `policy.allow_implicit_invocation: false` for Codex.
- `scripts/validate.py` and CI checks for structure, naming, invocation policy,
  internal links, personal paths and secrets, plus a gitleaks scan.
- English and Vietnamese documentation: installation, workflow recipes, runtime
  evidence and limits, and practical guides for all skills.
- A worked CSV-export case study covering brainstorm, planning, bounded worker
  orchestration, PR creation, companion review, merge and verified shipping.
- Documentation checks requiring core guides, per-skill guides and matching
  English/Vietnamese paths in addition to internal-link validation.
- `scripts/qk_run.py`: opt-in runner from request to a ready-for-review PR on
  Claude Code, Codex or omp, with one plan-approval gate, runner-run verification,
  cross-model review, at most one fix round and runner-only commit/push/PR;
  unit tests in CI and English/Vietnamese guides.
- English and Vietnamese lean-setup guide: measure per-session instruction load
  with each runtime's own commands and trim skill descriptions, always-loaded
  rules and duplicated instructions without removing other kits.

### Changed

- Skill reports now end with Done, Evidence, Not verified and Needs your decision;
  the validator checks each skill's contract rows and ordered report labels.
- Canonical instructions for all ten skills and the worker prompt reference are
  now English; human documentation remains available in English and Vietnamese.
- Reports localize human-facing labels to the user's requested language; edits
  preserve existing artifacts' language and format, including plans and handoffs.
- Clarified independent-event counting and exact-path source resolution in
  `qk-dogfood`, without adding an apply mode or expanding its authority.

### Fixed

- Grant the gitleaks job PR-read access without comment-write access; describe
  event-range scanning rather than implying a full-history scan.
- Include staged blob IDs in worker mutation checks and retain every flaky-run
  outcome, including the original failure.
- Stop installation on clone failure or invalid/missing skill sources.
- Reject nested descriptions and duplicate interface keys; scan UTF-8 text of any
  suffix and match punctuation-bearing denylist terms, including in the validator.
