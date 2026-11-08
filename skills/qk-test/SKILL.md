---
name: qk-test
description: >-
  Independently verify a change with test, lint and typecheck commands discovered
  from the repo; report actual results, classify new failures versus baseline,
  and never edit to make it green. Use only when the user explicitly invokes
  qk/test (`/qk-test`, `$qk-test`, `/skill:qk-test`).
disable-model-invocation: true
---

# qk/test

Use when verification must be broader than, or independent of, the checks in `qk/cook`, e.g. before merging, after someone else's change, or on a different environment.

| | |
|---|---|
| **Result** | Commands run, exit codes, new failures versus baseline, test coverage gaps |
| **Authority** | Run the repo's check commands. Do not edit code, change test configuration, install new dependencies or commit |
| **Done when** | Every command has an actual result; failures are classified; anything that could not run has a reason |

## Method

1. Discover commands in this order: repo docs, CI workflows, manifest scripts (`package.json`, `composer.json`, `Makefile`...). Do not presuppose a tool or package manager.
2. Determine scope: tests for the changed part first, then broader suites if requested or if the change touches shared interfaces.
3. Run and keep the output. For long output, write it to a temporary file and quote only the failing part.
4. When failures appear: check whether they occur on base (read base CI, or run on base when the user permits creating a temporary worktree). If present on base, it is baseline and not attributed to the change.
5. Flaky failures: rerun at most twice, record both results, do not call it a pass.
6. List changed behavior that no test touches.

## Report

```text
| Command | Exit | Result |
New failures:  <test — message — suspected cause>
Baseline:      <pre-existing failures>
Flaky:         <...>
Not verified:  <behavior / environment — reason>
```

Report remote CI status as CI, not as local tests.

## Boundaries

- Higher-priority instructions, runtime rules and repository rules override this skill.
- Language: reply in the user's language unless the user or repository specifies another; localize human-facing report labels. When updating a saved artifact, keep its existing language and format; new artifacts follow user/repository conventions. Commands, paths, identifiers and fixed machine strings stay unchanged.
- Do not change model, permissions, hooks or configuration. Do not invoke other qk skills automatically.
