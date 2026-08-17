# Rubric Mapping Eval

`rubric-mapping-eval` is a deterministic evaluator for the two quantitative
outputs in the Rubric Mapping Work Trial:

- **Sectioning:** compare a predicted `sections.json` with a gold
  `sections.json` using grouped-cell-pair precision, recall, and F1.
- **I2C mapping:** compare a predicted `items_to_cells.json` with a gold mapping,
  calculate per-item cell precision, recall, and F1, and aggregate the results
  using the criterion structure in `rubric.json`.

The repository exposes both a Python API and a command-line interface. It does
not open or modify Excel workbooks; it evaluates the machine-readable JSON
artifacts produced by another system.

## Requirements and installation

- Python 3.11 or newer
- No runtime dependencies outside the Python standard library

Clone the repository and create its environment with `uv`:

```bash
git clone <repository-url> rubric-mapping-eval
cd rubric-mapping-eval
uv sync --locked
```

After installation, the following command lists the available commands:

```bash
uv run rubric-mapping-eval --help
```

## Metric conventions

All metric values are returned on a `0.0` to `1.0` scale:

```text
precision = true positives / all predictions
recall    = true positives / all gold answers
F1        = 2 * precision * recall / (precision + recall)
```

Results include the underlying true-positive, false-positive, and
false-negative counts so every score can be reproduced.

The gold comparison set must be non-empty. When a valid prediction set is
empty, precision, recall, and F1 are all reported as `0.0`.

## Sectioning evaluation

### Input schema

Both predicted and gold files use this exact structure:

```json
{
  "sections": [
    {
      "section_id": "section_001",
      "sheet": "Model",
      "cells": ["A1", "A2", "A3"]
    }
  ]
}
```

Section identifiers do not need to agree between predicted and gold files.
They are validated for uniqueness but do not participate in scoring. A predicted
file may use an empty `sections` array to represent no predicted sections; the
gold file must contain at least one section.

### How grouped pairs are constructed

For every section, the evaluator creates every unordered pair of cells in that
section. A cell is also paired with itself. For a section containing `A1`, `A2`,
and `A3`, the resulting pairs are:

```text
(A1, A1), (A2, A2), (A3, A3),
(A1, A2), (A1, A3), (A2, A3)
```

Each cell identity includes both the exact sheet name and address. A pair is
counted once even if overlapping sections create it more than once.

- **Grouping precision** is the fraction of predicted pairs also found in gold.
- **Grouping recall** is the fraction of gold pairs recovered by the prediction.
- **Grouping F1** balances grouping precision and recall.

The public `build_grouped_pairs()` helper exposes the exact transformation used
by the evaluator.

Because the evaluator materializes these relationships explicitly, pair
construction is quadratic in the number of cells inside a section. This is
usually modest for the supplied work-trial tasks, but an extremely large single
section can create many pairs and use correspondingly more memory.

### Python API

Evaluate files directly:

```python
from rubric_mapping_eval.sectioning import evaluate_section_files

result = evaluate_section_files(
    "predicted_sections.json",
    "gold_sections.json",
)
print(result["metrics"]["f1"])
```

Or inspect and evaluate parsed sections:

```python
import json

from rubric_mapping_eval.sectioning import (
    build_grouped_pairs,
    evaluate_sections,
    parse_sections,
)

with open("predicted_sections.json", encoding="utf-8") as handle:
    predicted = parse_sections(
        json.load(handle), context="predicted", allow_empty_sections=True
    )
with open("gold_sections.json", encoding="utf-8") as handle:
    gold = parse_sections(json.load(handle), context="gold")

predicted_pairs = build_grouped_pairs(predicted)
result = evaluate_sections(predicted, gold)
```

### CLI

```bash
uv run rubric-mapping-eval sectioning \
  --predicted predicted_sections.json \
  --gold gold_sections.json \
  --output sectioning_results.json
```

Omit `--output` to print the JSON result to stdout. The small files under
`examples/sectioning/` reproduces the worked sectioning example from the assignment:

```bash
uv run rubric-mapping-eval sectioning \
  --predicted examples/sectioning/predicted_sections.json \
  --gold examples/sectioning/gold_sections.json
```

The example returns precision `1.0`, recall `0.5`, and F1 `0.666...`.

## I2C mapping evaluation

### Input schemas

Predicted and gold `items_to_cells.json` files use this exact structure:

