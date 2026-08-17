# Output contracts

Evaluator-facing files must contain only the exact keys below. Do not add confidence, provenance, explanations, ranges, or diagnostics.

## Part 1: `sections.json`

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

- The root has exactly `sections`.
- Every section has exactly `section_id`, `sheet`, and `cells`.
- Section IDs are non-empty, unique, and deterministic.
- Each non-empty section belongs to exactly one existing worksheet.
- Cells are explicit, unique uppercase A1 addresses; range shorthand is invalid.
- Sort sections by workbook sheet order and top-left cell. Sort cells row-major.

## Part 3: `items_to_cells.json`

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

- The root has exactly `items`.
- Every item has exactly `item_id` and `cells`; every cell has exactly `sheet` and `address`.
- Include every rubric item ID exactly once and include no unknown IDs.
- Empty predicted `cells` lists are valid.
- Worksheet names must match case exactly. Addresses are unique uppercase A1 coordinates.
- Every mapped coordinate must be in the deterministic input-to-complete diff.
- Order items by their rubric order. Within an item, order cells by workbook sheet order, then row-major.

## Part 2: project handoff

The assignment has no required Part 2 evaluator artifact. This project writes `subsections.json` with exactly this internal handoff shape:

```json
{
  "subsections": [
    {
      "subsection_id": "subsection_001",
      "parent_section_id": "section_001",
      "sheet": "Model",
      "cells": ["B2", "C2"],
      "roles": ["historical", "input"]
    }
  ]
}
```

The root has exactly `subsections`; every subsection has exactly the five fields shown. IDs are unique and deterministic, `parent_section_id` identifies an existing Part 1 section, sheet names and explicit A1 cells follow the Part 1 rules, and roles are short semantic tags. Never mix evidence, confidence, or other diagnostics into this handoff.

## Final validation

Serialize JSON deterministically and validate it with the supplied evaluator parser or an equivalent strict schema check before returning. Write to a temporary output in the destination directory and replace the requested artifact only after validation succeeds.
