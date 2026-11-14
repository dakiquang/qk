# Load bundle documents with strict validation

Status: approved

## Goal

Add `load_bundle(doc)` in a new module `bundle/loader.py`. `doc` is a bundle document already parsed from JSON (a `dict`). The function returns a `bundle.models.Bundle`.

`load_bundle` must reject every structurally invalid bundle with `BundleError`. It must never raise another exception type, and it must never return a `Bundle` whose fields do not match the types declared in `bundle/models.py`.

## Rules

A valid document has this shape (unknown fields are ignored):

- The document is a `dict`.
- `name`: a non-empty string.
- `capacity`: an integer of at least 1. A boolean is not an integer here, and a numeric string is not accepted.
- `policy`: a `dict` with `name` (a string) and `statement`.
- `policy.statement`: a `dict` with `effect` (`"Allow"` or `"Deny"`) and `actions` (a list of strings). It is required; `null`, an empty object or a missing statement is invalid.
- `versions`: a list. Each entry is a `dict` with `name` (a string) and `created` (a string).

## Changes

- `bundle/loader.py`: `load_bundle` and private helpers.
- `tests/test_loader.py`: a valid bundle loads; invalid documents raise `BundleError`.

No other files change. Standard library only.

## Verification

```qk-verify
python3 -m unittest
```
