# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Skills `qk-brainstorm`, `qk-research`, `qk-plan`, `qk-cook`, `qk-debug`,
  `qk-test`, `qk-handoff`, `qk-agent-coord` and `qk-release-notes`.
- Explicit-invocation only: `disable-model-invocation: true` for Claude Code and
  omp, `policy.allow_implicit_invocation: false` for Codex.
- `scripts/validate.py` and CI checks for structure, naming, invocation policy,
  internal links, personal paths and secrets, plus a gitleaks scan.
