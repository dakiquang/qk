import unittest

from collector.collect import collect_all


def listing(pages):
    """fetch_page over {marker: page}; an unexpected marker fails the test instead of looping."""
    calls = []

    def fetch_page(marker):
        calls.append(marker)
        if marker not in pages:
            raise AssertionError(f"unexpected marker {marker!r}")
        return pages[marker]
    return fetch_page, calls


class CollectTest(unittest.TestCase):
    def test_single_page(self):
        fetch, calls = listing({None: {"items": ["a", "b"], "next": None}})
        self.assertEqual(collect_all(fetch), ["a", "b"])
        self.assertEqual(calls, [None])

    def test_two_pages(self):
        fetch, calls = listing({None: {"items": ["a"], "next": "m1"}, "m1": {"items": ["b", "c"], "next": None}})
        self.assertEqual(collect_all(fetch), ["a", "b", "c"])
        self.assertEqual(calls, [None, "m1"])


if __name__ == "__main__":
    unittest.main()
