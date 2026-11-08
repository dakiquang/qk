---
name: qk-research
description: >-
  Answer a decision-relevant question using primary sources and controlled
  experiments, clearly separating what was verified from inference. Use only when
  the user explicitly invokes qk/research (`/qk-research`, `$qk-research`,
  `/skill:qk-research`).
disable-model-invocation: true
---

# qk/research

| | |
|---|---|
| **Result** | A sourced answer to a specific question, and how it changes the decision |
| **Authority** | Read sources inside and outside the repo; experiment in a temporary directory. Do not install global packages, change configuration, or send code or sensitive data to external services |
| **Done when** | Every conclusion has a source or a reproduction command; conflicts between sources are stated; limits of the evidence are recorded |

## Method

1. Write down the question and what would change in the decision if the answer is A or B. If no decision depends on it, ask about the purpose before digging deeper.
2. Prefer primary sources: source code, official docs for the version in use, changelogs, the project's issues. Blogs and forum answers are only leads.
3. Docs and real behavior can differ. When cheap, test for real in a temporary directory with a **control**: also run the case without the change to prove the test can distinguish outcomes.
4. Record tool versions and environment for every experiment.
5. Clean up the temporary directory when done.

## Report

```markdown
Question: <...> — Decision that depends on it: <...>
Answer: <short>

| Conclusion | Evidence | Level |
|---|---|---|
| <...> | <link / file:line / command + output> | verified / inference |

Limits: <what was not tested, which version, which environment>
Impact: <how the decision should change>
```

If asked to write into a plan, add only to that plan's evidence section and leave the rest unchanged.

## Boundaries

- Higher-priority instructions, runtime rules and repository rules override this skill.
- Language: reply in the user's language unless the user or repository specifies another; localize human-facing report labels. When updating a saved artifact, keep its existing language and format; new artifacts follow user/repository conventions. Commands, paths, identifiers and fixed machine strings stay unchanged.
- Use the runtime's search and web-reading tools. Do not change model, permissions, hooks or configuration.
- Do not invoke other qk skills automatically.
