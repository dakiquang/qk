# Task: items missing from collect_all on large accounts

Users with large accounts report that `collect_all` in `collector/collect.py` returns fewer items than the listing API holds. Small accounts look correct. The listing API is paginated: each call returns `{"items": [...], "next": marker or None}`.

Find the root cause, fix it, and add a regression test to the repository's tests that fails without the fix. Keep the change limited to the cause.

Run the repository's tests with `python3 -m unittest` from the repository root before you finish.
