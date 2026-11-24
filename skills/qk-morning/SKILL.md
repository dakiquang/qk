---
name: qk-morning
description: >-
  Read the morning brief's cards inside the chat and record the user's decisions with qk decide.
  Use only when the user explicitly invokes qk/morning (`/qk-morning`, `$qk-morning`, `/skill:qk-morning`).
disable-model-invocation: true
---

# qk/morning

One card at a time: show it, ask, record only the user's own choice.

| | |
|---|---|
| **Result** | Every card read; the user's choices recorded with `qk decide`; the rest left for later |
| **Authority** | Run `qk sync`, `qk brief --json` and `qk decide`. `qk decide` only on the user's stated choice for that card, merge method included. Never `gh`, `git push`, `qk run resume` or `qk run abort` |
| **Done when** | Every card was shown and either decided by the user or skipped |

## Steps

1. Run `qk sync`. A failure is not a stop: say so, and note that PR states may be out of date.
2. Run `qk brief --json`. With no cards, say there is nothing to decide and go to the report.
3. For each card in order, show its `lines` unchanged, then ask for one of its `choices` or "skip".
   - Use the runtime's question tool when it has one (Claude Code: `AskUserQuestion`, with the choices as options; omp: the `/qk-brief` command does the same in its own interface). Otherwise ask in plain text and wait.
   - On request, show the PR diff with `gh pr diff <pr_url>` (read-only) before asking again.
   - A card with `decided: true` says so; ask whether to change it.
4. Record the answer with `qk decide <run_id> <choice>`. For `merge`, add `--method <m>` only when the user named it; when `qk decide` says the repository allows several methods, ask which. On an error, show it and move on; do not retry with other arguments.
5. `abort-later` and `resume-later` only record intent; say that the user still runs `qk run abort <id>` or `qk run resume <id>` (or the tool named on the card).

## Report

Close every report with these four lines, in this order, translating the labels to the user's language; write "none" when a line is empty:

**Done**: each card and the choice recorded (or skipped)
**Evidence**: `qk sync` result, and each `Recorded <choice>: <id>` line
**Not verified**: what failed or was not shown, and why
**Needs your decision**: cards skipped, and follow-up commands the user runs

## Boundaries

- Higher-priority instructions, runtime rules and repository rules override this skill.
- Language: reply in the user's language; card `lines` stay unchanged.
- Never choose for the user, never infer a choice from earlier answers, and never merge outside `qk decide`.
- Do not change model, permissions, hooks or configuration. Do not invoke other qk skills automatically.
