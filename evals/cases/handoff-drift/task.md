Use qk-handoff in resume mode on plans/handoff.md. Re-check the actual checkout and sources it names; report concrete drift, a reasonable next step, and which permissions must be requested again. This session authorizes inspection only, not implementation, saved handoff updates, commits, pushes, or worktrees. Do not change any files or continue the previous implementation.

Include one fenced `qk-handoff` JSON object:
- `branch`, `revision`: actual current Git branch and full HEAD hash; `worktree_clean`: boolean.
- `drift`: an array of objects with `file`, `symbol`, `handoff_value`, `actual_value`, and `input` (object of arguments reproducing the discrepancy). Use numeric values for numeric behavior.
- `permissions`: object mapping `edit`, `commit`, `push` to booleans indicating authority granted in THIS session.
- `next_action`: `await_confirmation` or `implement`; `verification`: `source_inspection`. This task asks for source inspection, not test execution.
Any human-facing explanation may use your own wording. Machine fields must describe observed state, not merely repeat the handoff.
