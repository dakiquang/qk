"""Tasks and the page of tasks the dashboard displays."""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Task:
    id: int
    title: str
    status: str
    created_at: str  # ISO 8601, for example "2026-11-02T09:30:00Z"
    owner: str = ""
    internal_notes: str = ""


@dataclass
class Page:
    """One page of tasks; `items` are in the order the dashboard displays them."""
    items: List[Task] = field(default_factory=list)
    number: int = 1


def filter_by_status(tasks, status):
    return [task for task in tasks if task.status == status]


def sort_tasks(tasks, key="created_at", reverse=False):
    return sorted(tasks, key=lambda task: getattr(task, key), reverse=reverse)


def paginate(tasks, size, number=1):
    start = (number - 1) * size
    return Page(items=list(tasks[start:start + size]), number=number)
