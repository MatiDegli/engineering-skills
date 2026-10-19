import unittest

import numpy as np

from reviewclf.features import select_vocabulary, terms, tokenize, vectorize
from reviewclf.model import train
from reviewclf.synth import generate

ROWS = [
    {"text": "The kettle broke after one week.", "label": 1},
    {"text": "The lamp broke on the first day.", "label": 1},
    {"text": "Refund took weeks, very disappointed.", "label": 1},
    {"text": "The kettle works well.", "label": 0},
    {"text": "The lamp works well and looks great.", "label": 0},
    {"text": "Great value, happy with it.", "label": 0},
]


class FeatureTests(unittest.TestCase):
    def test_words_are_lowercased_and_keep_contractions(self):
        self.assertEqual(tokenize("Doesn't WORK, sadly."), ["doesn't", "work", "sadly"])

    def test_pairs_add_each_pair_of_adjacent_words(self):
        self.assertEqual(terms("works well today", pairs=False), ["works", "well", "today"])
        self.assertEqual(
            terms("works well today", pairs=True),
            ["works", "well", "today", "works well", "well today"],
        )

    def test_the_vocabulary_keeps_the_terms_that_separate_the_labels(self):
        vocabulary = select_vocabulary(ROWS, 4, pairs=False)
        self.assertEqual(vocabulary, ["broke", "great", "well", "works"])
        self.assertNotIn("the", select_vocabulary(ROWS, 8, pairs=False))

    def test_the_vocabulary_has_at_most_the_requested_size(self):
        self.assertEqual(len(select_vocabulary(ROWS, 5, pairs=True)), 5)

    def test_vectors_mark_the_vocabulary_terms_a_text_contains(self):
        matrix = vectorize(["works well", "broke"], ["broke", "well", "works well"], pairs=True)
        np.testing.assert_array_equal(matrix, [[0, 1, 1], [1, 0, 0]])


class ModelTests(unittest.TestCase):
    def test_training_fits_a_separable_set(self):
        vocabulary = select_vocabulary(ROWS, 10, pairs=False)
        model = train(ROWS, vocabulary, False, 30, 0.5, np.random.default_rng(0))
        self.assertEqual(model.predict([row["text"] for row in ROWS]), [1, 1, 1, 0, 0, 0])

    def test_the_same_seed_gives_the_same_weights(self):
        vocabulary = select_vocabulary(ROWS, 10, pairs=True)
        first = train(ROWS, vocabulary, True, 5, 0.5, np.random.default_rng(3))
        second = train(ROWS, vocabulary, True, 5, 0.5, np.random.default_rng(3))
        np.testing.assert_array_equal(first.weights, second.weights)

    def test_invalid_training_settings_are_rejected(self):
        rng = np.random.default_rng(0)
        for rows, epochs, rate in (([], 1, 0.5), (ROWS, 0, 0.5), (ROWS, 1, 0.0)):
            with self.subTest(rows=len(rows), epochs=epochs, rate=rate):
                with self.assertRaises(ValueError):
                    train(rows, ["broke"], False, epochs, rate, rng)


class SyntheticTests(unittest.TestCase):
    def test_generated_reviews_alternate_labels_and_repeat_for_a_seed(self):
        rows = generate(6, np.random.default_rng(5))
        self.assertEqual([row["label"] for row in rows], [1, 0, 1, 0, 1, 0])
        self.assertEqual(rows, generate(6, np.random.default_rng(5)))
        self.assertTrue(all(row["text"].strip() for row in rows))


if __name__ == "__main__":
    unittest.main()
