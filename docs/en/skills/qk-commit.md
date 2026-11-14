# qk/commit

[Tiếng Việt](../../vi/skills/qk-commit.md) · [Docs index](../README.md) · [Skill source](../../../skills/qk-commit/SKILL.md)

## When to use it

Invoke `qk/commit` when finished work should become a commit. Name the authorized steps: `commit`, `commit push`, or `commit push pr`. The skill reads the status and diff, excludes unrelated or sensitive files, scans the content to be committed, and follows the repository's commit-message convention. It reports the SHA, files and real status of each requested step.

## Example input

```text
/qk-commit commit push pr
```

Use `$qk-commit` in Codex or `/skill:qk-commit` in interactive/RPC omp.

## Authority and completion

The skill runs only the named steps. Before pushing, it runs the [identity preflight](../../../skills/qk-commit/scripts/qk_preflight.py) against the active `gh` account. A failed check stops the push; if the script is missing, it does not push and reports that the account could not be checked. The user chooses the account to use. A PR description includes what changed, why and checks actually run in the session. The skill never amends, force-pushes, switches accounts, merges or tags.

Tip: If the identity check fails because another logged-in account owns the repository, you can run one command as that account without switching the active one, for example `GH_TOKEN=$(gh auth token --user <name>) git push -u origin <branch>`. This works when git uses `gh` as its credential helper (`gh auth setup-git`). The skill never reads tokens or switches accounts; run this yourself or explicitly ask for it.
