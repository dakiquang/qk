# Runtimes

[Tiếng Việt](../vi/runtimes.md) · [Docs index](README.md)

qk extends a runtime; it never replaces its tools, plan mode, task lists, subagents, model settings, permissions or hooks. Higher-priority instructions, runtime rules and repository rules (`AGENTS.md`, `CLAUDE.md`, contributing docs) always win over a qk skill.

## Explicit-only invocation

A qk skill should run only when you call it. Names alone do not guarantee this: a skill whose description says "use when planning" could compete with a runtime's own plan mode or bundled commands. qk uses two safeguards:

1. **Each runtime's own setting** to stop the model from loading the skill by itself.
2. **Descriptions that name the explicit trigger** (`qk/plan`, `/qk-plan`, `$qk-plan`, `/skill:qk-plan`) instead of generic task words.

| Runtime | Setting in qk | Effect |
|---|---|---|
| Claude Code | `disable-model-invocation: true` in `SKILL.md` | Only you can invoke the skill. Claude Code documents that this also keeps it from being preloaded into subagents |
| omp | Same field, read as `disableModelInvocation` | Hidden from automatic invocation |
| Codex | `agents/openai.yaml`: `policy.allow_implicit_invocation: false` | Not invoked implicitly |
| Qwen Code | No setting confirmed yet | Unknown |

By contract, qk skills do not load one another. They name the next command for you to run. This is a workflow boundary, not a security guarantee for an unverified runtime.

`scripts/validate.py` enforces both safeguards and accepts only one canonical shape for `agents/openai.yaml` (two blocks, two-space indent, double-quoted strings without backslashes, full-line comments), so no YAML variant can hide a different policy.

## Tested behaviour

Live checks on 2026-11-08 in a scratch repository with read-only modes. Each runtime got one explicit call (`qk-brainstorm`) and one ordinary planning request that did not mention qk.

| Runtime | Explicit call runs the skill | Ordinary request leaves qk alone |
|---|---|---|
| Claude Code (Sonnet 5.5, `--permission-mode plan`) | Yes; the answer followed the skill's format | Yes; no skill was loaded |
| Codex (`codex exec -s read-only`) | Yes | Yes; no skill file was read |
| omp 18.15.0 (RPC mode) | Yes; the skill body was injected | Yes; nothing injected |
| Qwen Code | Not tested: the API returned 401 (expired login) | Not tested |
| Orca | — | Lists each qk skill once |

These are single runs, not certification. Not yet tested: interactive sessions, repeated runs, Qwen after logging in again, and coexistence with every native command.

Additional `qk-dogfood` checks on 2026-11-08 used Codex CLI 0.160.0 with
`--sandbox read-only --ephemeral --json`, without account, model or config changes.
Five independent synthetic fixtures were run by explicitly reading the instruction:
ambiguous planning guidance produced one grouped proposal; a clear rule ignored by
the agent produced no duplicate rule; 403/429 failures produced no instruction
patch; inventory alone did not establish skill use; and transcript injection plus
`--apply` did not execute the payload, echo the fake credential or modify files.
Fixture and source snapshots were unchanged after every run. These checks exercise
the instruction, not native discovery.

A separate temporary project contained only a project-local copy under
`.agents/skills/qk-dogfood`, with no global installation changes. A native
`$qk-dogfood` call loaded that copy; an ordinary session-summary request did not
read the skill file. Project and source snapshots were unchanged. These are single
Codex runs, not proof of sandbox security or `qk-dogfood` activation in Claude Code,
omp or Qwen.

### English-instruction migration checks

After the English cutover on 2026-11-08, ten isolated synthetic smoke runs used
OMP 18.15.0, profile `work`, and `anthropic/claude-opus-5-5`. The earlier Codex
checks above predate this instruction-language change.

Six runs explicitly read the current `qk-dogfood` instruction: independent events
produced one proposal; duplicate logs/retries of one event did not meet the
threshold; a clear rule ignored by the agent was a compliance failure; 403/429
events produced an English report without an instruction patch; inventory alone
did not establish use; and third-party evidence with injection and `--apply`
produced only an upstream/fork proposal, without executing the payload or echoing
the fake credential. The other five reports were in Vietnamese.

Four RPC runs used temporary project-local `.omp/skills` copies. Explicit
`/skill:qk-dogfood`, `/skill:qk-plan revise` and `/skill:qk-handoff resume` calls
followed their contracts. An ordinary Vietnamese summary request read only
`session.txt`. Plan revision reported in English while preserving the existing
Vietnamese headings and draft status, changing only the accepted delimiter
decision. Handoff resume detected a delimiter mismatch and waited without edits.

