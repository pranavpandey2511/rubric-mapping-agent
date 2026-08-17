# Part 1: overall sections

Implement the assignment boundary:

```text
create_overall_section(input.xlsx, complete.xlsx, instructions.md) -> sections.json
```

The rubric is forbidden. Gold `sections.json` files and annotated review workbooks are evaluation data, not solver inputs.

## Objective

Group cells into high-level regions whose contents form a cohesive financial object: a schedule, statement, assumptions area, controls block, valuation output, or comparable semantic unit. Section identifiers are arbitrary; exact membership and grouping determine the score.

## Build candidate regions

1. Detect occupied and deliberately formatted blocks without trusting worksheet dimensions alone.
2. Identify title rows, multi-row headers, period bands, row labels, table bodies, totals, notes, and blank separators.
3. Record discontinuities in borders, fills, number formats, formula families, merged ranges, row/column sizing, and outline levels.
4. Compare input and complete by coordinate to distinguish template scaffolding from populated work, while retaining unchanged structure.
5. Attach instructions-derived business vocabulary to candidate regions without using instructions as coordinate evidence.

## Choose boundaries

- Keep titles, headers, labels, values, formulas, totals, and internal template blanks together when they describe one financial object.
- Include meaningful blank cells inside the block's layout or formatting footprint.
- Separate neighboring schedules when multiple signals show a change of purpose.
- Do not split a repeated table because one row is blank or sparse.
- Do not merge unrelated blocks merely because they share columns, colors, or number formats.
- Permit a union of rectangular bands when one semantic section is non-rectangular, but preserve explicit cells.
- Prefer boundaries supported by several independent signals. Re-inspect the local area when evidence conflicts.

Generate candidate geometry deterministically; let the model select or revise candidates using financial semantics. Avoid free-form generation of thousands of addresses.

## Optimize for the grouped-pair metric

The evaluator converts every section into all unordered cell pairs, including self-pairs, and deduplicates pairs across overlaps.

- Over-merging creates many false-positive cross-block pairs and reduces precision.
- Over-splitting removes relationships between cells that belong together and reduces recall.
- Omitting or adding one cell affects its self-pair and every relationship it has within the section.
- An error in a large section has greater pairwise impact than the same error in a small section.

Use conservative, evidence-backed boundaries, then expand to explicit cells only after the grouping is stable. Read `output-contracts.md` before writing `sections.json`.
