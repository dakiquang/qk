---
name: qk-debug
description: >-
  Find the root cause of a bug through an evidence chain and reproduction, then
  propose the smallest fix; does not edit code by default. Use only when the user
  explicitly invokes qk/debug (`/qk-debug`, `$qk-debug`, `/skill:qk-debug`).
disable-model-invocation: true
---

# qk/debug

| | |
|---|---|
| **Result** | Root cause with `file:line` evidence, a reproduction, a proposed fix and how to verify after the fix |
| **Authority** | Read, run reproductions, run existing tests. Temporary diagnostic logs or scripts only when needed, and they must be removed before reporting. Do not edit product code unless the chat asks for a fix |
| **Done when** | There is a reproduction command (or a reason it cannot be reproduced); the cause explains all symptoms; rejected hypotheses have reasons |

## Method

1. Record the exact symptom: error, input, environment, since when. Distinguish what the user observed from what you inferred.
2. Reproduce with the smallest command. If it cannot be reproduced, narrow the conditions before guessing.
3. Narrow the area: compare against base or a working version, read logs, bisect commits or input.
4. Pair each hypothesis with a test that could refute it. Run the test and record the result. Do not try fixes just to see whether the bug goes away.
5. Separate symptom from cause: fix where the error surfaces, or where the bad data originates? Look for the same bug pattern elsewhere.
6. If the failure comes from the environment or tooling, not the code: state it clearly and do not propose code changes.

## Report

```text
Symptom:       <...>
Reproduction:  <command> → <result>
Cause:         <file:line — mechanism>
Ruled out:     <hypothesis — why>
Proposed fix:  <smallest> — verify with: <command>
```

If the user wants a fix: give a `qk/cook` command with the verified cause as input. If the chat has already asked for an immediate fix, follow the qk/cook contract: smallest change, rerun the reproduction command and regression tests.

Close every report with these four lines, in this order, translating the labels to the user's language; write "none" when a line is empty:

**Done**: what was produced or changed, with paths
**Evidence**: commands run and their results, sources read
**Not verified**: what was not checked, and why
**Needs your decision**: what waits on the user

## Boundaries

- Higher-priority instructions, runtime rules and repository rules override this skill.
- Language: reply in the user's language unless the user or repository specifies another; localize human-facing report labels. When updating a saved artifact, keep its existing language and format; new artifacts follow user/repository conventions. Commands, paths, identifiers and fixed machine strings stay unchanged.
- Use the runtime's debugger and tools. Do not change model, permissions, hooks or configuration.
- Do not invoke other qk skills automatically.
