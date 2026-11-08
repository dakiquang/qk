# qk/cook

[Tiếng Việt](../../vi/skills/qk-cook.md) · [Docs index](../README.md) · [Skill source](../../../skills/qk-cook/SKILL.md)

## When to use it

Use this for a clear request with completion criteria, or an approved plan. It is the implementation command, not another planning layer.

## Example input

```text
/qk-cook plans/health-endpoint.md Implement the approved plan. Verify the endpoint on the running app. Do not commit or push.
```

For a small task, give the behaviour directly instead of creating a plan only to satisfy a pipeline. Include what must stay unchanged and how success can be observed.

## What happens

1. Read the request/plan, repository rules and related code. Recheck assumptions if the code has moved since the plan.
2. Preserve unrelated local work; do not stash or overwrite it.
3. Implement the smallest in-scope change using existing conventions.
4. Discover verification commands from the repository, run focused and relevant checks, and exercise runnable changed behaviour once.
5. Self-review the diff for scope, secrets and leftover diagnostics. Update progress in the plan when implementing one.

A plan mismatch gets the smallest goal-preserving correction with a reason. A change to user-visible behaviour, public API or scope needs your decision before proceeding.

## Output, authority and completion

Report implemented behaviour, changed files and reasons, actual commands/results, unverified areas and deviations from the plan. Existing failures are baseline, not permission to weaken tests or bypass hooks.

May edit in-scope files and run repository checks. No commit, push, merge, tag, deployment or publication without explicit authority for that action. A delegated writing task stays in its assigned worktree.

Done means all agreed criteria have observed evidence and introduced failures are fixed. For an independent view, explicitly request the separate `pr-orchestrator` for a PR review, or `qk/agent-coord` with a named reviewer/model. `qk/test` is optional independent or broader verification, not a mandatory next stage.

All higher-priority, runtime and repository rules still apply. This skill does not change models, permissions, hooks or configuration, and never invokes another qk skill automatically.
