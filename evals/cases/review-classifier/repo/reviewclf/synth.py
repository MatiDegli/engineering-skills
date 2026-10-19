"""Synthetic product reviews that augment the training split."""

from __future__ import annotations

import argparse
import json

import numpy as np

PRODUCTS = (
    "kettle", "toaster", "blender", "desk lamp", "hair dryer", "speaker",
    "bike light", "alarm clock", "desk fan", "coffee grinder", "rice cooker", "radio",
)
OTHER = (
    "works exactly as described", "arrived early and well packed", "feels solid in the hand",
    "is worth every cent", "was easy to set up", "still works after months of daily use",
    "looks better than in the photos", "is quiet and quick", "heats up fast", "is easy to clean",
)
COMPLAINT = (
    "stopped working after a week", "arrived with a cracked lid", "is smaller than described",
    "broke the second time I used it", "was missing a part", "smells of burnt plastic",
    "leaks from the base", "trips the fuse", "rattles when it runs",
    "drains its battery overnight",
)
OPENERS = ("The", "My", "This")
CLOSINGS = {
    0: ("", " Happy with it.", " Would buy again.", " Good value."),
    1: ("", " I want a refund.", " Very disappointed.", " Returning it today."),
}
TEMPLATES = (
    "{opener} {product} {phrase}.{closing}",
    "Bought a {product} last month and it {phrase}.{closing}",
    "Got the {product} as a gift and it {phrase}.{closing}",
)


def generate(count: int, rng: np.random.Generator) -> list[dict]:
    """Return `count` reviews, alternating complaints (label 1) and other reviews (label 0)."""
    rows = []
    for index in range(count):
        label = (index + 1) % 2
        phrases = COMPLAINT if label else OTHER
        text = TEMPLATES[rng.integers(len(TEMPLATES))].format(
            opener=OPENERS[rng.integers(len(OPENERS))],
            product=PRODUCTS[rng.integers(len(PRODUCTS))],
            phrase=phrases[rng.integers(len(phrases))],
            closing=CLOSINGS[label][rng.integers(len(CLOSINGS[label]))],
        )
        rows.append({"id": f"synthetic-{index + 1}", "text": text, "label": label})
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print synthetic reviews as JSON lines.")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args(argv)
    for row in generate(args.count, np.random.default_rng(args.seed)):
        print(json.dumps(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
