---
name: qk-brainstorm
description: >-
  Compare approaches to an unclear problem, state trade-offs and assumptions to
  verify, then recommend one approach for the user to choose. Use only when the
  user explicitly invokes qk/brainstorm (`/qk-brainstorm`, `$qk-brainstorm`,
  `/skill:qk-brainstorm`).
disable-model-invocation: true
---

# qk/brainstorm

| | |
|---|---|
| **Result** | 2–4 viable approaches, trade-offs, key assumptions and one recommendation. The user chooses the approach |
| **Authority** | Read-only. Write a file only when asked and given a path. Do not implement |
| **Done when** | Each approach has upside, downside and cost of reversal; assumptions that available sources can check have been checked; decisions needed from the user are stated clearly |

## Method

1. Restate the problem in one sentence, with constraints and what must not change. If the problem is misunderstood, every approach is wrong, so ask first if the problem still has two readings with different outcomes.
2. Read related code, docs and prior decisions. Ideas must fit the real system, not an idealized model.
3. Always consider the simplest approach and the "do nothing / do it manually" approach. Drop approaches that violate constraints, with a one-line reason.
4. Compare on: whether it achieves the outcome; reasonable worst case; how hard it is to reverse; maintenance cost; new dependencies.
5. Separate out key assumptions (if wrong, the approach fails). Check now the ones that can be checked quickly; propose `qk/research` for the ones that need research.

## Report

```markdown
Problem: <one sentence> — Constraints: <...>

| Approach | How | Gains | Costs | Reversal |
|---|---|---|---|---|

Key assumptions: <assumption — verified / unverified>
Recommendation: <approach> because <reason>; reconsider if <condition>
User decisions needed: <question>
Next: qk/plan after choosing an approach, or qk/research for unverified assumptions
```

## Boundaries

- Higher-priority instructions, runtime rules and repository rules override this skill.
- Language: reply in the user's language unless the user or repository specifies another; localize human-facing report labels. When updating a saved artifact, keep its existing language and format; new artifacts follow user/repository conventions. Commands, paths, identifiers and fixed machine strings stay unchanged.
- Do not change model, permissions, hooks or configuration. Do not invoke other qk skills automatically.
