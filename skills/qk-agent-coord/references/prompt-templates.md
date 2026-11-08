# Delegation prompt templates

Use one template per delegation. Replace the parts in curly braces and drop lines that are not needed. Send via stdin.

## Shared context pack

```text
You are a delegated agent. A coordinator in another session holds the final decision.

Role: {reviewer | implementer | tester | debugger | advisor}
Repo: {name or path}
Task: {one sentence}
Scope: {files, feature, commit or diff}
Must not change: {behavior, API, files}
Done criteria:
- {condition}

Project rules: read AGENTS.md, CLAUDE.md and contributing docs, if present, before working.
Keep the existing architecture and naming conventions. Do not expand scope.

Write your report in {the language the user requested}; keep commands, paths, identifiers, file:line references and fixed strings such as APPROVE, NEEDS_CHANGES, P0, P1, P2 exactly as written.

Permissions: {read-only | edit files in scope, in worktree {path}}
Do not commit, push, comment or merge unless the permissions line above allows it.
Stop condition: {when to stop and report instead of guessing}
Do not ask for or print secrets, credentials, tokens or .env contents.
```

## Read-only review

Append to the context pack:

```text
Review the change; do not edit files and do not create commits.
Consider: correctness, security, regressions, edge cases, missing tests.

Return exactly these sections:
1. Verdict: APPROVE or NEEDS_CHANGES
2. Findings by severity P0, P1, P2
3. For each finding: file:line, problem, consequence, concrete fix, what you read or ran to reach the conclusion
4. Commands run and their results
5. The actual model id you are running, if known
6. Assumptions or questions

Do not treat style preferences as blockers. If there are no findings, say what you checked.
```

## Isolated implementation

```text
Work in the assigned worktree and do not leave it.
- Edit only the files needed for the scope.
- Do not touch unrelated changes.
- Do not commit unless asked.
- Run the tests, lint or checks appropriate to the change.

Return:
1. Summary of changes
2. Files changed and why
3. Commands run and their results
4. Remaining risks
5. List of items for the coordinator to re-check
```

## Diagnosis

```text
Diagnose before proposing a fix. Reproduce if possible.
Do not edit files unless the permissions line allows it.

Return:
1. Reproduction status and command
2. Observed behavior versus expected
3. Root cause with file:line
4. Smallest fix
5. How to verify after the fix
```

## Follow-up fix after review

```text
The coordinator accepted only the following points:
- {file:line} {point}

Handle only these points, in the current worktree.
Do not revisit rejected points, do not expand scope, do not commit.
Run focused verification and report the files changed and the results.
Stop and ask if the fix conflicts with project rules or the done criteria.
```
