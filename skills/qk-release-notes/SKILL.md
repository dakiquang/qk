---
name: qk-release-notes
description: >-
  Draft release notes and CHANGELOG entries from commits, PRs and verified
  evidence, in one or two languages; no tagging, no publishing. Use only when the
  user explicitly invokes qk/release-notes (`/qk-release-notes`,
  `$qk-release-notes`, `/skill:qk-release-notes`).
disable-model-invocation: true
---

# qk/release-notes

Input: a tag range (`v0.1.0..HEAD`), a list of PRs, or the upcoming version. The language defaults to the repo's; if bilingual output is requested, write both.

| | |
|---|---|
| **Result** | Draft release notes and/or a CHANGELOG entry the user can approve |
| **Authority** | Read git and PRs (read-only commands only). Write a draft file, or the `[Unreleased]` section of the CHANGELOG when asked. Do not create tags, run `gh release`, publish, or change the version |
| **Done when** | Every line traces back to a commit or PR; the "verified" section contains only items with real evidence |

## Method

1. Gather sources: `git log` for the range, merged PRs, the existing CHANGELOG. Read the diff when a commit title does not explain the change.
2. Group for the reader, using the repo's existing headings when it has them. Added, Changed, Fixed and Upgrade notes (breaking changes, dependencies, environment variables, migrations) are examples, not an override of the repo's headings. Omit internal commits with no user impact.
3. Write in terms of user-visible behavior, not file names.
4. The CHANGELOG follows the format the repo already uses (often Keep a Changelog). Do not change an existing format.
5. The "verified" section lists only verification that actually happened: CI, commands run, tests on a real environment. If there is none, omit the section; do not infer it from a PR having been merged.
6. Do not mention customer names, customer data or internal systems.

## Report

Dropped changes (one-line reason each). Under Needs your decision, list the version and any breaking changes to confirm. Tagging and releasing belong to the repo's release process or the release mode of `pr-orchestrator`, and need a separate request.

Close every report with these four lines, in this order, translating the labels to the user's language; write "none" when a line is empty:

**Done**: what was produced or changed, with paths
**Evidence**: commands run and their results, sources read
**Not verified**: what was not checked, and why
**Needs your decision**: what waits on the user

## Boundaries

- Higher-priority instructions, runtime rules and repository rules override this skill.
- Language: reply in the user's language unless the user or repository specifies another; localize human-facing report labels. The draft and CHANGELOG language and format follow the repo rules above (repo default, both languages when bilingual output is requested); when updating a saved artifact, keep its existing language and format. Commands, paths, identifiers and fixed machine strings stay unchanged.
- Do not change model, permissions, hooks or configuration. Do not invoke other qk skills automatically.
