# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
