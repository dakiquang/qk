# Philosophy

[Tiếng Việt](../vi/philosophy.md) · [Docs index](README.md)

> **Understand enough to decide.** Getting code to run is easy now; what stays hard is seeing clearly enough to make the call. qk optimizes only for that.

Most kits help AI do more on its own, or add an orchestration layer above the agent. qk goes the other way: each skill does one job, then hands back what you need to decide, and no more.

## Three principles

| # | Principle | Means | Does not mean |
|---|---|---|---|
| 1 | **Three roles: make, check, decide** | Whoever makes a change is not the final checker of it. Authority to commit, push, merge, tag, deploy or publish stays with you and does not carry over to another session. A new decision or new authority means stop and ask | Every task needs two models. For a small, reversible change, a command that runs is the checker |
| 2 | **Evidence, not claims** | Know what "done" means before starting. Reports separate what was seen (commands run, files read), what another party reviewed, and what was only told; what was not checked is said. Decisions are written to a plan or handoff file, not left in chat | Every sentence needs proof. Only conclusions you decide on do |
| 3 | **Enough** | Check only what could change the decision, once, the cheapest sufficient way; reuse what this session already saw; list the rest as not verified and move on. At most one review round and one fix round; remaining disagreement goes to you. Pick the process by what is missing; there is no mandatory pipeline. The kit stays small, loads nothing by default, and leaves tools, models, permissions and repository rules to the runtime | Skipping checks. What changes the decision must still be seen |

Principle 3 is the brake on the first two: separating roles and demanding evidence without a limit turns into checking and rechecking, spending tokens without adding understanding.

Every report ends with four lines in this order: **Done**, **Evidence**, **Not verified**, **Needs your decision**. The last line is the only one you must read.

## What each skill does

| Role | Skills |
|---|---|
| Offer options and evidence, not choose | [brainstorm](skills/qk-brainstorm.md), [research](skills/qk-research.md) |
| Make | [cook](skills/qk-cook.md), [plan](skills/qk-plan.md) (create, revise), [release-notes](skills/qk-release-notes.md) |
| Check | [test](skills/qk-test.md), [plan](skills/qk-plan.md) (audit), [debug](skills/qk-debug.md), [dogfood](skills/qk-dogfood.md) |
| Hand over work, not authority | [handoff](skills/qk-handoff.md), [agent-coord](skills/qk-agent-coord.md) |
| Carry out authority you granted | [commit](skills/qk-commit.md), [prefs](skills/qk-prefs.md) |

Skills never call each other; each one names the next command and you decide whether to run it.

## When you want more automation

[`qk-run`](runner.md) chains the roles for one task: one agent makes the change, the runner runs the plan's checks itself, a model from a different family reviews, at most one fix round follows, and a pull request opens. You approve the plan at the start and merge at the end. Any automation added later keeps the same three principles: it may automate making and checking, never deciding.

## A note

This frame grew out of a daily working habit: write down what was done, what was checked, and what is still a guess. Only later did it become clear that it echoes a few Buddhist ideas: hear, reflect, then see for yourself; say what is true and name what you do not know; avoid both extremes.
