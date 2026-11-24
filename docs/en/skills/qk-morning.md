# qk/morning

The morning brief read in the chat, with your decisions recorded.

[Tiếng Việt](../../vi/skills/qk-morning.md) · [Docs index](../README.md) · [Skill source](../../../skills/qk-morning/SKILL.md)

## When to use it

Use it after an overnight drain or a harness job, when `qk brief --pending` (or the session-start reminder from the [runtime adapters](../runtime-status.md)) says cards wait for a decision. It replaces typing in the terminal brief, not deciding.

## Example

```text
/qk-morning
```

## What it does

It runs `qk sync`, then `qk brief --json`. For each card it shows the brief's own lines and asks for one of the card's choices, or skip. Claude Code asks with a question dialog; other runtimes ask in text. It records your answer with `qk decide`, adding a merge method only when you name one. It can show the PR diff on request.

## Authority and completion

It may run `qk sync`, `qk brief --json`, `qk decide` and, on request, `gh pr diff`. It never chooses for you, never merges outside `qk decide`, and never runs `qk run resume` or `qk run abort`; `abort-later` and `resume-later` only record your intent. It finishes when every card was decided or skipped, with the four-line report.
