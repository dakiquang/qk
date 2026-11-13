# Runtimes

[Tiếng Việt](../vi/runtimes.md) · [Docs index](README.md)

qk extends a runtime; it never replaces its tools, plan mode, task lists, subagents, model settings, permissions or hooks. Higher-priority instructions, runtime rules and repository rules (`AGENTS.md`, `CLAUDE.md`, contributing docs) always win over a qk skill.

## Support

| Runtime | Status |
|---|---|
| Claude Code | Smoke-checked |
| Codex | Smoke-checked |
| omp | Smoke-checked in RPC mode; print mode does not expand `/skill:` (see [quirks](#known-runtime-quirks)) |
| Qwen Code | Linked but not checked; the explicit-only setting is unconfirmed |
| Orca | Nothing to install; it lists the skills of the agents it runs |

"Smoke-checked" means the [manual checklist](evidence.md#manual-smoke-checklist) passed on the version recorded in [Test evidence](evidence.md). It is not certification, and a newer release of a runtime can change the result.

## Explicit-only invocation

A qk skill should run only when you call it. A name alone does not guarantee this: a skill whose description says "use when planning" could compete with a runtime's own plan mode or bundled commands. qk uses two safeguards.

1. **Each runtime's own setting** stops the model from loading the skill by itself.
2. **Descriptions name the explicit trigger** (`qk/plan`, `/qk-plan`, `$qk-plan`, `/skill:qk-plan`) instead of generic task words.

| Runtime | Setting in qk | Effect |
|---|---|---|
| Claude Code | `disable-model-invocation: true` in `SKILL.md` | Only you can invoke the skill. Claude Code documents that this also keeps it from being preloaded into subagents |
| omp | Same field, read as `disableModelInvocation` | Hidden from automatic invocation |
| Codex | `agents/openai.yaml`: `policy.allow_implicit_invocation: false` | Not invoked implicitly |
| Qwen Code | No setting confirmed yet | Unknown |

By contract, qk skills do not load one another. They name the next command for you to run. This is a workflow boundary, not a security guarantee on an unverified runtime.

`scripts/validate.py` enforces both safeguards. It accepts only one canonical shape for `agents/openai.yaml` (two blocks, two-space indent, double-quoted strings without backslashes, full-line comments), so no YAML variant can hide a different policy.

## Preference hook

The opt-in [preference hook](preference-hook.md) is a `UserPromptSubmit` command hook. Claude Code and Codex document the same output shape (`hookSpecificOutput.additionalContext`), and the hook prints that shape for both.

| Runtime | Where you register it |
|---|---|
| Claude Code | `hooks` in `settings.json` (user) or `.claude/settings.local.json` (project) |
| Codex | `~/.codex/hooks.json`, a project's `.codex/hooks.json`, or `[hooks]` in `config.toml` |
| omp, Qwen Code | Not supported or tested |

Codex skips new or changed hooks until you trust them with `/hooks`; project hooks also need the project's `.codex/` layer to be trusted. What was checked on each runtime is in [Test evidence](evidence.md#preference-hook).

## Known runtime quirks

- **omp print mode.** `omp -p "/skill:qk-plan …"` sends the text to the model unexpanded, for every skill, including omp's built-in ones. Use an interactive session or RPC mode.
- **omp skill inventory.** Asking which skills are available does not list qk skills, because they are explicit-only. Check an installation by invoking a skill explicitly.
- **Qwen writes skill arguments to disk.** When a skill is invoked, Qwen writes a temporary file under `.qwen/tmp/` in the current repository, even in plan mode. This is Qwen's behaviour, not qk's; consider ignoring `.qwen/` in your repositories.
- **Duplicate skill directories.** If a skill is linked into two directories one runtime reads, it may be listed twice. Pick one.

## Choosing agent and model per task

qk adds no model configuration of its own. Use what the runtime already has:

- **omp:** define an agent whose frontmatter points at a role (`model: "@plan"`) and map the role in `modelRoles`, or set `task.agentModelOverrides`. This works even when per-call model overrides are disabled.
- **Claude Code:** `--model`, or subagent definitions with a model.
- **Codex:** `-m <model>`.
- **Qwen Code:** `-m <model>`.

`qk/agent-coord` uses these routes to run a task on the agent and model you name, and reports `blocked` instead of silently falling back to another model. See [qk/agent-coord](skills/qk-agent-coord.md).