```json
{
  "items": [
    {
      "item_id": "1.1",
      "cells": [
        {"sheet": "Model", "address": "B2"},
        {"sheet": "Model", "address": "C2"}
      ]
    }
  ]
}
```

The evaluator also requires `rubric.json`. It reads:

```text
criteria -> each criterion's criterion_id -> grading -> each item_id
```

Other rubric fields are permitted and ignored. The item IDs in both mappings
must exactly match the rubric's item IDs.

Predicted items may use an empty `cells` array to explicitly record that an
item was not mapped. Gold items must contain at least one cell.

### Scores and aggregation

For every rubric item, the evaluator compares predicted and gold cell sets:

- **Cell precision:** selected cells that are in gold / all selected cells.
- **Cell recall:** selected gold cells / all gold cells.
- **Cell F1:** the F1 of cell precision and recall.

The result contains three levels:

1. `items`: precision, recall, F1, and counts for every `item_id`.
2. `criteria`: the unweighted average of item scores within each criterion.
3. `summary`: the unweighted criterion macro-average, the macro-average across
   all items, and the number and fraction of items with non-empty predictions.

The criterion macro-average is the primary aggregate. Each criterion receives
equal weight even when criteria contain different numbers of grading items.

### Python API

```python
from rubric_mapping_eval.i2c_mapping import evaluate_i2c_files

result = evaluate_i2c_files(
    "predicted_items_to_cells.json",
    "gold_items_to_cells.json",
    "rubric.json",
)
print(result["summary"]["criterion_macro"]["f1"])
```

The lower-level public functions `parse_item_mapping()`, `parse_rubric()`, and
`evaluate_item_mappings()` are available when the caller already holds parsed
JSON data.

### CLI

```bash
uv run rubric-mapping-eval i2c \
  --predicted predicted_items_to_cells.json \
  --gold gold_items_to_cells.json \
  --rubric rubric.json \
  --output i2c_results.json
```

An executable example is included under `examples/i2c_mapping/`:

```bash
uv run rubric-mapping-eval i2c \
  --predicted examples/i2c_mapping/predicted_items_to_cells.json \
  --gold examples/i2c_mapping/gold_items_to_cells.json \
  --rubric examples/i2c_mapping/rubric.json
```

## Batch evaluation

Batch evaluation uses an explicit manifest so files can live in any directory
layout. Paths are resolved relative to the manifest file unless they are
absolute.

```json
{
  "tasks": [
    {
      "task_id": "keysight",
      "sectioning": {
        "predicted": "predictions/keysight/sections.json",
        "gold": "gold/keysight/sections.json"
      },
      "i2c_mapping": {
        "predicted": "predictions/keysight/items_to_cells.json",
        "gold": "gold/keysight/items_to_cells.json",
        "rubric": "gold/keysight/rubric.json"
      }
    }
  ]
}
```

A task may declare sectioning, I2C mapping, or both. Task IDs must be unique.
The batch output includes every task result and unweighted macro-averages across
the tasks evaluated by each evaluator. For I2C, we compute criterion-macro F1
within each task, then average tasks equally.

```bash
uv run rubric-mapping-eval batch \
  --manifest batch_manifest.json \
  --output eval_results.json
```

Run the included batch example with:

```bash
uv run rubric-mapping-eval batch --manifest examples/batch/manifest.json
```

From Python:

```python
from rubric_mapping_eval.batch import evaluate_batch_manifest

result = evaluate_batch_manifest("batch_manifest.json")
```

## Strict validation

The evaluator fails with a descriptive error rather than repairing inputs.
Specifically:

- Cell addresses must already use canonical uppercase A1 notation without `$`
  characters or whitespace and must fall within Excel's row and column limits.
- Sheet names are compared exactly and are not normalized.
- Top-level and mapping-object keys must exactly match the documented schemas.
- Section IDs and item IDs must be unique.
- Duplicate cells within a section or item are errors.
- Predicted section files may contain no sections; gold section files may not.
- Every section must contain at least one cell.
- Predicted and gold I2C files must contain exactly the rubric's item IDs.
- Predicted item cell lists may be empty; gold item cell lists may not.
- The same cell may appear in multiple different sections or grading items.

Schema errors cause the CLI to exit with status code `2` and print a concise
message to stderr.

## Running tests

The test suite uses the standard library's `unittest` runner:

```bash
uv run python -m unittest discover -s tests -v
```

The tests cover pair construction, documented metric examples, overlapping
sections, strict address and duplicate validation, item and criterion
aggregation, missing IDs, empty gold items, and relative paths in batch
manifests.
