---
name: excel
description: Inspect and interpret Excel financial-model workbooks as read-only structured documents. Use for coordinate-aware .xlsx and .xlsm analysis with formula and cached-value views, workbook structure, optional rendered views for unresolved layout questions, and separate-copy recalculation only when a required cached formula result is missing. Never overwrite or otherwise modify a source workbook.
---

# Excel Workbook Inspection

Use this skill only for read-only workbook inspection. It provides workbook
mechanics, not domain semantics or output formats.

For evaluator-facing section or item-to-cell mapping, also use the available `xlsx-rubric-mapping` skill. That skill governs stage inputs, mapping rules,
allowed references, and JSON outputs.

## Keep the workbook read-only

- Never save, edit, repair, recalculate, refresh, or overwrite a source
  workbook.
- Use only the files and paths supplied for the current task.
- Treat worksheet names and cell coordinates as exact identifiers.
- Do not use rendered views as proof of exact cell membership.

## Inspect the workbook

- Use OpenPyXL for coordinate-aware inspection and raw OOXML when OpenPyXL is
  ambiguous.
- Load formula (`data_only=False`) and cached-value (`data_only=True`) views
  separately when both matter. OpenPyXL does not calculate formulas, and a
  missing cached value does not mean a formula is blank or invalid.
- Preserve workbook order and distinguish formulas, cached values, styles,
  comments, merged ranges, hidden state, defined names, validations, tables,
  filters, and links when relevant.
- Treat merged non-anchor cells as layout space. Distinguish `None`, empty
  text, numeric zero, and an empty formula result.
- Do not trust `max_row`, `max_column`, or styled blank cells as content
  boundaries.
- Use Pandas only for coordinate-tagged summaries; keep the workbook or OOXML
  representation as the source of truth.
- Close workbook handles after inspection.

## Interpret financial-model structure

- Use labels, units, number formats, period axes, historical and forecast
  bands, assumptions, formulas, totals, and subtotals to understand each
  region's role.
- Compare formula families and references to identify repeated schedules and
  related calculation blocks. Use cached values for magnitude and context, but
  remember that they may be missing or stale.
- Treat formatting as supporting semantic evidence, not proof of a boundary or
  cell relationship. This skill interprets model structure; it does not audit
  or repair the model's financial logic.

## Use rendered views selectively

- Rendering does not require recalculation. When the task-specific runtime
  provides `inspect_workbook_view`, use it only after programmatic inspection
  leaves a question about merged headers, whitespace, repeated axes, labels,
  or panel boundaries.
- The repository's visual tool opens the workbook read-only, disables macros
  and external-link updates, creates a temporary view, and closes without
  saving the source.
- A rendered value may reflect the viewer's in-memory interpretation. Use the
  workbook and OOXML views for formulas, cached values, and exact coordinates;
  use the rendering only for visual layout.

## Handle missing cached values

Recalculation is unnecessary for opening, structural inspection, or rendering.
If a cached value is absent, first use the formula text and surrounding model
structure. Recalculate only when the exact numeric result is necessary for the
current interpretation.

- Never recalculate a source workbook in place.
- For `.xlsx`, use [the recalculation helper](scripts/recalc.py) with distinct
  source and output paths. It uses LibreOffice only when `soffice` is available,
  refuses workbooks with external links, and verifies that formulas are
  unchanged before publishing the recalculated copy.
- In hosted Code Interpreter, the helper's logic can run only if that container
  has a `soffice` executable. The skill file does not install LibreOffice.
- The helper intentionally does not recalculate `.xlsm`; use the original
  formula and cached-value views rather than risking VBA loss.
- Use a recalculated copy only as an additional `data_only=True` value view.
  Continue to use the original workbook for formulas, coordinates, workbook
  structure, diff eligibility, and emitted mappings.

Return to the task-specific skill for interpretation, validation, and artifact
creation.
