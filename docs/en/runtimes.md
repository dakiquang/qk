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

## Known runtime quirks

- **omp print mode.** `omp -p "/skill:qk-plan …"` sends the text to the model unexpanded, for every skill (checked against the built-in `find-skills`). Use an interactive session or RPC mode.
- **Qwen writes skill arguments to disk.** When a skill is invoked, Qwen writes a temporary file under `.qwen/tmp/` in the current repository, even in plan mode. This is Qwen's behaviour, not qk's; consider ignoring `.qwen/` in your repositories.
- **Codex and duplicate directories.** If a skill is linked into two directories Codex reads, it may be listed twice. Pick one.

## Choosing agent and model per task

qk does not add its own model configuration. Use what the runtime already has:

- **omp:** define an agent whose frontmatter points at a role (`model: "@plan"`) and map the role in `modelRoles`, or set `task.agentModelOverrides`. This works even when per-call model overrides are disabled.
- **Claude Code:** `--model`, or subagent definitions with a model.
- **Codex:** `-m <model>`.
- **Qwen Code:** `-m <model>`.

`qk/agent-coord` uses these routes to run a task on the agent and model you name, and reports "blocked" instead of silently falling back to another model. See [qk/agent-coord](skills/qk-agent-coord.md).
