# qk/test

[Tiếng Việt](../../vi/skills/qk-test.md) · [Docs index](../README.md) · [Skill source](../../../skills/qk-test/SKILL.md)

## When to use it

Use this for independent or broader verification: before merge, after another agent's changes, or in a different environment. It does not replace cook's own verification and is not automatically required after every change.

## Example input

```text
/qk-test Verify the current health-endpoint change. Discover commands from this repo. Run focused checks first, then the relevant broader suite. Do not fix code or install dependencies.
```

## What you get

A table of actual commands, exit codes and outcomes; new failures; confirmed baseline failures; flaky outcomes; behaviours/environments left untested. Remote CI is labelled CI, not local execution.

Commands come from repository docs, CI and manifest scripts, not an assumed package manager. A failure is baseline only when there is evidence from base CI or an authorised temporary base worktree. If that evidence is unavailable, say baseline is unknown. Flaky failures may be rerun at most twice, preserving every outcome; a later success does not turn the original failure into a clean pass.

## Authority and completion

Run repository checks only. Do not edit product code, change test configuration, install new dependencies or commit. Test processes may create their normal output; this is not a filesystem sandbox.

Done means results and classifications have evidence and blocked checks have reasons. Take a discovered failure to `qk/debug` explicitly; do not make tests green by weakening assertions or changing configuration.

All higher-priority, runtime and repository rules still apply. This skill does not change models, permissions, hooks or configuration, and never invokes another qk skill automatically.
