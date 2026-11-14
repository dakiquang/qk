import unittest

from collector.collect import collect_all


def listing(pages):
    calls = []

    def fetch_page(marker):
        calls.append(marker)
        if marker not in pages:
            raise AssertionError(f"unexpected marker {marker!r}")
        if len(calls) > 20:
            raise AssertionError("collect_all kept fetching")
        return pages[marker]
    return fetch_page, calls


class CollectHiddenTest(unittest.TestCase):
    def test_empty_page_with_marker_does_not_end_the_listing(self):
        fetch, calls = listing({None: {"items": ["a", "b"], "next": "m1"},
                                "m1": {"items": [], "next": "m2"},
                                "m2": {"items": ["c"], "next": None}})
        self.assertEqual(collect_all(fetch), ["a", "b", "c"])
        self.assertEqual(calls, [None, "m1", "m2"])

    def test_final_empty_page_without_marker_ends_the_listing(self):
        fetch, calls = listing({None: {"items": ["a"], "next": "m1"}, "m1": {"items": [], "next": None}})
        self.assertEqual(collect_all(fetch), ["a"])
        self.assertEqual(calls, [None, "m1"])


if __name__ == "__main__":
    unittest.main()
