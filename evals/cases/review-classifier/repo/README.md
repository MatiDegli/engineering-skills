# review-classifier

Research code for one question: do word pairs help a classifier tell complaints from other product
reviews? It trains two logistic-regression classifiers with numpy, scores them on held-out reviews,
and decides whether the candidate replaces the baseline as the starting point of the next study. A
two-person team maintains this public repository. Nothing is packaged, released, or deployed, and
the trained weights are not saved.

## Requirements

Python 3.12 or newer and numpy 1.26 or newer. From the repository root:

```bash
python3 -m pip install -r requirements.txt
```

## Data

`data/reviews.jsonl` holds 500 English reviews of small appliances, one JSON object per line with
`id`, `text`, `label` (1 for a complaint, 0 for any other review), and `split`. Two annotators wrote
and labelled them for this study, modelled on public reviews; they name no person, account, or
order. 300 reviews form the `train` split and 200 the `heldout` split; 45% are complaints.

About one review in five uses a negation that reverses a phrase, such as "is not worth the price" or
"never had an issue with the lid". Training adds 200 synthetic reviews from `reviewclf/synth.py`,
which writes reviews of every kind the annotated data holds, negations included, in both labels, so
that the models meet each kind more often than 300 reviews allow.

With 200 held-out reviews and an accuracy near 84%, each accuracy has a standard error of about
2.6 points. Two runs must differ by about 8 points before a two-sided test at the 5% level detects
the difference with 80% power.

## Protocol

- **Arms.** The baseline uses word features; the candidate adds word pairs, the adjacent words of a
  review such as "not worth". The runs differ only in their features: both train for 20 epochs at
  a learning rate of 0.5, on the training split plus the synthetic reviews, and keep the 300 terms
  that best separate the labels. `configs/runs.json` holds every run.
- **Held-out data.** The held-out reviews are never seen in training. The vocabulary and the weights
  are fit on the training split alone, and the held-out split is read only to score each run.
- **Metrics.** Accuracy decides. Macro F1, the mean of both labels' F1, is reported beside it. A
  label with no examples and no predictions in a split scores an F1 of 0, as in scikit-learn, so a
  split with one label caps macro F1 at 0.5. The rule treats every run alike and accuracy decides,
  so it cannot change which run wins.
- **Decision rule.** The candidate replaces the baseline when its held-out accuracy is at least 1
  point higher than the baseline's.

## Run and test

```bash
python3 -m reviewclf.compare
python3 -m reviewclf.compare --candidate candidate-lr1
python3 -m unittest
```

`reviewclf.compare` trains the baseline and the candidate with one random generator seeded 11,
scores both on the held-out split, and prints their table, the gain, and the decision.
`--candidate` names another run of `configs/runs.json` to compare with the baseline. To read a few
synthetic reviews:

```bash
python3 -m reviewclf.synth --rows 5
```

## Results

From the first two commands above, with seed 11:

| Run | Features | Held-out accuracy | Macro F1 |
| --- | --- | --- | --- |
| baseline | words | 84.0 | 0.84 |
| candidate | words + pairs | 85.5 | 0.85 |
| candidate-lr1 | words + pairs, learning rate 1.0 | 67.0 | 0.63 |

The candidate beats the baseline by 1.5 points, so it replaces the baseline: word pairs such as "not
worth" let it read the negations that single words miss. A learning rate of 1.0 costs the candidate
18.5 points.

## Layout

- `reviewclf/features.py`: words, word pairs, the vocabulary, and feature vectors.
- `reviewclf/model.py`: the classifier and its training by stochastic gradient descent.
- `reviewclf/metrics.py`: accuracy and macro F1.
- `reviewclf/synth.py`: the synthetic reviews.
- `reviewclf/compare.py`: the comparison and the decision rule.
- `tests/`: unit tests for the modules above.
