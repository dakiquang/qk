# Approved plan: stop `test_latency_budget` failing when the machine is briefly busy

This plan is approved. Implement it; do not ask for approval again.

## Goal

`Hook.test_latency_budget` in `tests/test_prefs.py` must stop failing at random when the machine is busy for a moment. The budget stays 0.05 s of extra cost for the hook over a bare interpreter start.

## Evidence

- `tests/test_prefs.py`: `p95()` runs one command 20 times and takes the second slowest sample. The test runs the whole `bare` series (`[sys.executable, "-I", "-S", "-c", "pass"]`) and then the whole `hook` series (`[sys.executable, "-I", "-S", str(SCRIPT), "hook"]`), then checks `hook - bare < 0.05`. The two series run at different times, so two slow samples in the `hook` series are enough to fail it. This matches the reported failure ("hook p95 392 ms") that passes when run alone.

## Decision

Measure in pairs: each round runs `bare` and then `hook` right after it and records `hook - bare`. Both runs of a pair see the same machine load, so the shared load cancels out. Compare `statistics.median` of the differences with `0.05`. With 21 pairs the median only moves when more than 10 pairs are skewed.

## Change

In `tests/test_prefs.py`, replace `p95()` and the two series with:

```python
# Each hook run is paired with a bare run right before it, so a burst of machine
# load hits both sides of a pair; the median ignores the pairs it skews.
payload = json.dumps({"prompt": "From now on use pnpm"})
bare = [sys.executable, "-I", "-S", "-c", "pass"]
hook = [sys.executable, "-I", "-S", str(SCRIPT), "hook"]
extra = [elapsed(hook, payload) - elapsed(bare, "") for _ in range(21)]
cost = statistics.median(extra)
self.assertLess(cost, 0.05, f"hook median extra {cost * 1000:.0f} ms over {len(extra)} pairs")
```

`elapsed(command, stdin)` times one `subprocess.run` with `time.perf_counter`, as `p95()` did.

Note on order: in a subtraction Python evaluates the left operand first, so `elapsed(hook, ...)` runs before `elapsed(bare, ...)`. To keep the bare → hook order this plan requires, write the loop out: `b = elapsed(bare, ""); h = elapsed(hook, payload); extra.append(h - b)`.

Keep the `CI` skip. Change only `tests/test_prefs.py`.

## Verification

- `CI=1 python3 -m unittest` passes from the repository root.
- `python3 -m unittest tests.test_prefs` passes on an idle machine.