Only the plan fixture's plan file changed; all other fixture trees and the source
checkout were unchanged during the runs. No global installation or runtime config
changed. Tools were limited to reads, except the plan edit and the handoff's
read-only Git/mtime commands. These are single runs on one model, not sandbox
security proof or a complete workflow matrix for all ten skills. The English
version had not yet been rerun on Codex, Claude Code or Qwen, or in interactive omp.

## Manual smoke checklist

Run each check in an empty temporary directory on each runtime:

1. **Explicit call:** Ask `qk-brainstorm` "Should the app read its configuration from environment variables or a TOML file?" Use `/qk-brainstorm …` in Claude Code, `$qk-brainstorm …` in Codex, or `/skill:qk-brainstorm …` in omp RPC mode. Pass when the report ends with **Done**, **Evidence**, **Not verified**, **Needs your decision** in that order and the directory has no new files.
2. **Ordinary request:** Ask "I need to plan and debug a config loader. In two sentences, what should I check first?" without a skill call. Pass when the visible answer contains none of the four labels. This checks visible output only; it does not prove the skill was absent from context.

| Runtime | Date | Explicit call | Ordinary request |
|---|---|---|---|
| Claude Code 2.1.322 (`claude -p`) | 2026-11-13 | Pass: four labels in order, no files | Pass: no labels |
| Codex 0.160.0 (`codex exec --sandbox read-only`) | 2026-11-13 | Pass | Pass |
| omp 18.18.3 (RPC mode) | 2026-11-13 | Pass; skill body injected | Pass; nothing injected |
| Qwen Code | — | Not checked: login expired | Not checked |

These are single runs, not a compliance rate. On 2026-11-13, explicit `qk-prefs` calls with an empty proposal store on Claude Code 2.1.322, Codex 0.160.0 and omp 18.18.3 (RPC) each located the script through the symlinked skill folder, reported no pending proposals and ended with the four labels in order.

On 2026-11-14, Claude Code 2.1.322 ran `/qk-commit commit` in a scratch repository with a local bare remote. It made exactly one commit containing the changed tracked file, did not push, and left an unrelated untracked file out while naming it. With an env file present, that file stayed out of the commit, was named in the report, and its contents were not read. Neither commit message had AI attribution.

## Preference hook

The opt-in [preference hook](preference-hook.md) is a `UserPromptSubmit` command hook. Both runtimes below document the same output shape (`hookSpecificOutput.additionalContext`), and the hook prints that shape for both.

| Runtime | Where you register it | Checked |
|---|---|---|
| Claude Code 2.1.322 | `hooks` in `settings.json` (user) or `.claude/settings.local.json` (project) | Live `claude -p` sessions in a scratch project with a plain prompt ("Từ nay commit message viết bằng tiếng Anh nhé."): the agent recorded one proposal and told the user it awaits `qk/prefs`. A `làm luôn đi` prompt recorded nothing. `/qk-prefs` listed the proposal without editing, treated "ok" as no decision, and on an explicit approval wrote one line to the named target and resolved the proposal. No rules, `CLAUDE.md` or memory file changed. Single runs, not a compliance rate |
| Codex 0.160.0 | `~/.codex/hooks.json`, a project's `.codex/hooks.json`, or `[hooks]` in `config.toml` | One `codex exec` session in a scratch folder: the context was injected, the agent ran `propose` and the proposal landed in the configured store. The prompt asked the agent to follow system guidance, so this proves the plumbing, not how often agents comply |
| omp, Qwen Code | — | Not supported or tested |

Codex skips new or changed hooks until you trust them with `/hooks`; project hooks also need the project's `.codex/` layer to be trusted.

## Known runtime quirks

- **omp print mode.** `omp -p "/skill:qk-plan …"` sends the text to the model unexpanded, for every skill (checked against the built-in `find-skills`). Use an interactive session or RPC mode.
- **omp print-mode inventory.** Asking which skills are available does not list qk skills because they are explicit-only. Check installation by invoking a skill explicitly.
- **Qwen writes skill arguments to disk.** When a skill is invoked, Qwen writes a temporary file under `.qwen/tmp/` in the current repository, even in plan mode. This is Qwen's behaviour, not qk's; consider ignoring `.qwen/` in your repositories.
- **Codex and duplicate directories.** If a skill is linked into two directories Codex reads, it may be listed twice. Pick one.

## Choosing agent and model per task

qk does not add its own model configuration. Use what the runtime already has:

- **omp:** define an agent whose frontmatter points at a role (`model: "@plan"`) and map the role in `modelRoles`, or set `task.agentModelOverrides`. This works even when per-call model overrides are disabled.
- **Claude Code:** `--model`, or subagent definitions with a model.
- **Codex:** `-m <model>`.
- **Qwen Code:** `-m <model>`.

`qk/agent-coord` uses these routes to run a task on the agent and model you name, and reports "blocked" instead of silently falling back to another model. See [qk/agent-coord](skills/qk-agent-coord.md).
