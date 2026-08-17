# Evaluation and experiments

Prediction generation and scoring are separate trust boundaries. The solver must finish and write its prediction before any process receives a gold path.

## Run the labeled examples

Place predictions under `predictions/<task>/`, then run both Part 1 and Part 3 evaluators with:

```bash
uv run python scripts/evaluate_examples.py
```

The helper calls the supplied `rubric_mapping_eval` Python APIs and writes aggregate results. Use its help output to inspect filtering and path options.

## Interpret the metrics

- Part 1 scores the set of unordered within-section cell pairs, including self-pairs.
- Part 3 scores predicted cells per item, averages items within each criterion, and then averages criteria equally.
- Report precision, recall, and F1 together. Also record invalid-output rate, mapped-item fraction, latency, token use, and estimated API cost.

## Use controlled ablations

Change one factor at a time and preserve the prediction and trace for each run:

1. values/formulas/merges only versus added styles and formatted blanks;
2. input only, complete only, and paired-workbook comparison;
3. candidate-region selection versus unconstrained cell generation;
4. instructions present versus removed;
5. Part 3 direct retrieval versus Part 1 plus Part 2 hierarchical retrieval;
6. raw labels versus formula/dependency features;
7. model and reasoning-effort choices, including cost and latency;
8. optional visual evidence only after the structural system has a stable baseline.

Classify failures as extraction, diff, candidate retrieval, financial interpretation, boundary choice, rubric interpretation, or serialization. Do not tune only against the aggregate score; inspect which error class changed and whether the change plausibly generalizes.
