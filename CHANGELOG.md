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

### Changed

- Canonical instructions for all ten skills and the worker prompt reference are
  now English; human documentation remains available in English and Vietnamese.
- Reports localize human-facing labels to the user's requested language; edits
  preserve existing artifacts' language and format, including plans and handoffs.
- Clarified independent-event counting and exact-path source resolution in
  `qk-dogfood`, without adding an apply mode or expanding its authority.
