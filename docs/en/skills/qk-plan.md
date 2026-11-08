# qk/plan

[Tiếng Việt](../../vi/skills/qk-plan.md) · [Docs index](../README.md) · [Skill source](../../../skills/qk-plan/SKILL.md)

## When to use it

Use this before a change that needs explicit scope, decisions and verifiable completion criteria. A small change gets a short plan; phases are for genuine complexity, not ceremony.

## Modes and examples

```text
/qk-plan create Add a health endpoint. It must not require authentication or expose secrets. Follow this repo's conventions.
/qk-plan audit plans/health-endpoint.md
/qk-plan revise plans/health-endpoint.md Apply the accepted findings from this conversation; keep the scope unchanged.
```

`create` is the default when no plan exists. It writes `plans/<slug>.md` or the repository's conventional location, without overwriting an existing plan unless requested. `audit` reads the plan against current sources and does not edit it. `revise` applies decisions and findings you accepted and removes contradictions across the whole plan.

## What you get

Goal and non-goals, current evidence, decisions and rejected alternatives, intended interfaces/files, steps with done criteria, verification, risks and unresolved decisions. Claims have sources or an inference label. Audit findings have severity (`blocker`, `important`, `nit`), location, evidence and proposed correction; unsupported concerns are questions, not findings.

## Authority and completion

Only plan files may be written. No product code, installation or automatic implementation. A material decision unavailable from sources is asked once rather than guessed. The result includes the path, changes and remaining decisions.

Done means you can approve a bounded plan and every completion criterion can be checked. Approval is not commit, push, merge or release authority. After approving, invoke `qk/cook <path>` yourself.

All higher-priority, runtime and repository rules still apply. This skill does not change models, permissions, hooks or configuration, and never invokes another qk skill automatically.
