# Part 2 output format

The Part 2 agent writes two files directly:

- `/mnt/data/subsections.json`; and
- `/mnt/data/subsection_index.json`.

The host never separates a combined response and never renames IDs. For
sheet-scoped execution it only concatenates arrays from the agent-generated
files in workbook order.

## `subsections.json`

Keep `subsections` in exactly this public handoff shape:

```json
{
  "subsections": [
    {
      "subsection_id": "subsection_s001_001",
      "parent_section_id": "section_001",
      "sheet": "Model",
      "cells": ["B4", "C4"],
      "roles": ["historical", "input"]
    }
  ]
}
```

- Every subsection contains exactly the five fields shown.
- IDs are deterministic and workbook-unique using
  `subsection_s<sheet-position-3-digits>_<within-sheet-3-digits>`.
- `parent_section_id` identifies an existing Part 1 section on the same sheet.
- Every uppercase A1 address lies inside its parent section.
- `roles` is non-empty and uses only the taxonomy in `part-2-workflow.md`.

## `subsection_index.json`

The `subsection_index` root has exactly this shape:

```json
{
  "schema_version": 2,
  "generated_by": "part2_agent",
  "families": [
    {
      "family_id": "subsection_s001_001_family_01",
      "subsection_id": "subsection_s001_001",
      "parent_section_id": "section_001",
      "sheet": "Model",
      "object_name": "Revenue",
      "aliases": ["Sales"],
      "changed_cells": ["C4"],
      "anchor_cells": ["B4"],
      "roles": ["historical", "input"],
      "scope": {
        "period_type": "historical",
        "period_headers": [{"cell": "C3", "label": "2025A"}]
      },
      "orientation": "row",
      "calculation_kind": "input",
      "formula_signatures": []
    }
  ],
  "relationships": [
    {
      "source_family_id": "subsection_s001_001_family_01",
      "target_family_id": "subsection_s001_002_family_01",
      "relationship": "paired_with"
    }
  ]
}
```

Contract rules:

- `schema_version` is exactly `2` and `generated_by` is exactly
  `part2_agent`.
- Every family contains exactly the thirteen fields shown.
- Every family references an emitted subsection and repeats its exact parent
  section and worksheet.
- `object_name` is a concise workbook-native semantic name. `aliases` is a
  unique string list and may be empty.
- `changed_cells` is a non-empty unique list. Each address must be an eligible
  nonblank input-to-complete change inside the referenced subsection. Every
  eligible changed cell in every subsection appears in exactly one family.
- `anchor_cells` is a unique list of unchanged interpreting cells inside the
  referenced subsection. It may be empty and cannot overlap `changed_cells`.
- `roles` is a non-empty subset of the referenced subsection's roles.
- `scope` contains exactly `period_type` and `period_headers`.
  `period_type` is `historical`, `projected`, or `unspecified`.
  Each period-header record contains exactly uppercase A1 `cell` and non-empty
  `label`.
- `orientation` is `row`, `column`, `block`, or `non_contiguous`.
- `calculation_kind` uses one allowed kind from the Part 2 instructions.
- `formula_signatures` is a unique string list and may be empty.
- Every relationship contains exactly `source_family_id`, `target_family_id`,
  and `relationship`. Both family IDs must exist, differ, and use one of
  `feeds`, `linked_to`, `component_of`, or `paired_with`.
- Do not emit duplicate relationships.

Write `/mnt/data/subsections.json` as:

```json
{
  "subsections": []
}
```

Write `/mnt/data/subsection_index.json` separately as:

```json
{
  "schema_version": 2,
  "generated_by": "part2_agent",
  "families": [],
  "relationships": []
}
```

Populate all arrays. Serialize deterministically, write only these two declared
files, and return both paths in the structured receipt.
