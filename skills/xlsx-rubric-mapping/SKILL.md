---
name: xlsx-rubric-mapping
description: Analyze financial-model XLSX workbooks across Part 1 overall sections, Part 2 rubric-independent semantic subsections, and Part 3 rubric item-to-cell mapping. Use when input.xlsx, complete.xlsx, instructions.md, and optionally rubric.json must be converted into exact sections.json, subsection evidence, or items_to_cells.json artifacts without modifying the workbooks.
---

# XLSX Rubric Mapping

Inspect financial-model workbooks as structured data, preserve exact cell coordinates, and use semantic reasoning only where deterministic extraction is insufficient. This skill covers all three assignment stages while keeping their input boundaries distinct.

> Modification notice: this project skill adapts selected technical guidance from OpenAI's historical Apache-2.0 `spreadsheet` skill and substantially changes its purpose, workflow, and outputs. See `NOTICE.txt` and `LICENSE.txt`.

## Route the task

Determine the stage from the declared function or `TASK_STAGE` marker. Always read [references/workbook-inspection.md](references/workbook-inspection.md), then read only the references for that stage:

- Part 1, overall section creation: [references/part-1-overall-sections.md](references/part-1-overall-sections.md) and [references/output-contracts.md](references/output-contracts.md).
- Part 2, intermediate subsections: [references/part-2-intermediate-sections.md](references/part-2-intermediate-sections.md) and [references/output-contracts.md](references/output-contracts.md).
- Part 3, items-to-cells mapping: [references/part-3-items-to-cells.md](references/part-3-items-to-cells.md) and [references/output-contracts.md](references/output-contracts.md).
- Example evaluation, ablations, or error analysis: [references/evaluation.md](references/evaluation.md).

Never load multiple stage references merely because the caller is running the complete pipeline. The orchestrator invokes the skill separately for Part 1, Part 2, and Part 3 and passes validated JSON artifacts between fresh invocations.

## Preserve the task boundary

- Read only the paths explicitly supplied for the current task.
- Never search for or open gold outputs, reviewer workbooks, prior predictions, or evaluator fixtures while generating a prediction.
- Part 1 and Part 2 must not receive or inspect `rubric.json`. Part 3 requires it.
- Part 2 receives the validated Part 1 `sections.json`. Part 3 may receive validated Part 1 and Part 2 artifacts as retrieval context.
- Never save, recalculate, repair, or modify `input.xlsx` or `complete.xlsx`. Use a temporary copy only if a future operation could write implicitly.
- Do not use screenshots, computer use, Excel, or LibreOffice in the initial runtime. Cell contents and OOXML metadata are the coordinate-level source of truth.
- Use only the hosted `python` tool for Python execution. Use the caller-provided Python paths, which refer to the current stage's isolated Code Interpreter container; do not look for a local shell, local Python, UV, or unlisted container files.
- Return only the artifact requested by the caller. The orchestrator validates and writes it. Keep traces, evidence, confidence, and diagnostic metadata out of evaluator-facing JSON.

## Use the right division of labor

- Use OpenPyXL and OOXML for deterministic extraction, coordinate-preserving comparison, and validation.
- Use Pandas only for bulk tabular summaries after the exact cell-level representation exists. Do not treat a DataFrame as the source of truth for formulas, styles, merged ranges, or coordinates.
- Use deterministic code to enumerate cells, compute the workbook diff, form candidates, and validate schemas.
- Use the language model to interpret financial meaning, choose section boundaries, classify subsection roles, and rank rubric-to-cell candidates.

## Common workflow

1. Confirm the stage and the allowed input roles.
2. Inspect the initial and completed workbooks independently, retaining formula text and cached results when available.
3. Build a compact coordinate-backed workbook map; compute the deterministic eligible diff when the stage needs it.
4. Apply the stage-specific workflow without widening its allowed context.
5. Re-inspect ambiguous local regions instead of guessing from a global summary.
6. Validate sheet names, coordinates, uniqueness, coverage, diff membership, exact keys, and deterministic ordering.
7. Return the requested JSON in the structured-response envelope; do not write it from the tool.
8. End the stage invocation before another stage or evaluation receives additional inputs.

Use this evidence priority when signals conflict: workbook cells and package XML, structural summaries derived from them, task instructions, and—only in Part 3—the rubric. A renderer is never authoritative for cell membership.
