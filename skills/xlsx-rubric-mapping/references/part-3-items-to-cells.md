# Part 3: items-to-cells mapping

Implement the assignment boundary:

```text
create_items_to_cells_mapping(
    input.xlsx,
    complete.xlsx,
    instructions.md,
    rubric.json,
) -> items_to_cells.json
```

The rubric is required here. Gold mappings and evaluator fixtures remain forbidden during prediction generation.

## Compute the eligible diff first

Create the candidate universe deterministically before semantic mapping. A cell is eligible when, at the same sheet and coordinate:

1. `complete.xlsx` contains cell content that is absent or different in `input.xlsx`; or
2. `complete.xlsx` contains a formula whose formula text differs from `input.xlsx`.

Use exact content and raw formula comparisons; do not define the diff from rendered values alone. Retain, for every diff cell, both workbook states, formula signatures, styles, neighboring labels, section/subsection memberships, period, semantic role, and dependencies. Validate every final predicted cell against this diff set.

## Parse the rubric completely

Enumerate every `item_id` under every criterion exactly once. Preserve the criterion description, item condition, point information, partial-credit guidance, deductions, and grading notes as context, but map cells at item granularity. The final JSON must contain every rubric item ID, including items for which the prediction is an empty list.

## Retrieve candidates before final reasoning

1. Retrieve likely Part 1 sections from financial-object and label matches.
2. Narrow through Part 2 roles, periods, formula families, and subsection evidence.
3. Intersect with the eligible diff cells.
4. Provide the model a compact candidate table with enough local row/column context to reject plausible but incorrect cells.
5. Re-inspect ambiguous regions or formula dependencies before deciding.

Rank candidates using several signals:

- rubric language and nearby workbook labels;
- historical/projection and input/output distinctions;
- requested periods, scenarios, and financial-object identity;
- formula structure and precedent/dependent relationships;
- row and column headers, section membership, and task instructions;
- whether the cell is the evidence a judge should inspect, not merely a remote supporting precedent.

Lexical similarity alone is insufficient. Do not map an entire section when the item concerns one row, one period band, or one assumption family. A cell may legitimately map to multiple grading items.

## Calibrate precision and recall

The evaluator scores each item's cell set, averages items within a criterion, and then weights criteria equally. One oversized mapping can damage cell precision, while an empty mapping has zero recall. Prefer a small evidence-backed set over arbitrary section-wide coverage, but use labeled-example evaluation to calibrate this threshold rather than applying a universal precision-only rule.

Track uncertainty internally with the candidate score, competing interpretation, and missing evidence. Do not add uncertainty fields to `items_to_cells.json`. Read `output-contracts.md` before writing the artifact.
