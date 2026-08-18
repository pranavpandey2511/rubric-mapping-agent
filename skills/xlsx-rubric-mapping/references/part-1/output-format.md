# Part 1 output format

The hosted stage output is internal JSON with exactly `sections` and
`section_summaries`. The host validates it, assigns final IDs, and writes the two
public artifacts below.

## `sections.json`

```json
{
  "sections": [
    {
      "section_id": "section_001",
      "sheet": "Model",
      "cells": ["B2", "C2", "B3", "C3"]
    }
  ]
}
```

- The root contains exactly `sections`.
- Every section contains exactly `section_id`, `sheet`, and `cells`.
- IDs are non-empty and unique. Every non-empty section belongs to one existing
  worksheet.
- Cells are explicit, unique uppercase A1 addresses. Ranges are invalid.
- Include blank cells only inside a confirmed panel footprint.
- Sort sections by workbook sheet order and top-left cell; sort cells row-major.

## Internal `section_summaries`

```json
{
  "section_summaries": [
    {
      "section_id": "section_001",
      "title": "Revenue Growth Drivers",
      "detail": "Summarizes historical revenue and the assumptions used to project growth.",
      "plain_language": "Shows past sales and how future sales are estimated."
    }
  ]
}
```

Every local section ID must have exactly one non-empty title, detail, and
plain-language explanation, in section order and with no extra IDs. Titles are
at most ten words, details at most sixty words, and plain-language explanations
at most thirty-five words. Do not add these fields to `sections`.

## `summary.md`

The host renumbers descriptions with the combined section IDs and renders:

```markdown
# Part 1 Section Summary

## section_001 — Revenue Growth Drivers

**Detail:** Summarizes historical revenue and the assumptions used to project growth.

**In normal words:** Shows past sales and how future sales are estimated.

**Worksheet:** `Model`
```

The summary is semantic and contains no cell coordinates. `sections.json` is
the only coordinate-bearing Part 1 artifact.

Write only the declared hosted JSON output and return only its path receipt. Do
not create diagnostics, confidence fields, drawings, or extra files.
