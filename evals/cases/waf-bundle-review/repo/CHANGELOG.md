# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `versions <rule-group>` command: lists the available versions of an AWS managed rule group and marks the current default.
- `diff <rule-group> <from> <to>` command: compares two versions (rules added and removed, rule action changes, capacity, available and consumed labels).
- `check` command: checks every AWS managed rule group in a web ACL (from a file or from the API) against a target version (`default`, `latest` by `LastUpdateTimestamp`, or a version name) and reports overrides of missing rules, labels no longer emitted, unavailable pinned versions, capacity increases, pinned versions that differ from the default, a default version that is not listed or cannot be described when a comparison needs it (`default-not-describable`, warning) and rule changes. Exits with `1` when a finding is an error.
- `--scope`, `--region`, `--profile` and `--format` options for all commands.
