---
name: qk-plan
description: >-
  Create, audit or revise an implementation plan with sources, decisions, done
  criteria and risks. Use only when the user explicitly invokes qk/plan
  (`/qk-plan`, `$qk-plan`, `/skill:qk-plan`). Do not use for generic planning
  requests when the user has not invoked qk/plan.
disable-model-invocation: true
---

# qk/plan

Three modes, read from the invocation: `create` (default when no plan exists yet), `audit <path>`, `revise <path>`.

| | |
|---|---|
| **Result** | A plan the user can approve: what to do, why, scope, how to verify, risks |
| **Authority** | Read the repo and external sources. Write only the specified plan file or the one the repo convention dictates. Do not edit code, install anything, or switch to implementation |
| **Done when** | Every claim has a source or an inference label; done criteria are verifiable; questions that need a user decision are listed |

## create

1. Clarify the goal, what must not change and what is out of scope from the invocation, prior plans, issues and source code. If an important decision is missing and sources cannot answer it, ask once.
2. Read repo rules and the relevant code. If facts that decide the direction are missing, check them against primary sources or with a quick test in a temporary directory; if lengthy research is needed, stop and propose `qk/research`.
3. Size the plan by risk: small work gets a few items; only large work is split into phases.
4. Write to `plans/<slug>.md`, or wherever the repo has a convention. Do not overwrite an existing plan unless asked.

Suggested structure; drop sections that are not needed:

```markdown
# <Task name>
Status: draft | approved | in progress | done — <date>

## Goal and out of scope
## Current state and evidence   <!-- sources, commands run; mark [Verified] / [Inference] -->
## Decisions                    <!-- what was chosen, why, rejected approaches -->
## Planned changes              <!-- files, interfaces, data -->
## Steps                        <!-- each step: work | done when -->
## Verification                 <!-- commands or scenarios that prove the done criteria -->
## Risks                        <!-- failure signals and how to respond -->
## Open questions
```

## audit

Check the plan against sources, without editing the plan:

- Claims the plan's decisions rest on: re-read the exact source or rerun the stated command; leave the rest as questions.
- Whether done criteria are verifiable; which steps are missing dependencies; whether scope has grown or contradicts settled decisions.
- Each finding: severity (blocker / important / nit), location in the plan, evidence, suggested fix. Without evidence, record it as a question, not an error.
- Another model's opinion is input to verify, not a conclusion.

## revise

Apply the decisions and findings the user has accepted. Then review the whole plan so no other section still contradicts them. Keep the settled-decisions table and record the date of the change. Do not add new scope on your own.

## Report

State the next step as a command for the user to invoke, e.g. `qk/cook <path>`.

Close every report with these four lines, in this order, translating the labels to the user's language; write "none" when a line is empty:

**Done**: what was produced or changed, with paths
**Evidence**: commands run and their results, sources read
**Not verified**: what was not checked, and why
**Needs your decision**: what waits on the user

## Boundaries

- Higher-priority instructions, runtime rules and repository rules override this skill.
- Language: reply in the user's language unless the user or repository specifies another; localize human-facing report labels. When updating a saved artifact, keep its existing language and format; new artifacts follow user/repository conventions. Commands, paths, identifiers and fixed machine strings stay unchanged.
- Use the runtime's plan mode, tasks and tools. Do not change model, permissions, hooks or configuration.
- Do not invoke other qk skills automatically. Plan approval is not permission to commit, merge or release.
