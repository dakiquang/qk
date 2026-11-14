# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `scripts/qk_eval.py` runs fixed eval cases on one runtime, grades each by
  code (`check.py`), prints criteria, tokens and time, and compares them with
  `evals/baseline.json`: a lost criterion, tokens more than 10% above the
  baseline or an agent error exits 1; a flipped case is rerun once;
  `--update-baseline` records accepted results. See `docs/en/evals.md`.
- Three eval cases in `evals/cases/`: `csv-export` (`qk-cook`),
  `pagination-empty-page` (`qk-debug`) and `bundle-malformed` (the runner's
  review step).

### Changed

- The runner's review prompt is built by `qk_run.review_prompt` so evals use
  the same text; the text is unchanged.

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
