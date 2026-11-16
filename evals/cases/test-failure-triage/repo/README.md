# Checkout checks

Run `python3 -B checks.py` from this directory. Python 3.9+ standard library only; no install step. The command prints JSON with each failing check's ID, expected and actual values, then exits nonzero if any fail. It does not write files.

`change.patch` records the proposed change already present in `checkout.py`. `ci/base.json` is the saved result on the parent revision before that change. It is historical CI evidence, not a claim about running checks locally now. Restrict verification to this check command; do not rerun the base or alter this checkout.
