import unittest

from reviewclf.metrics import accuracy, f1, macro_f1


class AccuracyTests(unittest.TestCase):
    def test_accuracy_is_the_share_of_matching_labels(self):
        self.assertEqual(accuracy([1, 0, 1, 0], [1, 0, 0, 0]), 0.75)

    def test_empty_or_mismatched_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            accuracy([], [])
        with self.assertRaises(ValueError):
            accuracy([1, 0], [1])


class F1Tests(unittest.TestCase):
    def test_f1_combines_precision_and_recall_of_one_label(self):
        # Label 1: one true positive, one false positive, one false negative.
        self.assertAlmostEqual(f1([1, 1, 0, 0], [1, 0, 1, 0], 1), 0.5)

    def test_macro_f1_is_the_mean_over_both_labels(self):
        labels, predictions = [1, 1, 1, 0], [1, 1, 0, 0]
        expected = (f1(labels, predictions, 0) + f1(labels, predictions, 1)) / 2
        self.assertAlmostEqual(macro_f1(labels, predictions), expected)
        self.assertAlmostEqual(macro_f1(labels, labels), 1.0)

    def test_a_label_absent_from_a_split_and_its_predictions_scores_zero(self):
        # Documented choice, as in scikit-learn: no complaints and none predicted gives F1 0 for
        # label 1, so a perfect run on such a split has a macro F1 of 0.5.
        self.assertEqual(f1([0, 0, 0], [0, 0, 0], 1), 0.0)
        self.assertEqual(macro_f1([0, 0, 0], [0, 0, 0]), 0.5)

    def test_a_predicted_label_that_never_occurs_scores_zero(self):
        self.assertEqual(f1([0, 0], [1, 0], 1), 0.0)


if __name__ == "__main__":
    unittest.main()
