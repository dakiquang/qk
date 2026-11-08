---
name: qk-cook
description: >-
  Implement a clear request or an approved plan, verifying and reviewing the work
  itself within the assigned scope. Use only when the user explicitly invokes
  qk/cook (`/qk-cook`, `$qk-cook`, `/skill:qk-cook`). Do not use for ordinary
  code-change requests when the user has not invoked qk/cook.
disable-model-invocation: true
---

# qk/cook

Input: a request with done criteria, or the path to an approved plan (optionally with the phase to work on).

| | |
|---|---|
| **Result** | Changes that meet the done criteria, with verification evidence, strictly within scope |
| **Authority** | Edit files within scope; run the repo's build/test/lint commands. Do not commit, push, merge, tag, deploy or publish anything externally unless the chat explicitly requests that exact action |
| **Done when** | Every done criterion has been verified by a command or scenario with output; failures caused by the change itself are fixed; anything that could not be verified is stated clearly |

## Before editing

1. Read the plan (if any), repo rules and the relevant code. If the plan is older than the current code, re-check its assumptions before working.
2. Missing done criteria, or a behavior-changing decision that sources cannot answer → ask once. Direction still unclear → stop and propose `qk/plan`.
3. The worktree has uncommitted changes unrelated to this task → do not stash, do not overwrite; work around them or ask.
4. Delegated through `qk/agent-coord` to write: work only in the specified worktree.

## Work

- Make the smallest change that achieves the goal, following the repo's existing conventions. No refactoring, renaming or abstractions beyond the request.
- When the plan is wrong or conflicts with the actual code: choose the smallest approach that still meets the goal, and record the decision and reason. If the choice changes user-visible behavior, changes a public API, or exceeds scope → stop and ask.
- Do not add AI author lines, `Co-Authored-By` or "Generated with" unless the repo requires it.

## Verification

- Take commands from the repo: config, CI workflows, manifest scripts, contributing docs. Do not invent commands.
- Exercise exactly the behavior you changed: focused tests, then the related suite; for runnable changes, run it for real once.
- Failures that already exist on base are baseline; record them separately. Do not loosen tests, delete assertions, disable hooks or use `--no-verify` to get green.
- Self-review the diff: only in-scope files, no secrets, no leftover debug code, no unintended changes.
- Significant changes that need an independent view: suggest the user invoke `pr-orchestrator review` or delegate to a reviewer from a different model family through `qk/agent-coord`.

## Report

```text
Done:          <summary>
Files changed: <path — reason>
Verification:  <command → actual result>
Not verified:  <what, why>
Decisions:     <deviations from the plan and reasons, if any>
Next:          <command the user can invoke, e.g. pr-orchestrator review>
```

Update the status in the plan when working from a plan.

## Boundaries

- Higher-priority instructions, runtime rules and repository rules override this skill.
- Language: reply in the user's language unless the user or repository specifies another; localize human-facing report labels. When updating a saved artifact, keep its existing language and format; new artifacts follow user/repository conventions. Commands, paths, identifiers and fixed machine strings stay unchanged.
- Use the available tools, tasks and subagents. Do not change model, permissions, hooks or configuration.
- Do not invoke other qk skills automatically.
