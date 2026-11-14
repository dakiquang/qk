import csv
import importlib
import io
import unittest
from unittest import mock

import tasklist.csv_export as csv_export
from tasklist.csv_export import page_to_csv
from tasklist.tasks import Page, Task

HEADER = ["title", "status", "createdAt"]


def task(title, status="open", created="2026-11-02T09:30:00Z", n=1):
    return Task(id=n, title=title, status=status, created_at=created, owner="owner-secret-7", internal_notes="note-secret-9")


def rows(page):
    text = page_to_csv(page)
    if not isinstance(text, str):
        raise AssertionError(f"page_to_csv returned {type(text).__name__}, not str")
    return list(csv.reader(io.StringIO(text, newline="")))


class CsvExportHiddenTest(unittest.TestCase):
    def test_header_and_columns(self):
        parsed = rows(Page(items=[task("Write docs", "done", "2026-11-03T10:00:00Z")]))
        self.assertEqual(parsed, [HEADER, ["Write docs", "done", "2026-11-03T10:00:00Z"]])

    def test_zero_rows_is_header_only(self):
        self.assertEqual(rows(Page(items=[])), [HEADER])

    def test_display_order_is_kept(self):
        items = [task("zeta", n=1, created="2026-11-09T00:00:00Z"), task("alpha", n=2, created="2026-11-01T00:00:00Z"),
                 task("mid", n=3, created="2026-11-05T00:00:00Z")]
        self.assertEqual([row[0] for row in rows(Page(items=items))[1:]], ["zeta", "alpha", "mid"])

    def test_internal_fields_are_absent(self):
        text = page_to_csv(Page(items=[task("Plain", n=424242)]))
        for secret in ("owner-secret-7", "note-secret-9", "424242"):
            self.assertNotIn(secret, text)

    def test_special_characters_round_trip(self):
        values = ['Café, "quoted" text', "line one\nline two", "日本語 — ünïcødé", 'trailing comma,', "a=b", "plan-b"]
        parsed = rows(Page(items=[task(value, n=i) for i, value in enumerate(values)]))
        self.assertEqual([row[0] for row in parsed[1:]], values)

    def test_formula_like_values_are_neutralised(self):
        values = ["=SUM(A1:A2)", "+1", "-1", "@cmd", "  =HYPERLINK(1)", "\tindent", "\rreturn"]
        parsed = rows(Page(items=[task(value, n=i) for i, value in enumerate(values)]))
        self.assertEqual([row[0] for row in parsed[1:]], ["'" + value for value in values])

    def test_every_column_is_neutralised(self):
        parsed = rows(Page(items=[task("ok", status="=1+1", created="@2026")]))
        self.assertEqual(parsed[1], ["ok", "'=1+1", "'@2026"])

    def test_output_is_written_with_the_csv_module(self):
        # csv.DictWriter calls csv.writer; the reload also catches `from csv import writer`.
        try:
            with mock.patch("csv.writer", wraps=csv.writer) as writer:
                importlib.reload(csv_export)
                csv_export.page_to_csv(Page(items=[task("Plain")]))
        finally:
            importlib.reload(csv_export)
        self.assertTrue(writer.called, "page_to_csv did not write through csv.writer or csv.DictWriter")


if __name__ == "__main__":
    unittest.main()
