# Part 1 mapping workflow

Part 1 identifies the workbook's overall sections:

```text
create_overall_section(input.xlsx, complete.xlsx, instructions.md)
  -> sections.json + summary.md
```

`input.xlsx` is the starting workbook given to a human. The human follows
`instructions.md` to produce `complete.xlsx`, the completed workbook. Treat them
as the before-and-after states of the same task: use `complete.xlsx` to understand
the finished work, `input.xlsx` to identify what the human added or changed, and
unchanged cells as supporting context.

An overall section is a complete, coherent worksheet panel that performs one
recognizable financial-modeling purpose. Examples include an assumptions block,
a revenue build, an operating schedule, a valuation output, a sensitivity
table, or a compact control table. A section is defined by both its financial
meaning and its exact cell footprint.

For every section, extract:

- the exact worksheet name;
- every A1 cell address inside the confirmed section footprint;
- a concise business title; and
- a short technical detail of the section's purpose and major contents; and
- a plain-language explanation understandable without finance jargon.

Derive sections only from the workbooks and the supplied task instructions.

## Follow the declared execution scope

The user message declares `EXECUTION_SCOPE` for this invocation.

- In `sheet` scope, inspect cell-level contents only for `TARGET_SHEET` and emit
  sections only for that worksheet.
- In `workbook` scope, inspect every worksheet in the completed workbook and
  emit one workbook-wide set of sections.

For every worksheet owned by this invocation:

1. Inventory its local titles, header and period axes, enclosures,
   merged cells, populated cells, styled blanks, formula patterns, and controls.
2. Identify tentative panels without using a raw whole-workbook dump or task
   instructions as coordinate or extent evidence.
3. Apply the rules below, then inspect every tentative split and all four outer
   edges locally before deciding membership.
4. Return only sections owned by this invocation. The orchestrator validates
   the declared scope and assigns final section IDs.

## Use attached visual inspection for boundary ambiguity

When `inspect_workbook_view` is attached, use it selectively after the
structural inventory when a panel boundary remains ambiguous. Inspect a bounded
viewport around the tentative panel and all four proposed edges when titles,
merged headers, borders, fills, whitespace, repeated axes, or nearby controls
may clarify whether the area is one coherent panel or several adjacent panels.
Compare the matching `input` and `complete` regions when the before-and-after
layout helps explain the completed structure.

The tool is restricted to the current target worksheet in sheet scope. Use its
screenshot to confirm or challenge a structurally supported boundary, never to
invent cell addresses, include cells merely because they look enclosed, or
override cell contents, formulas, merged ranges, styles, and OOXML metadata.
Do not call it for every candidate when structural evidence already establishes
the boundary.

## Choose boundaries

- Choose the smallest complete panel supported by its local title or header,
  enclosure, financial role, and formulas. Keep uncertain neighboring panels
  separate; shared columns, styles, formulas, or subject matter alone do not
  justify merging them.
- After confirming a panel footprint, include every cell inside it, including
  internal blank or sparse rows and columns. Interior blankness never justifies
  moving an outer edge.
- Keep adjacent blocks together only when one uninterrupted local period or
  header axis governs the combined area and no same-level title, enclosure,
  role, or axis reset intervenes. A repeated or new local axis is a split
  boundary. A subtotal, historical/projected transition, style change, or blank
  gap alone is not.
- Inspect every target sheet for a compact lookup, dropdown, or control table
  used by formulas, defined names, or data validation. Include only that helper
  table's tight occupied footprint; do not pad it through surrounding blanks.
- Audit every proposed section's top, bottom, left, and right edges. Extend an
  edge only while local panel evidence continues; stop before a new title,
  axis, enclosure, helper area, or blank/default exterior. Never use worksheet
  used or styled bounds, and never overlap sections.

The model decides membership. Use Python only to inspect workbook evidence and
enumerate chosen addresses; do not ask Python to propose or choose rectangles.
Return no ranges, boundary descriptions, candidate regions, drawings, or
diagnostics.

## Write section descriptions

Describe a section only after its geometry is final.

- Use a specific three-to-ten-word business title.
- In no more than sixty words, explain the financial purpose, principal line
  items or calculations, and any important period or scenario structure.
- In no more than thirty-five words, explain the same section in ordinary
  language without unexplained finance jargon.
- Describe what the section does, not how it was found.
- Do not mention coordinates, confidence, validation, or extraction mechanics.
- Do not change a section's geometry to make its description sound cleaner.

## Final checks

Before writing the result, confirm that:

- every emitted worksheet exists;
- every cell is a valid, unique uppercase A1 address;
- every section is non-empty and internally coherent;
- no sections overlap;
- every confirmed panel includes its full rectangular interior, including blank
  and sparse cells;
- uncertain neighboring panels remain separate unless the shared-axis rule is
  fully satisfied;
- every repeated or new local axis, same-level title, enclosure, or role reset
  was respected as a boundary;
- compact functional lookup and control tables use only their tight occupied
  footprints;
- all four outer edges stop before a new title, axis, enclosure, helper area, or
  blank/default exterior; and
- every section has exactly one matching title, detail, and plain-language
  explanation in section order.

Follow [output-format.md](output-format.md) exactly.
