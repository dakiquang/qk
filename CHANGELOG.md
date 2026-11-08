# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Skills `qk-brainstorm`, `qk-research`, `qk-plan`, `qk-cook`, `qk-debug`,
  `qk-test`, `qk-handoff`, `qk-agent-coord` and `qk-release-notes`.
- `qk-dogfood`: explicit-only, evidence-based instruction improvement proposals
  in chat, with ownership checks and no apply mode; English/Vietnamese guides.
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

### Changed

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
