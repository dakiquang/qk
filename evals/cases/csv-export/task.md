# Task: export the current task page as CSV

This request is approved. Implement it; do not ask for approval again.

Add a function `page_to_csv(page) -> str` in a new module `tasklist/csv_export.py`, and its tests in a new file `tests/test_csv_export.py`. `page` is a `tasklist.tasks.Page`. The function returns the CSV text of exactly that page.

Acceptance criteria (taken from the qk case study `docs/en/case-study-csv-export.md`, section "Situation and done criteria"):

- Columns are `title`, `status`, `createdAt`, in that order, with that header row. `createdAt` is `Task.created_at` unchanged. Do not add hidden or internal fields (`id`, `owner`, `internal_notes`).
- Export exactly the rows of `page.items`, in that order. Do not sort, filter or fetch anything else.
- A page with zero rows produces a header-only CSV.
- Unicode, commas, quotes and newlines in values are preserved with correct CSV encoding: parsing the output with Python's `csv.reader` gives back the original values.
- Spreadsheet-formula-like values are neutralised, not only quoted. Policy: if a value, after stripping leading spaces, starts with `=`, `+`, `-` or `@`, or the value starts with a tab or a carriage return, prefix the whole original value with a single quote `'`. Apply this to every exported value. Other values are written unchanged.
- Write the output with the standard library `csv` module (default dialect). Add no dependency.

Change no other files.

Before you finish, run the repository's tests with `python3 -m unittest` from the repository root.
