"""Train the baseline and a candidate run, score both on the held-out reviews, and decide."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from reviewclf.features import select_vocabulary
from reviewclf.metrics import accuracy, macro_f1
from reviewclf.model import train
from reviewclf.synth import generate

ROOT = Path(__file__).resolve().parents[1]
VOCABULARY_SIZE = 300
MIN_GAIN = 0.01


def decide(baseline_accuracy: float, candidate_accuracy: float) -> str:
    if candidate_accuracy - baseline_accuracy >= MIN_GAIN:
        return "the candidate replaces the baseline"
    return "keep the baseline"


def read_reviews(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def run_arm(config: dict, reviews: list[dict], rng: np.random.Generator) -> dict[str, float]:
    """Train one run on the training split and score it on the held-out split."""
    train_rows = [row for row in reviews if row["split"] == "train"]
    heldout = [row for row in reviews if row["split"] == "heldout"]
    pairs = config["features"] == "words+pairs"
    vocabulary = select_vocabulary(reviews, VOCABULARY_SIZE, pairs)
    rows = train_rows[: config.get("train_rows", len(train_rows))]
    rows += generate(config["synthetic_rows"], rng)
    model = train(rows, vocabulary, pairs, config["epochs"], config["learning_rate"], rng)
    labels = [row["label"] for row in heldout]
    predictions = model.predict([row["text"] for row in heldout])
    return {"accuracy": accuracy(labels, predictions), "macro_f1": macro_f1(labels, predictions)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "reviews.jsonl")
    parser.add_argument("--runs", type=Path, default=ROOT / "configs" / "runs.json")
    parser.add_argument("--baseline", default="baseline", help="run name in the runs file")
    parser.add_argument("--candidate", default="candidate", help="run name in the runs file")
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args(argv)

    runs = json.loads(args.runs.read_text(encoding="utf-8"))
    reviews = read_reviews(args.data)
    rng = np.random.default_rng(args.seed)
    arms = {"baseline": args.candidate, "candidate": args.candidate}
    scores = {arm: run_arm(runs[name], reviews, rng) for arm, name in arms.items()}

    print("| Arm | Held-out accuracy | Macro F1 |")
    print("| --- | --- | --- |")
    for arm, score in scores.items():
        print(f"| {arm} | {100 * score['accuracy']:.1f} | {score['macro_f1']:.2f} |")
    baseline, candidate = scores["baseline"]["accuracy"], scores["candidate"]["accuracy"]
    print(f"\nGain: {100 * (candidate - baseline):+.1f} points; {decide(baseline, candidate)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
