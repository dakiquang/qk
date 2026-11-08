---
name: qk-agent-coord
description: >-
  Delegate one bounded task (review, isolated implementation, diagnosis, second
  opinion) to the agent and model the user specifies, then verify the result
  before accepting it. Use only when the user explicitly invokes qk/agent-coord
  (`/qk-agent-coord`, `$qk-agent-coord`, `/skill:qk-agent-coord`).
disable-model-invocation: true
---

# qk/agent-coord

The running session is the **coordinator**: it keeps decisions, checks results and integrates. The delegated agent is the **worker**: its output is unverified evidence.

| | |
|---|---|
| **Result** | The task was delegated to the right agent/model with the right permissions; the results have been checked by the coordinator and classified as accepted / rejected |
| **Authority** | Launch the worker through paths already available on the machine. The worker gets write access only in a separate worktree, and only when the task requires writing. Do not install, log in or change runtime configuration to run a worker. Integrate the worker's diff into the main checkout only with the user's consent |
| **Done when** | There is worker output, the actual model that ran (or "unverified"), and the coordinator's conclusion on each point |

## 1. Define the delegation

- Delegate only to the agent/model the user named. If none is named, ask; do not choose one yourself.
- Choose the smallest sufficient form: a single headless run for a second opinion; a separate terminal or worktree for writing tasks; sequential steps with gates for multi-step chains.
- Write the contract using [references/prompt-templates.md](references/prompt-templates.md). Do not put secrets, `.env`, tokens or personal data in the prompt; tell the worker to read the repo itself.

## 2. Choose an execution path by capability

A path is valid only if it runs **exactly the specified agent and model**, **with the right permissions**, and **with write isolation** when the task writes.

| Path | When to use | Notes |
|---|---|---|
| Subagent of the current runtime | The specified model is selectable in this runtime | omp: agents bind a role via `modelRoles` or `task.agentModelOverrides` and are invoked by agent name; do not depend on per-call model overrides |
| Orca terminal | Long tasks, writing tasks, work that needs observing | Use a separate worktree for writing; Orca does not enforce read-only on its own |
| Headless CLI | An agent other than the current runtime, read tasks | Prompt via stdin, with a timeout; record the command that was run |

CLI flags seen in `--help` (re-check against the installed version before running):

| CLI | Model | Non-interactive | Permission limit |
|---|---|---|---|
| `claude` | `--model` | `-p` | `--permission-mode plan` |
| `codex exec` | `-m` | `exec` | `-s read-only` |
| `qwen` | `-m` | positional prompt, stdin appended | `--approval-mode plan` |
| `omp` | `--model` | `-p` | `--tools` restricts tools |

No path satisfies these conditions → report **blocked** with the reason. Do not silently switch to a default model, another provider or another agent.

## 3. Protect the checkout

- Only one writing agent per checkout. A worker's writes run in a separate worktree on a separate branch.
- A worktree prevents Git collisions; it is **not a sandbox**: network, credentials and files outside the repo are still governed by the runtime's permissions.
- Read-only tasks: use the runtime's permission-limiting mode from the table above — that is the primary barrier. For additional evidence, run these commands before and after the worker runs and compare the output:

  ```bash
  git rev-parse --verify -q HEAD
  git status --porcelain --ignored --untracked-files=all
  git ls-files --stage -z
  git ls-files -z -co --exclude-standard | xargs -0 shasum
  ```

  This set checks HEAD, status, staged blob IDs/modes and tracked/non-ignored untracked working-tree contents, including files that were already dirty. On a repo with no commits, the HEAD check exits nonzero; record that state and still run the other checks. Plain porcelain status does not expose staged content changes when the status flags stay the same. These checks still do **not** cover pre-existing ignored-file contents or files outside the repo; state those limits in the report.
- Unexpected changes → stop and report the changed files. Do not revert or stash on your own.
- A timeout does not prove the worker has stopped. Do not reassign a writing task in the same area until you are sure the old worker has exited. Do not automatically rerun tasks that have external effects.

## 4. Check results

- Review: accept only findings that are reproducible, in scope, and backed by `file:line` evidence the coordinator has re-read.
- Implementation: read the diff in the worker's worktree, run the relevant verification, and only then propose integration.
- Two models agreeing does not replace re-reading the evidence.
- Follow-up fixes: send a short prompt containing only the accepted points and the stop condition.

## Report

```text
Worker:     <agent> / requested model <...> / actual model <... or unverified>
Path:       <subagent / orca / headless — command>
Result:     <summary>
Accepted:   <point — verified evidence>
Rejected:   <point — reason>
Checkout:   <unchanged / unexpected changes: ...>
Next:       <what the user needs to decide>
```

## Boundaries

- Higher-priority instructions, runtime rules and repository rules override this skill.
- Language: reply in the user's language unless the user or repository specifies another; localize human-facing report labels. When updating a saved artifact, keep its existing language and format; new artifacts follow user/repository conventions. Commands, paths, identifiers and fixed machine strings stay unchanged.
- Use the runtime's existing task, subagent and model-binding mechanisms. Do not change model, permissions, hooks or configuration.
- Do not invoke other qk skills automatically.
