# Part 3 output format

Write `items_to_cells.json` with exactly this shape:

```json
{
  "items": [
    {
      "item_id": "1.1",
      "cells": [
        {"sheet": "Model", "address": "B2"}
      ]
    }
  ]
}
```

- The root contains exactly `items`.
- Every item contains exactly `item_id` and `cells`; every cell contains exactly
  `sheet` and `address`.
- Include every rubric item ID exactly once and no unknown IDs.
- Empty `cells` lists are valid.
- Sheet names match case exactly. Addresses are unique uppercase A1 cells.
- Every mapped coordinate belongs to the deterministic input-to-complete diff.
- Sort items in rubric order and cells by workbook sheet order then row-major.
- Keep confidence, evidence explanations, ranges, diagnostics, and provenance
  out of the artifact.

Serialize deterministically, validate the schema and eligible-diff membership,
write only the declared hosted JSON output, and return only its path receipt.
