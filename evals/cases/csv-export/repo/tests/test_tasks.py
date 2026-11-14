import unittest

from tasklist.tasks import Task, filter_by_status, paginate, sort_tasks


def task(n, status="open", created="2026-11-0{}T09:00:00Z"):
    return Task(id=n, title=f"Task {n}", status=status, created_at=created.format(n), owner="ops")


class TasksTest(unittest.TestCase):
    def test_filter_keeps_only_the_status(self):
        tasks = [task(1), task(2, status="done"), task(3)]
        self.assertEqual([t.id for t in filter_by_status(tasks, "open")], [1, 3])

    def test_sort_by_created_at(self):
        tasks = [task(3), task(1), task(2)]
        self.assertEqual([t.id for t in sort_tasks(tasks)], [1, 2, 3])
        self.assertEqual([t.id for t in sort_tasks(tasks, reverse=True)], [3, 2, 1])

    def test_paginate_returns_the_requested_page_in_order(self):
        tasks = [task(n) for n in range(1, 6)]
        page = paginate(tasks, size=2, number=2)
        self.assertEqual(page.number, 2)
        self.assertEqual([t.id for t in page.items], [3, 4])
        self.assertEqual(paginate(tasks, size=2, number=4).items, [])


if __name__ == "__main__":
    unittest.main()
