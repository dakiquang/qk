# qk/debug

[Tiếng Việt](../../vi/skills/qk-debug.md) · [Docs index](../README.md) · [Skill source](../../../skills/qk-debug/SKILL.md)

## When to use it

Use this when you have a symptom but not a verified cause. Supply the exact error, input, environment and when it started. A tool/authentication failure should not become a product-code patch.

## Example input

```text
/qk-debug The import command fails only with an empty CSV. Here is the exact command and error: <paste redacted output>. Find the root cause; do not modify product code.
```

## What you get

The smallest reproduction (or the reason it cannot be reproduced), a causal explanation with `file:line` evidence, hypotheses rejected by discriminating experiments, the smallest proposed fix and the command that would verify it. Each hypothesis needs a test that could disprove it; speculative edits are not diagnosis.

## Authority and completion

May read, reproduce and run existing tests. Temporary diagnostic logs/scripts are allowed only when needed and must be removed before reporting. Product code is unchanged unless you explicitly asked for a fix.

If you did ask to fix immediately, it follows the cook contract inline: smallest change, rerun the reproduction and relevant regression checks. It does not load another qk skill.

Done means the cause explains the symptoms and evidence distinguishes it from alternatives. If you requested diagnosis only, invoke `qk/cook` with the verified cause when you want the fix implemented.

All higher-priority, runtime and repository rules still apply. This skill does not change models, permissions, hooks or configuration, and never invokes another qk skill automatically.
