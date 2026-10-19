"""Accuracy and macro F1 for labels 1 (complaint) and 0 (other review)."""

from __future__ import annotations

LABELS = (0, 1)


def _check(labels: list[int], predictions: list[int]) -> None:
    if not labels or len(labels) != len(predictions):
        raise ValueError("labels and predictions must be non-empty and of equal length")


def accuracy(labels: list[int], predictions: list[int]) -> float:
    _check(labels, predictions)
    return sum(label == prediction for label, prediction in zip(labels, predictions)) / len(labels)


def f1(labels: list[int], predictions: list[int], label: int) -> float:
    """F1 of one label. A label with no examples and no predictions scores 0, as in scikit-learn."""
    _check(labels, predictions)
    pairs = list(zip(labels, predictions))
    true_positives = sum(actual == label and predicted == label for actual, predicted in pairs)
    false_positives = sum(actual != label and predicted == label for actual, predicted in pairs)
    false_negatives = sum(actual == label and predicted != label for actual, predicted in pairs)
    denominator = 2 * true_positives + false_positives + false_negatives
    return 2 * true_positives / denominator if denominator else 0.0


def macro_f1(labels: list[int], predictions: list[int]) -> float:
    return sum(f1(labels, predictions, label) for label in LABELS) / len(LABELS)
