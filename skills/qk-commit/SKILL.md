---
name: qk-commit
description: >-
  Make scoped commits, optionally push and open a PR when those steps are named.
  Use only when the user explicitly invokes qk/commit
  (`/qk-commit`, `$qk-commit`, `/skill:qk-commit`).
disable-model-invocation: true
---

# qk/commit

| | |
|---|---|
| **Result** | One or more commits following the repository convention; push and open a PR only when asked |
| **Authority** | Only the steps named in the invocation: `commit`, `commit push`, or `commit push pr`. Never amend, force-push, switch accounts, merge or tag |
| **Done when** | The report gives the SHA, committed files, scan result and real push/PR status; each unfinished step has a reason |

## Steps

1. Read `git status`, the full diff (including staged changes), and untracked files. Confirm which files belong to the task just done. If on the default branch and push was requested, stop and ask for a branch name.
2. Exclude env files, keys, unusually large files and files outside that task. Name every excluded file in the report; stage only intended files.
3. Scan the exact content to be committed for secrets and personal home paths. Run the repository's own check, such as a validator or pre-commit check, when available. Resolve findings before committing.
4. Write the message in the repository's convention, using contributing docs or recent commits. Add no AI attribution unless the repository requires it.
5. Before committing, compare `git diff --cached --name-only` with the intended files, unstage and report any other paths; then commit without `--no-verify` and record the SHA and committed file list.
6. Only when push was requested, locate the identity script inside this skill folder: `<this skill folder>/scripts/qk_preflight.py`. From the repository to push, run `python3 "<skill folder>/scripts/qk_preflight.py" identity`. If the check fails, stop and report; never switch accounts. If the script is missing, do not push; report that the account could not be checked. Push only after the check passes.
7. Only when a PR was requested, open it after a successful push. Its description states what changed, why, and verification evidence from this session. Never claim tests that did not run.

## Report

Give the SHA, committed files, scan and repository-check results, excluded files, and actual push/PR status. Explain each unfinished step.

Close every report with these four lines, in this order, translating the labels to the user's language; write "none" when a line is empty:

**Done**: what was produced or changed, with paths
**Evidence**: commands run and their results, sources read
**Not verified**: what was not checked, and why
**Needs your decision**: what waits on the user

## Boundaries

- Higher-priority instructions, runtime rules and repository rules override this skill.
- Reply in the user's language unless the user or repository specifies another. Keep commands, paths, identifiers and fixed machine strings unchanged.
- Do not amend, force-push, switch accounts, merge, tag or invoke other qk skills automatically.
