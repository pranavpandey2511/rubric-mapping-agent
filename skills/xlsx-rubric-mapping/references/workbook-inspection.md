# Workbook inspection

This reference contains the shared read-only inspection rules for all three stages.

Run inspection code only with the hosted `python` tool against the exact Python paths declared by the caller. The container has no network access and is unique to the current stage. Do not install packages or search for additional files. Prefer OpenPyXL and Pandas when available; if a required high-level parser is unavailable, use Python's standard `zipfile` and XML libraries for read-only OOXML inspection.

## Load formula and cached-value views

Open each workbook twice with OpenPyXL:

- `data_only=False` preserves formula text.
- `data_only=True` exposes cached results stored by Excel when they exist.

Align both views by exact sheet name and cell address. OpenPyXL does not calculate formulas, and a missing cache does not prove that a formula is invalid or evaluates to blank. Never save either loaded workbook; saving a `data_only=True` workbook can discard formula information.

Use normal loading for the full inspection because read-only mode can omit or complicate access to comments, styles, merged-cell details, and other metadata. A separate read-only pass is acceptable for a cheap inventory, but it cannot replace the complete pass.

## Preserve coordinate-level truth

For every worksheet, record:

- sheet name, workbook order, visibility, and tab properties;
- declared dimension, non-empty bounds, and styled bounds separately;
- raw value, formula text, cached value, data type, and number format by coordinate;
- merged ranges and their full spatial footprint;
- style identifiers plus meaningful font, fill, border, alignment, and protection properties;
- row heights, column widths, hidden states, and outline levels;
- tables, AutoFilters, freeze panes, print areas, defined names, and data validation;
- conditional-format rules, comments, hyperlinks, drawings, charts, and relationships when present.

Do not trust `max_row` or `max_column` alone. Old formatting can inflate worksheet dimensions far beyond meaningful content. Track populated cells, deliberately styled blank cells, and declared dimensions as different facts.

In a merged range, the top-left cell is the value-bearing anchor. The other coordinates still occupy layout space and may belong in a section. Expand merged footprints when reasoning about membership, but do not invent repeated values in the non-anchor cells.

Distinguish `None`, an empty string, numeric zero, and a formula whose cached result is empty. Dates are serialized numbers interpreted through workbook date settings and number formats; do not compare only display text.

## Compare formulas and results separately

Retain the original formula string. Also derive a normalized structural signature for repeated-formula analysis, such as a relative-reference or R1C1-like form. Never replace the raw formula with its signature.

Compare formula text and cached values as separate channels. A changed result with unchanged formula is not the assignment's formula-diff case, and two superficially similar formulas may refer to different sheets, defined names, or absolute references.

Preserve quoted sheet names and external references exactly. Workbook formulas may use shared formulas, array formulas, dynamic arrays, table references, and defined names. If OpenPyXL's high-level representation is ambiguous, inspect the relevant XML before classifying the cell.

## Use Pandas narrowly

Pandas is useful for bulk statistics such as sparsity, repeated labels, numeric density, or row and column profiles. It is not a workbook-layout parser: reading a sheet into a DataFrame can lose formulas, styles, merges, comments, blank formatted cells, and the original coordinate offset.

Create DataFrames only from coordinate-tagged records or with an explicit offset map. Return to the OpenPyXL/OOXML representation before emitting any cell address.

## Fall back to OOXML deliberately

An `.xlsx` file is a ZIP package. Inspect raw parts only when the high-level API is incomplete or when a finding needs verification. Relevant parts commonly include:

- `xl/workbook.xml` and workbook relationships for sheets, names, and links;
- `xl/worksheets/sheet*.xml` and worksheet relationships for cells, formulas, dimensions, merges, hyperlinks, and drawings;
- `xl/styles.xml`, theme files, and shared strings for formatting and text interpretation;
- `xl/tables/*.xml`, `xl/drawings/*.xml`, chart parts, comments, and external-link parts.

Resolve relationships rather than assuming that `sheet1.xml` is the first visible sheet. Theme and indexed colors require resolution; comparing only RGB fields can falsely treat identical styles as different.

## Avoid mutation and rendering hazards

- Do not open and re-save source files to "fix" them.
- Do not ask LibreOffice to recalculate. It may interpret formulas, links, fonts, or Excel-only features differently.
- Do not use a screenshot to recover exact cells; visual appearance is supporting human-debug evidence at most.
- For macro-enabled files, preserving VBA would require `keep_vba=True` if saving were ever allowed. This assignment is read-only and uses `.xlsx`, so do not add a save path.
- External links and cached values are evidence. Avoid any operation that refreshes or rewrites them.

## Compact the map without losing evidence

Summarize repeated structure as row bands, column bands, blocks, and formula/style signatures. Every summary must retain a reversible mapping to exact cells. Include local labels, period headers, neighboring rows, boundary signals, and input/complete state so the model can request focused detail instead of receiving a dense workbook dump.
