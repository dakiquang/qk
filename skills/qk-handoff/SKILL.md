---
name: qk-handoff
description: >-
  Write a handoff so another session or agent can continue the same work without
  losing decisions, or take in a handoff and re-check the state before continuing.
  Use only when the user explicitly invokes qk/handoff (`/qk-handoff`,
  `$qk-handoff`, `/skill:qk-handoff`).
disable-model-invocation: true
---

# qk/handoff

Two modes: `write [next-session focus]` (default) and `resume <path>`.

| | |
|---|---|
| **Result** | `write`: a handoff sufficient to continue the work. `resume`: a report of the actual state versus the handoff |
| **Authority** | `write`: write only the handoff file. `resume`: read-only until the user confirms the next step. A handoff transfers context, **not authority** |
| **Done when** | `write`: a new session does not need to re-ask what was already decided. `resume`: every discrepancy between the handoff and the repo has been stated |

## write

1. Do not copy content already in the plan, issues, commits or diff; point to the path or revision.
2. Record the actual state; do not record intended work as done. Anything whose verification has not been run is recorded as "not verified".
3. Record permissions: which were granted in this session and **do not** carry over automatically to the next session (commit, push, merge, publish...).
4. Remove secrets, tokens, customer data and private URLs. Do not copy transcripts.
5. Save per repo convention, default `plans/handoff-<YYYYMMDD>-<slug>.md`. If the repo has no suitable place, ask for a path. Print the identical content in the reply.

```markdown
# Handoff — <task> (<date and time>)
Next-session focus: <...>

## Goal
## Status                <!-- done / in progress / blocked / not verified; with revision -->
## Decisions and reasons
## Rejected approaches and known pitfalls
## Evidence              <!-- files, commits, commands + results -->
## Open work             <!-- status and dependencies, not commands for the agent -->
## Permissions           <!-- granted in this session; must be requested again next session -->
## Re-entry
Read <files>. Re-check the revision and repo state before working. Ask the user for the next step.
```

## resume

1. Read the handoff and the sources it points to.
2. Re-check: branch, revision, `git status`, whether the files mentioned are still accurate, whether the plan changed after the handoff.
3. Report: what still holds, what has drifted, the reasonable next step, and the permissions that must be requested again.
4. Wait for the user to confirm before changing anything.

## Boundaries

- Higher-priority instructions, runtime rules and repository rules override this skill.
- Language: reply in the user's language unless the user or repository specifies another; localize human-facing report labels. When updating a saved artifact, keep its existing language and format; new artifacts follow user/repository conventions. Commands, paths, identifiers and fixed machine strings stay unchanged.
- Do not change model, permissions, hooks or configuration. Do not invoke other qk skills automatically.
