# Evaluation and experiments

Prediction generation and scoring are separate trust boundaries. Finish and
persist predictions before any process receives a gold path.

Run labeled examples with:

```bash
uv run python scripts/evaluate_examples.py
```

Part 1 scores unordered within-section cell pairs, including self-pairs. Part 3
scores cell sets per item, averages items within criteria, then weights criteria
equally. Report precision, recall, and F1 together with invalid-output rate,
mapped-item coverage, latency, token use, and estimated API cost.

For controlled experiments, change one factor at a time and preserve the
prediction, configuration, and trace. Classify failures as extraction, diff,
retrieval, financial interpretation, boundary choice, rubric interpretation,
or serialization. Do not tune only against aggregate score; inspect whether the
changed failure class plausibly generalizes.
