# Lean setup

[Tiếng Việt](../vi/lean-setup.md) · [Docs index](README.md)

Every session starts by loading the system prompt, tools, skill descriptions and instruction files before your first message. This guide shows how to see that cost and how to cut it with what your runtimes already have. qk works next to other skill kits and never asks you to remove them.

## 1. Measure

Measure in an empty directory, so project files don't count, and start a new session after each change. One run gives an estimate, not a benchmark.

**Claude Code.** Run `/context` in a session, or the non-interactive form:

```bash
claude -p "/context" --output-format json --verbose
```

It makes no model call, so it costs nothing. It shows estimated tokens by category, including each memory file and each skill. Shortened example:

```text
System prompt      3,000 tokens
System tools      12,000 tokens
MCP tools          5,000 tokens
Memory files       4,000 tokens
  CLAUDE.md        1,000
  rules file       3,000
Skills             2,000 tokens
  some-skill         100
Messages             100 tokens
Free space       150,000 tokens
```

The full output also lists MCP server instructions, deferred MCP and System tools, Custom agents and the Autocompact buffer.

**Codex.**

```bash
codex exec --sandbox read-only --skip-git-repo-check --json "Reply with the single word OK."
```

`--skip-git-repo-check` lets it run in an empty folder outside a git repository, which `codex exec` otherwise refuses, and `--sandbox read-only` keeps the measurement from writing anything. Read `usage.input_tokens` in the `turn.completed` event; this costs one small model call. Example: `turn.completed → usage.input_tokens: 12000`. There is no per-category view, so compare totals before and after a change.

**omp.** Run `omp --mode json -p "Reply with the single word OK."` and read `usage.totalTokens` on the final message. Run it again with `--no-skills` to see what the skill list costs, and with `--no-context-files` to drop `AGENTS.md` / `CLAUDE.md`. Example values: `15000 / 13000 / 11000`. `omp stats` and `omp usage` exist but were not tried.

**Qwen Code.** Not checked.

Numbers are examples, not measurements. The versions these commands were checked on are in [Test evidence](evidence.md#lean-setup-measurements).

## 2. Cut the three usual heavy spots

**Descriptions of auto-invoked skills.** Every skill the model may invoke by itself carries its description into each session; in Claude Code, the Skills category lists them with tokens. For a skill you rarely use:

- make it explicit-only with the runtime's own setting (see [Runtimes](runtimes.md#explicit-only-invocation)), or
- unlink it if you created the link and no longer use it. Check with `readlink` first, as in [Getting started](getting-started.md#5-uninstall).

Change single skills, not whole kits.

**Always-loaded rules and instruction files.** In Claude Code, Memory files lists each `CLAUDE.md` or rules file with its tokens; in omp, compare a run with `--no-context-files`. Keep a short index in the always-loaded file and move the detail into files the agent reads only when the index points to them.

**User instructions duplicated across runtimes.** The same rules copied into each runtime's user instruction file, and into several files that one runtime loads, are likely paid for again in every session. omp, for example, drops both `AGENTS.md` and `CLAUDE.md` with `--no-context-files`, so a rule kept in both may load twice; this is an inference, not a measurement. Keep one copy of each rule per runtime and delete the repeats.

## 3. Why qk skills cost little until invoked

Every qk skill sets `disable-model-invocation: true`, and `policy.allow_implicit_invocation: false` for Codex. In the Claude Code check, skills with that field were not in the Skills table, so they add no tokens there until you call one.

On omp and Codex the same settings block automatic invocation, but whether the description still loads was not measured. Use the before/after check above. See [Runtimes](runtimes.md#explicit-only-invocation) for the evidence level.

## 4. Running alongside other kits

qk does not require removing or disabling anything. To trim, measure, change one skill to explicit-only, start a new session and measure again. Keep the change only if the difference is worth losing automatic invocation of that skill; otherwise revert it.

Edits inside another kit's files may be overwritten when that kit updates, so measure again after updates.
