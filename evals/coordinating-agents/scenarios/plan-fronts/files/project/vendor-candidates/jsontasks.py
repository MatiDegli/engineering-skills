# SPDX-License-Identifier: GPL-3.0-or-later
"""Read tasks from a JSON document: a list of objects with id, title, and due."""

import json
from datetime import date


def parse_json_tasks(text):
    """Return one dict per JSON object with id, title, and due date."""
    return [
        {"id": str(item["id"]), "title": item["title"], "due": date.fromisoformat(item["due"])}
        for item in json.loads(text)
    ]
