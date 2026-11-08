# qk/agent-coord

[Tiếng Việt](../../vi/skills/qk-agent-coord.md) · [Docs index](../README.md) · [Skill source](../../../skills/qk-agent-coord/SKILL.md)

## When to use it

Use this for a bounded second opinion, review, isolated implementation or diagnosis by an agent **and model you name**. The coordinator owns decisions and validation; worker output is unverified evidence until checked.

## Example input

```text
/qk-agent-coord Ask Codex with model gpt-6.1-sol to audit plans/health-endpoint.md against the current repo. Read-only. Require evidence for each finding. Do not edit the plan or install/configure anything.
```

If agent/model is missing, the skill asks rather than choosing. For writing work, specify scope and acceptance criteria; the worker needs a separate worktree/branch, and integration into the primary checkout needs your agreement.

## Execution contract

Use the smallest existing route that can honour the exact agent/model and permissions: native subagent with configured model binding, a visible Orca terminal, or a headless CLI. Inspect the installed CLI's help before relying on flags. In omp, per-call overrides may be disabled; a preconfigured agent/role is the native alternative, not a reason to change your configuration.

No valid route, missing login, quota or unavailable model means **blocked**, with the reason. Never silently substitute a default model or provider. Do not install tools, log in or change runtime configuration. See the [worker prompt templates](../../../skills/qk-agent-coord/references/prompt-templates.md).

## Isolation and evidence

One writer per checkout. A worktree prevents Git collisions; it is not a network/credential/filesystem sandbox. For read-only work, native permission limits are primary. The skill's before/after Git revision, full status and tracked/untracked content checks provide additional evidence but do not prove universal immutability: existing ignored-file contents and files outside the repo are not covered, among other limits.

Unexpected mutations are reported without reverting or stashing. A timeout does not prove a worker stopped; do not reassign a writing area until termination is known, or automatically retry external effects.

## Output and completion

Report requested and actual model (or `unverified`), route/command, output, accepted findings with checked evidence, rejected findings with reasons and checkout state. Review findings must be reproducible and in scope. Implementation needs diff review and relevant verification before proposing integration. Two models agreeing is not proof.

Done means worker output has been independently classified. A blocked route is reported as blocked, not successful delegation. You decide any integration or next invocation.

All higher-priority, runtime and repository rules still apply. This skill does not change models, permissions, hooks or configuration, and never invokes another qk skill automatically.
