"""Collect every item from a paginated listing API."""


def collect_all(fetch_page):
    """Return all items of a listing, following `next` markers until the listing ends.

    `fetch_page(marker)` returns {"items": [...], "next": str or None}; the first call gets marker None.
    """
    collected = []
    marker = None
    while True:
        page = fetch_page(marker)
        items = page.get("items") or []
        collected.extend(items)
        marker = page.get("next")
        if not marker or not items:
            break
    return collected
