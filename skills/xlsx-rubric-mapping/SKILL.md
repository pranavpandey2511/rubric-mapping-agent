---
name: xlsx-rubric-mapping
description: Analyze financial-model XLSX workbooks across Part 1 overall sections, Part 2 rubric-independent semantic subsections, and Part 3 rubric item-to-cell mapping. Use when input.xlsx, complete.xlsx, instructions.md, and optionally rubric.json must be converted into exact sections.json, subsection evidence, or items_to_cells.json artifacts without modifying the workbooks. When an Excel skill is available, use it as companion guidance for workbook inspection and handling.
---

# XLSX Rubric Mapping

Inspect financial-model workbooks as structured data, preserve exact cell
coordinates, and use semantic reasoning only where deterministic extraction is
insufficient. Keep the three assignment stages isolated.

## Combine compatible skills

When an `excel` skill is available, read it whenever the task requires inspecting or operating on workbook files. It may be read before or after this skill. Use its workbook mechanics together with this skill's mapping semantics, stage boundaries, and output contracts. Because this workflow is read-only, do not apply workbook editing, recalculation, or source-saving procedures to `input.xlsx` or `complete.xlsx`.

## Route the task

Determine the stage from the declared function or `TASK_STAGE`. Read exactly the
two references for that stage:

- Part 1: [workflow](references/part-1/part-1-workflow.md) and
  [output format](references/part-1/output-format.md).
- Part 2: [workflow](references/part-2/part-2-workflow.md) and
  [output format](references/part-2/output-format.md).
- Part 3: [workflow](references/part-3/part-3-workflow.md) and
  [output format](references/part-3/output-format.md).

Never load multiple stage references merely because the caller is running the complete pipeline. The orchestrator invokes the skill separately for Part 1, Part 2, and Part 3 and passes only the validated JSON and/or Markdown artifacts selected by the handoff policy between fresh invocations.

## Preserve the task boundary

- Read only the paths explicitly supplied for the current task.
- Never search for or open reference outputs, reviewer workbooks, prior
  predictions, or hidden fixtures while generating a prediction.
- Part 1 and Part 2 must not receive or inspect `rubric.json`. Part 3 requires it.
- Part 2 receives at least one of the validated Part 1 `sections.json` or its
  matching `summary.md`; both are supplied by default. Part 3 may receive the
  corresponding validated Part 1 JSON and summary plus Part 2
  `subsections.json` and the Part 2 agent-authored `subsection_index.json` as
  retrieval context. Part 2 does not generate a Markdown summary. The host
  downloads the two agent-authored Part 2 JSON artifacts directly. In sheet
  scope it only concatenates their arrays in workbook order; it does not rename
  IDs or synthesize semantic families or relationships.
- Never save, recalculate, repair, or modify `input.xlsx` or `complete.xlsx`. Use a temporary copy only if a future operation could write implicitly.
- Do not use screenshots, computer use, Excel, or LibreOffice unless the
  runtime-selected stage workflow explicitly provides a visual-inspection
  workflow. Cell contents and OOXML metadata remain the coordinate-level source
  of truth.
- Use only the hosted `python` tool for Python execution. Use the caller-provided Python paths, which refer to the current stage's isolated Code Interpreter container; do not look for a local shell, local Python, UV, or unlisted container files.
- Write only the requested stage JSON to the caller-declared hosted Python
  output path. Part 1's stage JSON contains strict sections plus the summary
  companion defined in Part 1's output-format reference; the orchestrator
  separates the final `sections.json` and `summary.md`. Do not print it or create other
  artifacts. Keep traces, evidence, confidence, and diagnostics out of the
  strict output JSON. Part 2 writes strict `subsections.json` and semantic
  `subsection_index.json` directly to their two caller-declared hosted output
  paths.

## Inspect workbooks safely

- Load formula (`data_only=False`) and cached-value (`data_only=True`) views and
  align them by exact sheet and coordinate. A missing cache is not a blank or
  invalid formula.
- Preserve raw values, formulas, styles, merged footprints, row/column state,
  names, validation, tables, filters, and workbook order. Do not trust
  `max_row`, `max_column`, or styled bounds as content boundaries.
- Treat merged non-anchor coordinates as layout space without inventing repeated
  values. Distinguish `None`, empty strings, zero, and empty formula caches.
- Keep raw formulas and derive separate normalized signatures for repeated
  family analysis. Inspect OOXML relationships when OpenPyXL is ambiguous.
- Use Pandas only for coordinate-tagged bulk summaries; return to the
  OpenPyXL/OOXML representation before emitting cells.
- Never save, repair, recalculate, or refresh source workbooks or external
  links. Use visual inspection only to resolve structural ambiguity, never as
  exact coordinate evidence.
- Compact repeated structure only when every summary remains reversible to
  exact cells.

## Use the right division of labor

- Use OpenPyXL and OOXML for deterministic extraction, coordinate-preserving comparison, and validation.
- Use Pandas only for bulk tabular summaries after the exact cell-level representation exists. Do not treat a DataFrame as the source of truth for formulas, styles, merged ranges, or coordinates.
- Use deterministic code to enumerate cells, compute the workbook diff, retrieve requested local evidence, and validate schemas. In Part 3, code may also form item-to-cell candidates.
- Use the language model to interpret financial meaning, choose section boundaries, classify subsection roles, and rank rubric-to-cell candidates.

## Common workflow

1. Confirm the stage and the allowed input roles.
2. Inspect the initial and completed workbooks independently, retaining formula text and cached results when available.
3. Build a compact coordinate-backed workbook map; compute the deterministic eligible diff when the stage needs it.
4. Read and apply the selected stage workflow and output-format files.
5. Re-inspect ambiguous local regions instead of guessing from a global summary.
6. Validate sheet names, coordinates, uniqueness, coverage, diff membership, exact keys, and deterministic ordering.
7. Write the requested stage JSON to the declared hosted Python output path and return only its path receipt.
8. End the stage invocation before another stage or evaluation receives additional inputs.

Use this evidence priority when signals conflict: workbook cells and package
XML, reversible structural summaries, task instructions, and—only in Part
3—the rubric. A renderer is never authoritative for cell membership.
