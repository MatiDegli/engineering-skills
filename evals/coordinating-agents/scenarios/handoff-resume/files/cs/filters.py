"""Filters for the task list."""


def since(tasks, start):
    """Return the tasks due on or after `start`."""
    return [task for task in tasks if task["due"] >= start]
