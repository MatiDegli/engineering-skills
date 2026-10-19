"""A logistic-regression complaint classifier trained by stochastic gradient descent."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from reviewclf.features import vectorize

L2 = 1e-4


def sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))


@dataclass
class Model:
    vocabulary: list[str]
    pairs: bool
    weights: np.ndarray
    bias: float

    def probabilities(self, texts: list[str]) -> np.ndarray:
        features = vectorize(texts, self.vocabulary, self.pairs)
        return sigmoid(features @ self.weights + self.bias)

    def predict(self, texts: list[str]) -> list[int]:
        """Label each text 1 (complaint) when its probability is at least 0.5, else 0."""
        return [int(p >= 0.5) for p in self.probabilities(texts)]


def train(
    rows: list[dict],
    vocabulary: list[str],
    pairs: bool,
    epochs: int,
    learning_rate: float,
    rng: np.random.Generator,
) -> Model:
    """Fit the weights on `rows`, visiting them in a new random order in each epoch."""
    if not rows or epochs < 1 or learning_rate <= 0:
        raise ValueError("training needs rows, at least one epoch, and a positive learning rate")
    features = vectorize([row["text"] for row in rows], vocabulary, pairs)
    labels = np.array([row["label"] for row in rows], dtype=float)
    weights = rng.normal(0.0, 0.01, len(vocabulary))
    bias = 0.0
    for _ in range(epochs):
        for index in rng.permutation(len(rows)):
            error = sigmoid(features[index] @ weights + bias) - labels[index]
            weights -= learning_rate * (error * features[index] + L2 * weights)
            bias -= learning_rate * error
    return Model(vocabulary, pairs, weights, float(bias))
